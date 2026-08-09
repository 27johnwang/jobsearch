"""Offline unit tests for the pure logic (no network needed).

Run: python -m resy_sniper.test_sniper
"""

from __future__ import annotations

from .client import ResyClient, Slot
from .sniper import BookingRequest, rank_slots
from .timing import parse_target


def _slot(hhmm: str, table_type: str = "Dining Room") -> Slot:
    return Slot(
        config_token=f"tok-{hhmm}-{table_type}",
        time_slot=f"2026-09-01 {hhmm}:00",
        table_type=table_type,
        raw={},
    )


def test_rank_prefers_ordered_times():
    req = BookingRequest(
        venue_id="1", day="2026-09-01", party_size=2,
        preferred_times=["19:00", "20:00"], time_window_minutes=90,
    )
    slots = [_slot("20:00"), _slot("19:00"), _slot("21:30")]
    ranked = rank_slots(slots, req)
    assert [s.hhmm for s in ranked] == ["19:00", "20:00", "21:30"], ranked
    # 21:30 is 90 min from 20:00 -> exactly on the window edge, kept.


def test_rank_filters_by_table_type():
    req = BookingRequest(
        venue_id="1", day="2026-09-01", party_size=2,
        preferred_times=["19:00"], time_window_minutes=120,
        table_types=["Dining Room"],
    )
    slots = [_slot("19:00", "Bar"), _slot("19:15", "Dining Room")]
    ranked = rank_slots(slots, req)
    assert [s.hhmm for s in ranked] == ["19:15"], ranked


def test_rank_drops_out_of_window():
    req = BookingRequest(
        venue_id="1", day="2026-09-01", party_size=2,
        preferred_times=["19:00"], time_window_minutes=30,
    )
    slots = [_slot("22:00"), _slot("19:20")]
    ranked = rank_slots(slots, req)
    assert [s.hhmm for s in ranked] == ["19:20"], ranked


def test_no_preference_accepts_all_ordered_by_time():
    req = BookingRequest(
        venue_id="1", day="2026-09-01", party_size=2,
        preferred_times=[], time_window_minutes=90,
    )
    slots = [_slot("21:00"), _slot("17:30"), _slot("19:00")]
    ranked = rank_slots(slots, req)
    assert [s.hhmm for s in ranked] == ["17:30", "19:00", "21:00"], ranked


def test_parse_target_with_tz_offset():
    # 2026-08-25 09:00:00 at UTC-4 == 13:00:00 UTC.
    ts = parse_target("2026-08-25 09:00:00", tz_offset_hours=-4)
    from datetime import datetime, timezone
    assert datetime.fromtimestamp(ts, timezone.utc).hour == 13


def test_parse_slots_shape():
    payload = {
        "results": {
            "venues": [
                {
                    "slots": [
                        {
                            "config": {"token": "abc", "type": "Dining Room"},
                            "date": {"start": "2026-09-01 19:00:00"},
                        },
                        {"config": {}, "date": {"start": "2026-09-01 20:00:00"}},
                    ]
                }
            ]
        }
    }
    slots = ResyClient._parse_slots(payload)
    assert len(slots) == 1
    assert slots[0].config_token == "abc"
    assert slots[0].hhmm == "19:00"


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    import sys
    sys.exit(_run())
