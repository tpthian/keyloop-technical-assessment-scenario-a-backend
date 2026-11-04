"""Start-window arithmetic for advisory availability (ADR-010).

A start window is the inclusive range ``[earliest_start, latest_start]`` of whole-minute start
instants at which a service of the given duration fits on one (bay, technician) pair without
overlapping either resource's existing appointments, and starts inside that local day's opening
hours.

Two rules carry the correctness (ADR-010, D-041 item 2):

- The duration is subtracted from the right end of a free interval on UTC instants, never on
  local wall time; wall-time subtraction across a DST change advertises starts the UTC booking
  range refuses (ADR-010 worked example).
- A window bounded by closing time ends at ``closes - 1 min``: the booking rule is
  ``opens_at <= t < closes_at`` (ADR-009) and starts are whole minutes, so the last bookable
  start is one minute before closing.

All intervals are half-open ``[start, end)`` on aware UTC instants, matching the booking range
and the exclusion constraints (ADR-004): a start that begins exactly as a busy range ends, or a
service that ends exactly as a busy range begins, is free.

Pure functions; standard library only (design §4, D-041).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from zoneinfo import ZoneInfo

Interval = tuple[dt.datetime, dt.datetime]
"""Half-open ``[start, end)`` on aware UTC instants."""

ONE_MINUTE = dt.timedelta(minutes=1)


# moved to model.py at merge (T4 owns model.py)
@dataclass(frozen=True)
class Hours:
    weekday: int  # 0 = Monday
    opens_at: dt.time
    closes_at: dt.time


# moved to model.py at merge (T4 owns model.py)
@dataclass(frozen=True)
class Dealership:
    id: int
    name: str
    zone: ZoneInfo
    hours: Mapping[int, Hours]  # missing weekday = closed


@dataclass(frozen=True)
class Window:
    """One pair's inclusive start window on one local day; both bounds aware UTC."""

    bay_id: int
    technician_id: int
    date: dt.date  # local calendar day in the dealership zone
    earliest_start: dt.datetime
    latest_start: dt.datetime


def merge(ranges: Iterable[Interval]) -> list[Interval]:
    """Union of half-open ranges, sorted, with overlapping and touching ranges joined.

    Empty or inverted ranges (``start >= end``) occupy no time and are dropped.
    """
    ordered = sorted((s, e) for s, e in ranges if s < e)
    merged: list[Interval] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            last_start, last_end = merged[-1]
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def free(busy: Iterable[Interval], lo: dt.datetime, hi: dt.datetime) -> list[Interval]:
    """The gaps of ``[lo, hi)`` not covered by ``busy``, sorted, each non-empty.

    ``busy`` need not be merged or clipped; ranges outside ``[lo, hi)`` are ignored.
    """
    gaps: list[Interval] = []
    cursor = lo
    for start, end in merge(busy):
        if end <= cursor:
            continue
        if start >= hi:
            break
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
        if cursor >= hi:
            break
    if cursor < hi:
        gaps.append((cursor, hi))
    return gaps


# replaced by time_rules.day_window_utc at merge (T4 owns time_rules.py)
def _day_window_utc(day: dt.date, hours: Hours, zone: ZoneInfo) -> Interval:
    """Opening and closing instants of a local day in UTC (wall time, first occurrence)."""
    opens = dt.datetime.combine(day, hours.opens_at, tzinfo=zone).astimezone(dt.UTC)
    closes = dt.datetime.combine(day, hours.closes_at, tzinfo=zone).astimezone(dt.UTC)
    return opens, closes


def _ceil_minute(instant: dt.datetime) -> dt.datetime:
    """The first whole-minute instant at or after ``instant`` (starts are whole minutes)."""
    floored = instant.replace(second=0, microsecond=0)
    return floored if floored == instant else floored + ONE_MINUTE


def start_windows(
    dealership: Dealership,
    days: Iterable[dt.date],
    duration: dt.timedelta,
    busy_by_bay: Mapping[int, Sequence[Interval]],
    busy_by_tech: Mapping[int, Sequence[Interval]],
    bays: Sequence[int],
    techs: Sequence[int],
    earliest_now: dt.datetime,
) -> list[Window]:
    """Start windows for every (bay, technician) pair on every open local day (ADR-010).

    For a day open ``[opens, closes)`` in UTC, the pair's free gaps are taken over
    ``[opens, closes + duration)``, the furthest any start of that day can reach. A gap
    ``[a, b)`` admits starts ``s`` with ``a <= s`` and ``s + duration <= b``, so
    ``s <= b - duration`` on UTC instants; that range is then intersected with the day's
    start range ``[opens, closes - 1 min]`` and cut at ``earliest_now`` rounded up to the
    minute (a start equal to now is not in the past, ADR-009). Each pair may get several
    windows per day; days absent from ``dealership.hours`` are closed and yield none.

    The caller must supply every busy range that intersects
    ``[first day's opens, last day's closes + duration)``; bays or technicians missing from
    the busy maps are free. ``techs`` are the technicians qualified for the service. The result
    is ordered by date, bay, technician, earliest start.
    """
    if duration <= dt.timedelta(0):
        raise ValueError("duration must be positive")
    not_before = _ceil_minute(earliest_now)
    windows: list[Window] = []
    for day in sorted(set(days)):
        hours = dealership.hours.get(day.weekday())
        if hours is None:
            continue
        opens, closes = _day_window_utc(day, hours, dealership.zone)
        last_start_of_day = closes - ONE_MINUTE
        first_start_of_day = max(opens, not_before)
        if first_start_of_day > last_start_of_day:
            continue
        for bay in sorted(bays):
            bay_busy = busy_by_bay.get(bay, ())
            for tech in sorted(techs):
                pair_busy = [*bay_busy, *busy_by_tech.get(tech, ())]
                for gap_start, gap_end in free(pair_busy, opens, closes + duration):
                    earliest = max(gap_start, first_start_of_day)
                    latest = min(gap_end - duration, last_start_of_day)
                    if earliest <= latest:
                        windows.append(Window(bay, tech, day, earliest, latest))
    return windows
