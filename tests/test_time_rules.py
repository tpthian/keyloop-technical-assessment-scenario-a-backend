"""TC-03 to TC-06: time rules of ADR-009 (domain, pure). One test per TC clause.

Europe/London 2027: clocks go forward Sun 28 Mar at 01:00 GMT (01:00-01:59 local does not
exist) and back Sun 31 Oct at 02:00 BST (01:00-01:59 local happens twice).
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import pytest

from scheduler.domain.errors import GapTime
from scheduler.domain.model import Dealership, Hours
from scheduler.domain.time_rules import end_at, local_to_utc, pickup_from, start_in_hours

LONDON = ZoneInfo("Europe/London")

# Seed shape of dealership 1 (T3): London, Mon-Sat 08:00-18:00, Sunday closed.
RIVERSIDE = Dealership(
    id=1,
    name="Riverside Motors",
    zone=LONDON,
    hours={d: Hours(weekday=d, opens_at=time(8), closes_at=time(18)) for d in range(6)},
)


def utc(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


# TC-03 local_to_utc


def test_tc03_gap_time_raises() -> None:
    with pytest.raises(GapTime):
        local_to_utc(datetime(2027, 3, 28, 1, 30), LONDON)


def test_tc03_repeated_time_takes_first_occurrence() -> None:
    assert local_to_utc(datetime(2027, 10, 31, 1, 30), LONDON) == utc(2027, 10, 31, 0, 30)


def test_tc03_ordinary_time_converts() -> None:
    result = local_to_utc(datetime(2027, 6, 1, 9, 0), LONDON)  # BST
    assert result == utc(2027, 6, 1, 8, 0)
    assert result.tzinfo is UTC


# TC-04 start_in_hours (Friday 2027-03-26, Sunday 2027-03-28)


def test_tc04_at_opens_at_is_in_hours() -> None:
    assert start_in_hours(datetime(2027, 3, 26, 8, 0), RIVERSIDE) is True


def test_tc04_at_closes_at_is_not_in_hours() -> None:
    assert start_in_hours(datetime(2027, 3, 26, 18, 0), RIVERSIDE) is False


def test_tc04_missing_weekday_is_not_in_hours() -> None:
    assert start_in_hours(datetime(2027, 3, 28, 9, 0), RIVERSIDE) is False


# TC-05 end_at


def test_tc05_multi_day_service_across_dst_is_elapsed() -> None:
    end = end_at(local_to_utc(datetime(2027, 3, 26, 9, 0), LONDON), 4320)
    assert end == utc(2027, 3, 29, 9, 0)
    assert end.astimezone(LONDON).replace(tzinfo=None) == datetime(2027, 3, 29, 10, 0)  # BST


# TC-06 pickup_from


def test_tc06_end_inside_hours_is_end() -> None:
    end = utc(2027, 3, 26, 10, 0)  # Fri 10:00 GMT
    assert pickup_from(end, RIVERSIDE) == end


def test_tc06_after_close_is_next_days_open() -> None:
    # Fri 18:30 GMT -> Sat 08:00 GMT
    assert pickup_from(utc(2027, 3, 26, 18, 30), RIVERSIDE) == utc(2027, 3, 27, 8, 0)


def test_tc06_saturday_evening_sunday_closed_is_monday_open() -> None:
    # Sat 19:00 GMT; Sunday closed; Monday 08:00 BST = 07:00Z
    assert pickup_from(utc(2027, 3, 27, 19, 0), RIVERSIDE) == utc(2027, 3, 29, 7, 0)
