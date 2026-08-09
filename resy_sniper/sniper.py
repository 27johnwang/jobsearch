"""Booking strategy: wait for the drop, burst-poll for slots, book the best match."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .client import ResyClient, ResyError, Slot

log = logging.getLogger("resy_sniper.sniper")


@dataclass
class BookingRequest:
    venue_id: str
    day: str                       # reservation date, YYYY-MM-DD
    party_size: int
    preferred_times: list[str]     # ordered HH:MM preferences, best first
    time_window_minutes: int = 90  # accept anything within this of a preference
    table_types: Optional[list[str]] = None  # e.g. ["Dining Room"]; None = any


@dataclass
class BurstConfig:
    duration_s: float = 20.0       # how long to keep hammering /find after the drop
    interval_s: float = 0.25       # gap between /find attempts
    dry_run: bool = False          # find + rank but never call /book


def _minutes(hhmm: str) -> Optional[int]:
    try:
        h, m = hhmm.split(":")[:2]
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def rank_slots(slots: list[Slot], req: BookingRequest) -> list[Slot]:
    """Order slots by how well they match the request; drop non-matches.

    A slot is kept only if its table type is allowed (when types are
    specified) and it falls within `time_window_minutes` of some preferred
    time. Ties break toward earlier preferences and smaller time deltas.
    """
    allowed = None
    if req.table_types:
        allowed = {t.strip().lower() for t in req.table_types}

    prefs = [(_minutes(p), i) for i, p in enumerate(req.preferred_times)]
    prefs = [(m, i) for (m, i) in prefs if m is not None]

    scored: list[tuple[tuple[int, int], Slot]] = []
    for s in slots:
        if allowed is not None and s.table_type.strip().lower() not in allowed:
            continue
        slot_min = _minutes(s.hhmm)
        if slot_min is None:
            continue
        if not prefs:
            # No preference given: accept everything, order by time of day.
            scored.append(((0, slot_min), s))
            continue
        best = min(
            ((abs(slot_min - pm), pref_rank) for pm, pref_rank in prefs),
            key=lambda t: (t[0], t[1]),
        )
        delta, pref_rank = best
        if delta > req.time_window_minutes:
            continue
        # Sort key: preferred-time rank first, then closeness.
        scored.append(((pref_rank, delta), s))

    scored.sort(key=lambda t: t[0])
    return [s for _, s in scored]


class Sniper:
    def __init__(self, client: ResyClient) -> None:
        self.client = client

    def burst_find(
        self,
        req: BookingRequest,
        burst: BurstConfig,
        clock: Callable[[], float] = time.time,
    ) -> list[Slot]:
        """Poll /find repeatedly until matching slots appear or time runs out."""
        deadline = clock() + burst.duration_s
        attempt = 0
        while clock() < deadline:
            attempt += 1
            try:
                slots = self.client.find_slots(
                    req.venue_id, req.day, req.party_size
                )
            except ResyError as exc:
                log.warning("find attempt %d failed: %s", attempt, exc)
                slots = []
            ranked = rank_slots(slots, req)
            if ranked:
                log.info(
                    "Found %d matching slot(s) on attempt %d: %s",
                    len(ranked),
                    attempt,
                    ", ".join(f"{s.hhmm} {s.table_type}" for s in ranked[:5]),
                )
                return ranked
            time.sleep(burst.interval_s)
        log.info("No matching slots after %d attempts.", attempt)
        return []

    def try_book(
        self,
        ranked: list[Slot],
        req: BookingRequest,
        payment_method_id: int,
        dry_run: bool = False,
    ) -> Optional[dict[str, Any]]:
        """Walk ranked slots, booking the first one that succeeds.

        Slots can vanish between /find and /book (someone else grabbed it, or
        the book token is stale), so we fall through to the next-best slot on
        recoverable failures.
        """
        for s in ranked:
            try:
                book_token = self.client.get_book_token(
                    s.config_token, req.day, req.party_size
                )
            except ResyError as exc:
                log.warning("Couldn't get book token for %s: %s", s.hhmm, exc)
                continue

            if dry_run:
                log.info(
                    "[dry-run] Would book %s (%s). Stopping before /book.",
                    s.hhmm,
                    s.table_type,
                )
                return {"dry_run": True, "slot": s.hhmm, "table_type": s.table_type}

            try:
                result = self.client.book(book_token, payment_method_id)
            except ResyError as exc:
                log.warning("Booking %s failed, trying next slot: %s", s.hhmm, exc)
                continue

            log.info("BOOKED %s (%s). reservation=%s",
                     s.hhmm, s.table_type, result.get("reservation_id"))
            return result

        log.error("Exhausted all %d matching slot(s) without booking.", len(ranked))
        return None
