"""Clock synchronisation and a precise sleep-until-target helper.

The whole game is firing the first /find request the instant the slots drop.
Your machine's clock can easily be off by a second or more, which is an
eternity here, so we optionally sync against an NTP server once at startup and
then spin-wait the last few milliseconds for accuracy.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

log = logging.getLogger("resy_sniper.timing")


def ntp_offset(server: str = "pool.ntp.org", timeout: float = 5.0) -> float:
    """Return (true_time - local_time) in seconds using NTP.

    Positive means the local clock is *behind*. Falls back to 0.0 (with a
    warning) if ntplib isn't installed or the server can't be reached, so the
    tool still runs on the system clock.
    """
    try:
        import ntplib  # optional dependency
    except ImportError:
        log.warning("ntplib not installed; using system clock (pip install ntplib).")
        return 0.0
    try:
        resp = ntplib.NTPClient().request(server, version=3, timeout=timeout)
        log.info("NTP offset vs %s: %+.3f s", server, resp.offset)
        return float(resp.offset)
    except Exception as exc:  # network flakiness shouldn't kill the run
        log.warning("NTP sync failed (%s); using system clock.", exc)
        return 0.0


def sleep_until(target_epoch: float, offset: float = 0.0, spin_ms: float = 40.0) -> None:
    """Block until `target_epoch` (a Unix timestamp) accounting for `offset`.

    Coarse-sleeps until ~`spin_ms` before the target, then busy-waits for
    sub-millisecond precision on the final approach.
    """
    def now() -> float:
        return time.time() + offset

    spin_s = spin_ms / 1000.0
    coarse_wake = target_epoch - spin_s
    remaining = coarse_wake - now()
    if remaining > 0:
        time.sleep(remaining)
    # Tight spin for the last few ms.
    while now() < target_epoch:
        pass


def parse_target(target: str, tz_offset_hours: float | None = None) -> float:
    """Parse a 'YYYY-MM-DD HH:MM:SS' local drop time into a Unix timestamp.

    If `tz_offset_hours` is given (e.g. -4 for US Eastern in summer), the time
    is interpreted in that timezone; otherwise the machine's local timezone is
    used.
    """
    dt = datetime.strptime(target, "%Y-%m-%d %H:%M:%S")
    if tz_offset_hours is None:
        return dt.timestamp()  # local tz
    tz = timezone(_hours(tz_offset_hours))
    return dt.replace(tzinfo=tz).timestamp()


def _hours(h: float):
    from datetime import timedelta

    return timedelta(hours=h)
