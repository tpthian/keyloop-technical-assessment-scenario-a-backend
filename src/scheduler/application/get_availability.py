"""``GetAvailability``: advisory start windows of one service type (ADR-010, SPEC-001 Interfaces).

The answer carries no guarantee; the booking attempt is authoritative (ADR-010). ``as_of`` is
the read watermark, taken before the busy ranges are read, so every commit up to ``as_of`` is
reflected and later commits may be missing.

Days are the local calendar days of ``[from_date, to_date)`` in the dealership zone. Window
bounds are inclusive whole-minute UTC instants; a window bounded by closing time ends at
``closes - 1 min`` (D-041 item 2). The arithmetic lives in ``domain/windows.py``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta

from scheduler.application.ports import Clock, SchedulingReadRepository
from scheduler.domain.errors import NotFound, ValidationFailed
from scheduler.domain.model import Dealership, ServiceType
from scheduler.domain.time_rules import HORIZON, day_window_utc
from scheduler.domain.windows import Interval, Window, start_windows

MAX_SPAN = timedelta(days=14)


def _utc(instant: datetime) -> str:
    return instant.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _window_body(w: Window) -> dict[str, object]:
    return {
        "bay_id": w.bay_id,
        "technician_id": w.technician_id,
        "date": w.date.isoformat(),
        "earliest_start": _utc(w.earliest_start),
        "latest_start": _utc(w.latest_start),
    }


class GetAvailability:
    def __init__(self, reads: SchedulingReadRepository, clock: Clock) -> None:
        self.reads = reads
        self.clock = clock

    async def execute(
        self, dealership_id: int, service_type_id: int, from_date: date, to_date: date
    ) -> Mapping[str, object]:
        """The availability body (SPEC-001 Wire formats).

        ``NotFound`` for an unknown dealership; ``ValidationFailed`` for ``to <= from``, a span
        over 14 days, ``from`` before today in the dealership zone, ``to`` beyond
        today + ``HORIZON``, or an unknown service type, checked in that order.
        """
        dealership = await self.reads.dealership(dealership_id)
        if dealership is None:
            raise NotFound("dealership")
        now = self.clock.now()
        service = await self._validate(dealership, service_type_id, from_date, to_date, now)
        as_of = await self.reads.watermark()  # before the busy read: see module docstring
        bays = await self.reads.bays(dealership_id)
        techs = await self.reads.qualified_technicians(dealership_id, service_type_id)
        duration = timedelta(minutes=service.duration_minutes)
        days = [from_date + timedelta(days=i) for i in range((to_date - from_date).days)]
        windows = await self._windows(dealership, days, duration, bays, techs, now)
        return {
            "dealership_id": dealership_id,
            "service_type_id": service_type_id,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "as_of": _utc(as_of),
            "windows": [_window_body(w) for w in windows],
        }

    async def _validate(
        self,
        dealership: Dealership,
        service_type_id: int,
        from_date: date,
        to_date: date,
        now: datetime,
    ) -> ServiceType:
        if to_date <= from_date:
            raise ValidationFailed("to must be after from")
        if to_date - from_date > MAX_SPAN:
            raise ValidationFailed(f"from to to spans more than {MAX_SPAN.days} days")
        today = now.astimezone(dealership.zone).date()
        if from_date < today:
            raise ValidationFailed("from is in the past")
        if to_date > today + HORIZON:
            raise ValidationFailed(f"to is more than {HORIZON.days} days ahead")
        service = await self.reads.service_type(service_type_id)
        if service is None:
            raise ValidationFailed(f"service type {service_type_id} does not exist")
        return service

    async def _windows(
        self,
        dealership: Dealership,
        days: list[date],
        duration: timedelta,
        bays: list[int],
        techs: list[int],
        now: datetime,
    ) -> list[Window]:
        """Busy ranges over ``[first opens, last closes + duration)``, then the arithmetic.

        That is the range ``start_windows`` needs covered; no open day, no bay or no qualified
        technician means no window and no busy read.
        """
        open_days = [
            day_window_utc(d, dealership.hours[d.weekday()], dealership.zone)
            for d in days
            if d.weekday() in dealership.hours
        ]
        if not open_days or not bays or not techs:
            return []
        lo, hi = open_days[0][0], open_days[-1][1]
        busy_by_bay: defaultdict[int, list[Interval]] = defaultdict(list)
        busy_by_tech: defaultdict[int, list[Interval]] = defaultdict(list)
        for r in await self.reads.busy_ranges(dealership.id, lo, hi + duration):
            busy_by_bay[r.bay_id].append((r.start_at, r.end_at))
            busy_by_tech[r.technician_id].append((r.start_at, r.end_at))
        return start_windows(
            dealership, days, duration, busy_by_bay, busy_by_tech, bays, techs, now
        )
