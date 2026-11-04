"""TC-08: window arithmetic (AC-06, ADR-010). Pure domain; no database.

One test function per TC-08 clause: merge of overlapping busy ranges; free gaps; duration
subtracted on UTC before intersecting the local day; closing bound ``closes - 1 min``.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from scheduler.domain.windows import Dealership, Hours, Window, free, merge, start_windows

UTC = dt.UTC
LONG_AGO = dt.datetime(2000, 1, 1, tzinfo=UTC)


def z(month: int, day: int, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(2027, month, day, hour, minute, tzinfo=UTC)


def london_mon_sat() -> Dealership:
    """ADR-010 dealership: Europe/London, 08:00-18:00 Monday to Saturday, Sunday closed."""
    hours = {wd: Hours(wd, dt.time(8), dt.time(18)) for wd in range(6)}
    return Dealership(id=1, name="Riverside Motors", zone=ZoneInfo("Europe/London"), hours=hours)


def one_pair_windows(
    day: dt.date, duration: dt.timedelta, busy: list[tuple[dt.datetime, dt.datetime]]
) -> list[Window]:
    """Windows of bay 1 / technician 1 on one day; ``busy`` is on the bay."""
    return start_windows(london_mon_sat(), [day], duration, {1: busy}, {1: []}, [1], [1], LONG_AGO)


def test_merge_of_overlapping_busy_ranges() -> None:
    ranges = [
        (z(3, 1, 14), z(3, 1, 15)),
        (z(3, 1, 9), z(3, 1, 11)),
        (z(3, 1, 10), z(3, 1, 12)),  # overlaps 09-11
        (z(3, 1, 12), z(3, 1, 13)),  # touches 12:00, half-open ranges join
        (z(3, 1, 9, 30), z(3, 1, 10)),  # contained
    ]
    assert merge(ranges) == [(z(3, 1, 9), z(3, 1, 13)), (z(3, 1, 14), z(3, 1, 15))]


def test_free_gaps() -> None:
    busy = [
        (z(3, 1, 6), z(3, 1, 9)),  # starts before lo
        (z(3, 1, 11), z(3, 1, 12)),
        (z(3, 1, 12), z(3, 1, 13)),  # back to back: no zero-length gap
        (z(3, 1, 17), z(3, 1, 20)),  # ends after hi
    ]
    assert free(busy, z(3, 1, 8), z(3, 1, 18)) == [
        (z(3, 1, 9), z(3, 1, 11)),
        (z(3, 1, 13), z(3, 1, 17)),
    ]


def test_duration_subtracted_on_utc_before_intersecting_local_day() -> None:
    """ADR-010: free Fri 2027-03-26 09:00Z to Mon 12:00 BST (11:00Z), 72 h, clocks forward on
    Sunday. UTC: 11:00Z - 72 h = Fri 11:00Z. Wall-time subtraction would give Fri 12:00 GMT,
    and an 11:30 start would end 12:30 BST, overlapping the next appointment."""
    friday = dt.date(2027, 3, 26)
    windows = one_pair_windows(
        friday,
        dt.timedelta(minutes=4320),
        [(z(3, 26, 6), z(3, 26, 9)), (z(3, 29, 11), z(3, 29, 13))],
    )
    assert windows == [Window(1, 1, friday, z(3, 26, 9), z(3, 26, 11))]


def test_closing_bound_closes_minus_one_minute() -> None:
    """Opening hours 08:00-18:00 GMT; starts are whole minutes and must be before closing."""
    monday = dt.date(2027, 3, 1)
    hour = dt.timedelta(minutes=60)
    assert one_pair_windows(monday, hour, []) == [Window(1, 1, monday, z(3, 1, 8), z(3, 1, 17, 59))]
    # free_end - duration == closes exactly: still capped at closes - 1 min
    assert one_pair_windows(monday, hour, [(z(3, 1, 19), z(3, 1, 20))]) == [
        Window(1, 1, monday, z(3, 1, 8), z(3, 1, 17, 59))
    ]
