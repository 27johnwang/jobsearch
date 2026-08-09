"""Command-line entry point for the Resy reservation sniper.

Config comes from (in order of precedence): CLI flags > environment variables
> a JSON config file. Your auth token should come from an env var or the
config file, never hard-coded on the command line.

Example:
    export RESY_AUTH_TOKEN="eyJ..."
    python -m resy_sniper.cli \
        --venue-id 12345 \
        --day 2026-09-01 \
        --party-size 2 \
        --time 19:00 --time 19:30 --time 18:30 \
        --table-type "Dining Room" \
        --drop "2026-08-25 09:00:00" \
        --tz-offset -4
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Optional

from .client import DEFAULT_API_KEY, ResyClient, ResyError
from .sniper import BookingRequest, BurstConfig, Sniper
from .timing import ntp_offset, parse_target, sleep_until


def _load_config_file(path: Optional[str]) -> dict[str, Any]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _get(name: str, cli_val, cfg: dict, env: Optional[str] = None, default=None):
    if cli_val is not None:
        return cli_val
    if env and os.environ.get(env) is not None:
        return os.environ[env]
    if name in cfg:
        return cfg[name]
    return default


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="resy_sniper",
        description="Book YOUR OWN Resy reservation the instant it drops. "
        "Personal use only -- automating Resy is against their ToS, and "
        "reselling reservations is illegal in some places.",
    )
    p.add_argument("--config", help="Path to a JSON config file.")
    p.add_argument("--venue-id", help="Resy venue id (numeric).")
    p.add_argument("--day", help="Reservation date, YYYY-MM-DD.")
    p.add_argument("--party-size", type=int, help="Number of guests.")
    p.add_argument(
        "--time",
        action="append",
        dest="times",
        help="Preferred time HH:MM (repeatable, best first).",
    )
    p.add_argument(
        "--table-type",
        action="append",
        dest="table_types",
        help="Acceptable seating type, e.g. 'Dining Room' (repeatable).",
    )
    p.add_argument(
        "--window",
        type=int,
        default=None,
        help="Accept slots within N minutes of a preferred time (default 90).",
    )
    p.add_argument(
        "--drop",
        help="When slots open: 'YYYY-MM-DD HH:MM:SS'. Omit to book right now.",
    )
    p.add_argument(
        "--tz-offset",
        type=float,
        default=None,
        help="Hours offset from UTC for --drop (e.g. -4). Default: local tz.",
    )
    p.add_argument("--burst-seconds", type=float, default=None,
                   help="How long to keep retrying /find after the drop (default 20).")
    p.add_argument("--burst-interval", type=float, default=None,
                   help="Seconds between /find attempts (default 0.25).")
    p.add_argument("--api-key", default=None,
                   help=f"Resy web api_key (default: built-in {DEFAULT_API_KEY[:6]}...).")
    p.add_argument("--no-ntp", action="store_true",
                   help="Skip NTP sync; trust the system clock.")
    p.add_argument("--dry-run", action="store_true",
                   help="Find and rank slots but never call /book.")
    p.add_argument("--lead-seconds", type=float, default=1.0,
                   help="Start bursting this many seconds before the drop (default 1).")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("resy_sniper")

    cfg = _load_config_file(args.config)

    auth_token = _get("auth_token", None, cfg, env="RESY_AUTH_TOKEN")
    if not auth_token:
        log.error("Missing auth token. Set RESY_AUTH_TOKEN or put it in --config.")
        return 2

    venue_id = _get("venue_id", args.venue_id, cfg)
    day = _get("day", args.day, cfg)
    party_size = _get("party_size", args.party_size, cfg)
    times = _get("preferred_times", args.times, cfg, default=[])
    table_types = _get("table_types", args.table_types, cfg, default=None)
    window = _get("time_window_minutes", args.window, cfg, default=90)
    api_key = _get("api_key", args.api_key, cfg, env="RESY_API_KEY",
                   default=DEFAULT_API_KEY)

    missing = [k for k, v in
               {"venue-id": venue_id, "day": day, "party-size": party_size}.items()
               if not v]
    if missing:
        log.error("Missing required options: %s", ", ".join(missing))
        return 2

    req = BookingRequest(
        venue_id=str(venue_id),
        day=str(day),
        party_size=int(party_size),
        preferred_times=list(times or []),
        time_window_minutes=int(window),
        table_types=list(table_types) if table_types else None,
    )
    burst = BurstConfig(
        duration_s=float(_get("burst_seconds", args.burst_seconds, cfg, default=20.0)),
        interval_s=float(_get("burst_interval", args.burst_interval, cfg, default=0.25)),
        dry_run=args.dry_run,
    )

    client = ResyClient(auth_token=str(auth_token), api_key=str(api_key))
    sniper = Sniper(client)

    # Fetch the payment method up front so we're not doing it during the burst.
    payment_method_id = 0
    if not args.dry_run:
        try:
            payment_method_id = client.get_payment_method_id()
            log.info("Using payment method id %s.", payment_method_id)
        except ResyError as exc:
            log.error("Could not load a payment method: %s", exc)
            return 1

    offset = 0.0
    if not args.no_ntp:
        offset = ntp_offset()

    if args.drop:
        target = parse_target(args.drop, args.tz_offset)
        lead = float(args.lead_seconds)
        log.info(
            "Waiting for drop at %s (%.1fs from now, clock offset %+.3fs). "
            "Bursting %.1fs early.",
            args.drop, target - (time.time() + offset), offset, lead,
        )
        sleep_until(target - lead, offset=offset)
        log.info("Go. Bursting /find now.")

    ranked = sniper.burst_find(req, burst)
    if not ranked:
        log.error("No matching slots appeared. Nothing booked.")
        return 1

    result = sniper.try_book(
        ranked, req, payment_method_id, dry_run=args.dry_run
    )
    if result is None:
        return 1

    if args.dry_run:
        log.info("Dry run complete: %s", result)
    else:
        log.info("Success! Reservation details: %s",
                 json.dumps({k: result.get(k) for k in
                             ("reservation_id", "resy_token")}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
