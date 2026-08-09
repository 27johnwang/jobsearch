"""Thin wrapper around Resy's (unofficial) internal booking API.

These endpoints are the ones the resy.com web app itself calls. They are not
an official public API: Resy can change or lock them down at any time, and
automating them is against Resy's Terms of Service. This module exists so you
can book *your own* table faster than clicking by hand -- not to hoard or
resell reservations.

All requests use *your* account's auth token, which you supply yourself
(see README.md for how to grab it from your browser).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

import requests

log = logging.getLogger("resy_sniper.client")

# The api_key embedded in the public resy.com web client. It identifies the
# *web app*, not you -- your identity comes from the auth token. Override via
# config if Resy rotates it.
DEFAULT_API_KEY = "VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5"

BASE = "https://api.resy.com"


class ResyError(RuntimeError):
    """Raised when the Resy API returns something we can't use."""


@dataclass
class Slot:
    """A single bookable time slot returned by /4/find."""

    config_token: str          # opaque id used to request a book token
    time_slot: str             # e.g. "2026-08-15 19:00:00"
    table_type: str            # e.g. "Dining Room", "Bar", "Patio"
    raw: dict[str, Any]

    @property
    def hhmm(self) -> str:
        """Just the HH:MM of the slot, for matching against a preferred time."""
        # time_slot looks like "2026-08-15 19:00:00"
        try:
            return self.time_slot.split(" ")[1][:5]
        except (IndexError, AttributeError):
            return ""


class ResyClient:
    def __init__(
        self,
        auth_token: str,
        api_key: str = DEFAULT_API_KEY,
        timeout: float = 7.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not auth_token:
            raise ValueError("auth_token is required (your Resy account token)")
        self.auth_token = auth_token
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(self._headers())

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f'ResyAPI api_key="{self.api_key}"',
            "X-Resy-Auth-Token": self.auth_token,
            "X-Resy-Universal-Auth": self.auth_token,
            "Origin": "https://resy.com",
            "Referer": "https://resy.com/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        }

    # -- account -----------------------------------------------------------

    def get_payment_method_id(self) -> int:
        """Return the default payment method id on your account.

        Resy requires a payment method on the booking call even when the
        reservation itself is free (it's used for no-show / cancellation
        policies).
        """
        r = self.session.get(f"{BASE}/2/user", timeout=self.timeout)
        _raise_for_status(r, "fetching your Resy profile")
        data = r.json()
        methods = data.get("payment_methods") or []
        if not methods:
            raise ResyError(
                "No payment method found on your Resy account. Add a card in "
                "the Resy app/website first -- most bookings require one."
            )
        return int(methods[0]["id"])

    # -- find --------------------------------------------------------------

    def find_slots(self, venue_id: str, day: str, party_size: int) -> list[Slot]:
        """Return all bookable slots for a venue on a given day.

        `day` is YYYY-MM-DD. Returns [] when nothing is open yet -- which is
        the normal state right up until the drop time.
        """
        params = {
            "lat": "0",
            "long": "0",
            "day": day,
            "party_size": str(party_size),
            "venue_id": str(venue_id),
        }
        r = self.session.get(f"{BASE}/4/find", params=params, timeout=self.timeout)
        _raise_for_status(r, "searching for slots")
        return self._parse_slots(r.json())

    @staticmethod
    def _parse_slots(payload: dict[str, Any]) -> list[Slot]:
        venues = (payload.get("results") or {}).get("venues") or []
        slots: list[Slot] = []
        for venue in venues:
            for s in venue.get("slots", []):
                token = (s.get("config") or {}).get("token")
                if not token:
                    continue
                slots.append(
                    Slot(
                        config_token=token,
                        time_slot=(s.get("date") or {}).get("start", ""),
                        table_type=(s.get("config") or {}).get("type", ""),
                        raw=s,
                    )
                )
        return slots

    # -- details (book token) ---------------------------------------------

    def get_book_token(self, config_token: str, day: str, party_size: int) -> str:
        """Exchange a slot's config token for a single-use book token."""
        body = {
            "commit": 1,
            "config_id": config_token,
            "day": day,
            "party_size": party_size,
        }
        r = self.session.post(
            f"{BASE}/3/details",
            json=body,
            timeout=self.timeout,
        )
        _raise_for_status(r, "requesting a book token")
        data = r.json()
        token = (data.get("book_token") or {}).get("value")
        if not token:
            raise ResyError(f"No book_token in details response: {_trunc(data)}")
        return token

    # -- book --------------------------------------------------------------

    def book(self, book_token: str, payment_method_id: int) -> dict[str, Any]:
        """Commit the booking. This is the irreversible step.

        Returns the parsed response (contains reservation_id / resy_token on
        success).
        """
        data = {
            "book_token": book_token,
            "struct_payment_method": json.dumps({"id": payment_method_id}),
            "source_id": "resy.com-venue-details",
        }
        # /3/book expects form-encoded, not JSON.
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        r = self.session.post(
            f"{BASE}/3/book",
            data=data,
            headers=headers,
            timeout=self.timeout,
        )
        # 412 = slot already taken between find and book -- a normal race loss.
        if r.status_code == 412:
            raise ResyError("Slot was taken before we could book it (412).")
        _raise_for_status(r, "booking the reservation")
        return r.json()


def _raise_for_status(r: requests.Response, action: str) -> None:
    if r.status_code >= 400:
        raise ResyError(
            f"Resy returned {r.status_code} while {action}: {_trunc(r.text)}"
        )


def _trunc(obj: Any, limit: int = 400) -> str:
    text = obj if isinstance(obj, str) else json.dumps(obj)
    return text[:limit] + ("..." if len(text) > limit else "")
