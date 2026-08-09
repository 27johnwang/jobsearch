"""resy_sniper -- book your own Resy reservation the instant it opens.

Personal-use automation only. See README.md for the ethical/legal boundaries.
"""

from .client import ResyClient, ResyError, Slot
from .sniper import BookingRequest, BurstConfig, Sniper, rank_slots
from .timing import ntp_offset, parse_target, sleep_until

__all__ = [
    "ResyClient",
    "ResyError",
    "Slot",
    "BookingRequest",
    "BurstConfig",
    "Sniper",
    "rank_slots",
    "ntp_offset",
    "parse_target",
    "sleep_until",
]
