"""TC-08: window arithmetic (AC-06, ADR-010). Pure domain; no database.

Edge and regression first: merge, free gaps, the DST cases where wall-time subtraction would
advertise refused starts, the closing bound ``closes - 1 min``, the "now" cut; the ADR-010 worked
example last.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from scheduler.domain.windows import (
    Dealership,
    Hours,
    Window,
    free,
    merge,
    start_windows,
)

UTC = dt.UTC
LONDON = ZoneInfo("Europe/London")
H72 = dt.timedelta(minutes=4320)
H1 = dt.timedelta(minutes=60)
LONG_AGO = dt.datetime(2000, 1, 1, tzinfo=UTC)


def z(month: int, day: int, hour: int, minute: int = 0, year: int = 2027) -> dt.datetime:
    return dt.datetime(year, month, day, hour, minute, tzinfo=UTC)


def london_mon_sat() -> Dealership:
    """ADR-010 dealership: Europe/London, 08:00-18:00 Monday to Saturday, Sunday closed."""
    hours = {wd: Hours(wd, dt.time(8), dt.time(18)) for wd in range(6)}
    return Dealership(id=1, name="Riverside Motors", zone=LONDON, hours=hours)


def one_pair(
    days: list[dt.date],
    duration: dt.timedelta,
    bay_busy: list[tuple[dt.datetime, dt.datetime]] | None = None,
    tech_busy: list[tuple[dt.datetime, dt.datetime]] | None = None,
    now: dt.datetime = LONG_AGO,
    dealership: Dealership | None = None,
) -> list[Window]:
    return start_windows(
        dealership or london_mon_sat(),
        days,
        duration,
        {1: bay_busy or []},
        {1: tech_busy or []},
        [1],
        [1],
        now,
    )


def spans(windows: list[Window]) -> list[tuple[dt.date, dt.datetime, dt.datetime]]:
    return [(w.date, w.earliest_start, w.latest_start) for w in windows]


# --- merge -------------------------------------------------------------------------------------


def test_merge_joins_overlapping_touching_and_contained_ranges_in_any_order() -> None:
    ranges = [
        (z(3, 1, 14), z(3, 1, 15)),
        (z(3, 1, 9), z(3, 1, 11)),
        (z(3, 1, 10), z(3, 1, 12)),  # overlaps the 09-11 range
        (z(3, 1, 12), z(3, 1, 13)),  # touches 12:00, joins
        (z(3, 1, 9, 30), z(3, 1, 10)),  # contained
    ]
    assert merge(ranges) == [(z(3, 1, 9), z(3, 1, 13)), (z(3, 1, 14), z(3, 1, 15))]


def test_merge_drops_empty_and_inverted_ranges() -> None:
    assert merge([(z(3, 1, 9), z(3, 1, 9)), (z(3, 1, 11), z(3, 1, 10))]) == []
    assert merge([]) == []


# --- free --------------------------------------------------------------------------------------


def test_free_returns_gaps_between_busy_ranges_clipped_to_bounds() -> None:
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


def test_free_without_busy_is_the_whole_bound_and_fully_busy_is_empty() -> None:
    assert free([], z(3, 1, 8), z(3, 1, 18)) == [(z(3, 1, 8), z(3, 1, 18))]
    assert free([(z(3, 1, 7), z(3, 1, 19))], z(3, 1, 8), z(3, 1, 18)) == []


def test_free_ignores_busy_ranges_outside_the_bound() -> None:
    busy = [(z(3, 1, 1), z(3, 1, 2)), (z(3, 1, 20), z(3, 1, 21))]
    assert free(busy, z(3, 1, 8), z(3, 1, 18)) == [(z(3, 1, 8), z(3, 1, 18))]


# --- duration subtracted on UTC instants (DST) -------------------------------------------------


def test_spring_forward_duration_subtracted_on_utc_not_wall_time() -> None:
    """ADR-010 'Rejected: wall-time subtraction'. Free Fri 09:00Z to Mon 12:00 BST (11:00Z).
    UTC: 11:00Z - 72 h = Fri 11:00Z. Wall time would give Fri 12:00, and an 11:30 GMT start would
    end 12:30 BST, overlapping the next appointment."""
    friday = dt.date(2027, 3, 26)
    windows = one_pair(
        [friday], H72, bay_busy=[(z(3, 26, 7), z(3, 26, 9)), (z(3, 29, 11), z(3, 29, 13))]
    )
    assert spans(windows) == [(friday, z(3, 26, 9), z(3, 26, 11))]
    latest = windows[0].latest_start
    assert latest + H72 == z(3, 29, 11)  # ends exactly as the next range begins (half-open)


def test_fall_back_duration_subtracted_on_utc_not_wall_time() -> None:
    """Clocks go back Sun 2027-10-31 01:00Z. Busy from Mon 1 Nov 12:00 GMT (12:00Z). UTC:
    12:00Z - 72 h = Fri 29 Oct 12:00Z = 13:00 BST. Wall time would give Fri 12:00 BST and hide
    a bookable hour."""
    friday = dt.date(2027, 10, 29)
    windows = one_pair([friday], H72, bay_busy=[(z(11, 1, 12), z(11, 1, 14))])
    # Friday opens 08:00 BST = 07:00Z.
    assert spans(windows) == [(friday, z(10, 29, 7), z(10, 29, 12))]


def test_local_day_window_follows_the_zone_offset_each_side_of_the_change() -> None:
    """Sat 27 Mar is GMT (08:00Z-17:59Z); Mon 29 Mar is BST (07:00Z-16:59Z); Sun closed."""
    days = [dt.date(2027, 3, 27), dt.date(2027, 3, 28), dt.date(2027, 3, 29)]
    assert spans(one_pair(days, H1)) == [
        (dt.date(2027, 3, 27), z(3, 27, 8), z(3, 27, 17, 59)),
        (dt.date(2027, 3, 29), z(3, 29, 7), z(3, 29, 16, 59)),
    ]


# --- closing bound: closes - 1 min ------------------------------------------------------------


def test_closing_bound_is_closes_minus_one_minute_when_free_runs_past_close() -> None:
    monday = dt.date(2027, 3, 1)  # GMT
    assert spans(one_pair([monday], H1)) == [(monday, z(3, 1, 8), z(3, 1, 17, 59))]


def test_closing_bound_caps_even_when_free_end_minus_duration_equals_closes() -> None:
    """Free until exactly closes + duration: free_end - duration == closes, which is not a
    bookable start (opens <= t < closes); latest start is closes - 1 min."""
    monday = dt.date(2027, 3, 1)
    windows = one_pair([monday], H1, bay_busy=[(z(3, 1, 19), z(3, 1, 20))])
    assert spans(windows) == [(monday, z(3, 1, 8), z(3, 1, 17, 59))]


def test_free_end_minus_duration_wins_when_it_is_before_the_closing_bound() -> None:
    monday = dt.date(2027, 3, 1)
    windows = one_pair([monday], H1, bay_busy=[(z(3, 1, 18), z(3, 1, 19))])
    assert spans(windows) == [(monday, z(3, 1, 8), z(3, 1, 17))]
    windows = one_pair([monday], H1, bay_busy=[(z(3, 1, 18, 59), z(3, 1, 19))])
    assert spans(windows) == [(monday, z(3, 1, 8), z(3, 1, 17, 59))]


def test_start_one_minute_before_close_is_offered_and_close_is_not() -> None:
    monday = dt.date(2027, 3, 1)
    windows = one_pair([monday], H1, bay_busy=[(z(3, 1, 8), z(3, 1, 17, 59))])
    assert spans(windows) == [(monday, z(3, 1, 17, 59), z(3, 1, 17, 59))]
    windows = one_pair([monday], H1, bay_busy=[(z(3, 1, 8), z(3, 1, 18))])
    assert windows == []


# --- gaps, exact fits, resources --------------------------------------------------------------


def test_exact_fit_gap_gives_a_single_instant_window_and_one_minute_short_gives_none() -> None:
    monday = dt.date(2027, 3, 1)
    busy = [(z(3, 1, 8), z(3, 1, 9)), (z(3, 1, 10), z(3, 1, 20))]
    assert spans(one_pair([monday], H1, bay_busy=busy)) == [(monday, z(3, 1, 9), z(3, 1, 9))]
    assert one_pair([monday], H1 + dt.timedelta(minutes=1), bay_busy=busy) == []


def test_several_gaps_on_one_day_give_several_windows_in_order() -> None:
    monday = dt.date(2027, 3, 1)
    busy = [(z(3, 1, 10), z(3, 1, 11)), (z(3, 1, 13), z(3, 1, 14))]
    assert spans(one_pair([monday], H1, bay_busy=busy)) == [
        (monday, z(3, 1, 8), z(3, 1, 9)),
        (monday, z(3, 1, 11), z(3, 1, 12)),
        (monday, z(3, 1, 14), z(3, 1, 17, 59)),
    ]


def test_bay_and_technician_busy_ranges_are_unioned_per_pair() -> None:
    monday = dt.date(2027, 3, 1)
    windows = one_pair(
        [monday],
        H1,
        bay_busy=[(z(3, 1, 8), z(3, 1, 12))],
        tech_busy=[(z(3, 1, 12), z(3, 1, 16))],  # the technician on another bay
    )
    assert spans(windows) == [(monday, z(3, 1, 16), z(3, 1, 17, 59))]


def test_every_pair_is_evaluated_and_ordered_by_date_bay_technician() -> None:
    monday, tuesday = dt.date(2027, 3, 1), dt.date(2027, 3, 2)
    windows = start_windows(
        london_mon_sat(),
        [tuesday, monday],
        H1,
        {2: [(z(3, 1, 8), z(3, 1, 20)), (z(3, 2, 8), z(3, 2, 20))]},  # bay 2 busy both days
        {1: [(z(3, 2, 8), z(3, 2, 12))]},  # technician 1 busy Tuesday morning
        [2, 1],
        [2, 1],
        LONG_AGO,
    )
    assert [(w.date, w.bay_id, w.technician_id, w.earliest_start) for w in windows] == [
        (monday, 1, 1, z(3, 1, 8)),
        (monday, 1, 2, z(3, 1, 8)),
        (tuesday, 1, 1, z(3, 2, 12)),
        (tuesday, 1, 2, z(3, 2, 8)),
    ]


def test_no_bays_or_no_technicians_give_no_windows() -> None:
    d = london_mon_sat()
    monday = dt.date(2027, 3, 1)
    assert start_windows(d, [monday], H1, {}, {}, [], [1], LONG_AGO) == []
    assert start_windows(d, [monday], H1, {}, {}, [1], [], LONG_AGO) == []


def test_closed_weekday_yields_no_window() -> None:
    sunday = dt.date(2027, 3, 7)
    assert one_pair([sunday], H1) == []


# --- earliest_now ------------------------------------------------------------------------------


def test_now_cuts_the_earliest_start_rounded_up_to_the_whole_minute() -> None:
    monday = dt.date(2027, 3, 1)
    now = dt.datetime(2027, 3, 1, 10, 15, 0, 123456, tzinfo=UTC)
    assert spans(one_pair([monday], H1, now=now)) == [(monday, z(3, 1, 10, 16), z(3, 1, 17, 59))]


def test_now_on_a_whole_minute_is_itself_a_valid_start() -> None:
    monday = dt.date(2027, 3, 1)
    assert spans(one_pair([monday], H1, now=z(3, 1, 10, 15))) == [
        (monday, z(3, 1, 10, 15), z(3, 1, 17, 59))
    ]


def test_now_after_the_last_start_of_the_day_removes_that_day() -> None:
    monday, tuesday = dt.date(2027, 3, 1), dt.date(2027, 3, 2)
    now = dt.datetime(2027, 3, 1, 17, 59, 0, 1, tzinfo=UTC)
    assert spans(one_pair([monday, tuesday], H1, now=now)) == [
        (tuesday, z(3, 2, 8), z(3, 2, 17, 59))
    ]


def test_non_positive_duration_is_rejected() -> None:
    with pytest.raises(ValueError):
        one_pair([dt.date(2027, 3, 1)], dt.timedelta(0))


# --- ADR-010 worked example (AC-06) -----------------------------------------------------------


def test_adr_010_worked_example_gives_exactly_friday_and_monday_windows() -> None:
    """London, 72 h, one pair B1/T1, E1 ending Fri 09:00Z, E2 Mon 11:00Z-13:00Z, request
    from=2027-03-26 to=2027-03-30 issued 2027-03-25T16:00Z. AC-06: Friday [09:00Z, 11:00Z],
    Monday [13:00Z, 16:59Z]; Saturday none (every start ends after E2 begins); Sunday closed."""
    e1 = (z(3, 26, 6), z(3, 26, 9))
    e2 = (z(3, 29, 11), z(3, 29, 13))
    days = [dt.date(2027, 3, 26) + dt.timedelta(days=i) for i in range(4)]
    windows = start_windows(
        london_mon_sat(),
        days,
        H72,
        {1: [e1, e2]},
        {1: [e1, e2]},
        [1],
        [1],
        z(3, 25, 16),
    )
    assert windows == [
        Window(1, 1, dt.date(2027, 3, 26), z(3, 26, 9), z(3, 26, 11)),
        Window(1, 1, dt.date(2027, 3, 29), z(3, 29, 13), z(3, 29, 16, 59)),
    ]
    for w in windows:
        assert w.earliest_start.utcoffset() == dt.timedelta(0)
        assert w.latest_start.utcoffset() == dt.timedelta(0)
