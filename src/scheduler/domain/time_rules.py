"""Time rules of ADR-009 (design §3).

Wall time is used only for the client's input and the opening-hours check; every instant the
system compares or stores is aware UTC, and durations are elapsed time added in UTC.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from scheduler.domain.errors import GapTime, NoOpeningInstant
from scheduler.domain.model import Dealership, Hours

HORIZON = timedelta(days=90)
PICKUP_WALK_DAYS = 14


def _require_naive(naive: datetime) -> None:
    if naive.tzinfo is not None:
        raise ValueError("expected a naive local wall time, got an aware datetime")


def _require_aware(instant: datetime) -> None:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("expected an aware datetime, got a naive one")


def canonical_utc(naive: datetime, zone: ZoneInfo) -> datetime:
    """The deterministic UTC instant of a wall time, defined for every wall time.

    ``fold=0`` always: a repeated time maps to its first occurrence and a gap time maps to the
    instant given by the pre-transition offset. Used by the canonical hash, which must be
    defined before the gap check runs (ADR-008).
    """
    _require_naive(naive)
    return naive.replace(tzinfo=zone, fold=0).astimezone(UTC)


def local_to_utc(naive: datetime, zone: ZoneInfo) -> datetime:
    """Convert the client's wall time to UTC; raise ``GapTime`` for a time that does not exist.

    A wall time exists iff converting to UTC and back gives the same wall time. A repeated time
    takes the first occurrence (ADR-009).
    """
    instant = canonical_utc(naive, zone)
    if instant.astimezone(zone).replace(tzinfo=None) != naive.replace(fold=0):
        raise GapTime(f"{naive.isoformat()} does not exist in {zone.key}")
    return instant


def start_in_hours(naive: datetime, dealership: Dealership) -> bool:
    """``opens_at <= t < closes_at`` on the local weekday of the wall time as sent (ADR-009)."""
    _require_naive(naive)
    hours = dealership.hours.get(naive.weekday())
    if hours is None:
        return False
    return hours.opens_at <= naive.time() < hours.closes_at


def end_at(start_utc: datetime, duration_minutes: int) -> datetime:
    """Elapsed end: the start as a UTC instant plus the duration (ADR-009).

    The start is normalised to UTC first, because ``+ timedelta`` on a ``ZoneInfo`` datetime is
    wall-time arithmetic and would be wrong across a DST change.
    """
    _require_aware(start_utc)
    return start_utc.astimezone(UTC) + timedelta(minutes=duration_minutes)


def day_window_utc(day: date, hours: Hours, zone: ZoneInfo) -> tuple[datetime, datetime]:
    """The ``[opens, closes)`` instants of one local day's opening hours, in UTC."""
    opens = canonical_utc(datetime.combine(day, hours.opens_at), zone)
    closes = canonical_utc(datetime.combine(day, hours.closes_at), zone)
    return opens, closes


def pickup_from(end_utc: datetime, dealership: Dealership) -> datetime:
    """The first opening instant at or after ``end_utc`` (ADR-009), in UTC.

    Opening instants are ``[opens, closes)`` of each local day with an hours row, so an end
    exactly at closing time picks up at the next opening. Walks local dates starting at the
    end's local date, skipping days with no row, for at most ``PICKUP_WALK_DAYS`` days;
    raises ``NoOpeningInstant`` after.
    """
    _require_aware(end_utc)
    end = end_utc.astimezone(UTC)
    first_day = end.astimezone(dealership.zone).date()
    for offset in range(PICKUP_WALK_DAYS):
        day = first_day + timedelta(days=offset)
        hours = dealership.hours.get(day.weekday())
        if hours is None:
            continue
        opens, closes = day_window_utc(day, hours, dealership.zone)
        if end < closes:
            return max(end, opens)
    raise NoOpeningInstant(
        f"no opening instant within {PICKUP_WALK_DAYS} days of {end.isoformat()}"
    )
