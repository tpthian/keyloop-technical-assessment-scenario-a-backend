"""PostgreSQL adapters for the application ports (SPEC-001 § Execution; ADR-004, ADR-008).

``PostgresAppointmentRepository.reserve`` is the only place that reads SQLSTATE: one SAVEPOINT
per attempt, 23P01 and 40P01 become ``ResourceTaken``, anything else re-raises.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from sqlalchemy import and_, exists, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from scheduler.domain.model import (
    Appointment,
    BusyRange,
    Candidate,
    Confirmed,
    Customer,
    Dealership,
    Hours,
    NewAppointment,
    ResourceTaken,
    ServiceType,
    StoredResponse,
    Vehicle,
)
from scheduler.infrastructure.postgres.schema import (
    appointment,
    dealership,
    idempotency_key,
    opening_hours,
    service_bay,
    service_type,
    service_type_required_skill,
    technician,
    technician_skill,
)

ConnectionFactory = Callable[[], AbstractAsyncContextManager[AsyncConnection]]

_APPOINTMENT_COLUMNS = (
    appointment.c.id,
    appointment.c.dealership_id,
    appointment.c.service_type_id,
    appointment.c.bay_id,
    appointment.c.technician_id,
    appointment.c.status,
    appointment.c.start_at,
    appointment.c.end_at,
    appointment.c.customer_id,
    appointment.c.customer_email,
    appointment.c.customer_name,
    appointment.c.vehicle_id,
    appointment.c.vin,
    appointment.c.make,
    appointment.c.model,
)


def row_of(new: NewAppointment, candidate: Candidate) -> dict[str, Any]:
    """The INSERT values for one attempt; ``vehicle_key`` is the domain's identity (ADR-008)."""
    return {
        "dealership_id": new.dealership_id,
        "bay_id": candidate.bay_id,
        "technician_id": candidate.technician_id,
        "service_type_id": new.service_type_id,
        "start_at": new.start_at,
        "end_at": new.end_at,
        "customer_id": new.customer.id,
        "customer_email": new.customer.email,
        "customer_name": new.customer.name,
        "vehicle_id": new.vehicle.id,
        "vin": new.vehicle.vin,
        "vehicle_key": new.vehicle_key,
        "make": new.vehicle.make,
        "model": new.vehicle.model,
    }


def _appointment_of(row: Any) -> Appointment:
    return Appointment(
        id=row.id,
        dealership_id=row.dealership_id,
        service_type_id=row.service_type_id,
        bay_id=row.bay_id,
        technician_id=row.technician_id,
        status=row.status,
        start_at=row.start_at,
        end_at=row.end_at,
        customer=Customer(id=row.customer_id, email=row.customer_email, name=row.customer_name),
        vehicle=Vehicle(id=row.vehicle_id, vin=row.vin, make=row.make, model=row.model),
    )


def _busy(dealership_id: int, lo: datetime, hi: datetime) -> Any:
    """Appointments of the dealership overlapping [lo, hi) (half-open, as tstzrange)."""
    return and_(
        appointment.c.dealership_id == dealership_id,
        appointment.c.start_at < hi,
        appointment.c.end_at > lo,
    )


class PostgresSchedulingReadRepository:
    """Reference data and read-only appointment queries.

    ``connect`` is ``engine.connect`` before the transaction, or a context yielding the
    transaction's own connection inside the unit of work, so one class serves both paths.
    """

    def __init__(self, connect: ConnectionFactory) -> None:
        self._connect = connect

    async def dealership(self, dealership_id: int) -> Dealership | None:
        async with self._connect() as conn:
            head = (
                await conn.execute(select(dealership).where(dealership.c.id == dealership_id))
            ).first()
            if head is None:
                return None
            rows = await conn.execute(
                select(opening_hours).where(opening_hours.c.dealership_id == dealership_id)
            )
            hours = {
                r.weekday: Hours(weekday=r.weekday, opens_at=r.opens_at, closes_at=r.closes_at)
                for r in rows
            }
        return Dealership(id=head.id, name=head.name, zone=ZoneInfo(head.timezone), hours=hours)

    async def service_type(self, service_type_id: int) -> ServiceType | None:
        async with self._connect() as conn:
            row = (
                await conn.execute(select(service_type).where(service_type.c.id == service_type_id))
            ).first()
        if row is None:
            return None
        return ServiceType(id=row.id, name=row.name, duration_minutes=row.duration_minutes)

    async def qualified_technicians(self, dealership_id: int, service_type_id: int) -> list[int]:
        """Technicians of the dealership holding every required skill (ADR-006).

        Double NOT EXISTS: no required skill without a matching technician_skill row, so a
        service type with zero required skills qualifies every technician.
        """
        missing_skill = (
            select(service_type_required_skill.c.skill_id)
            .where(service_type_required_skill.c.service_type_id == service_type_id)
            .where(
                ~exists()
                .where(
                    and_(
                        technician_skill.c.technician_id == technician.c.id,
                        technician_skill.c.skill_id == service_type_required_skill.c.skill_id,
                    )
                )
                .correlate(technician, service_type_required_skill)  # both from outer queries
            )
        )
        stmt = (
            select(technician.c.id)
            .where(technician.c.dealership_id == dealership_id)
            .where(~exists(missing_skill))
            .order_by(technician.c.id)
        )
        async with self._connect() as conn:
            return [int(r[0]) for r in await conn.execute(stmt)]

    async def bays(self, dealership_id: int) -> list[int]:
        stmt = (
            select(service_bay.c.id)
            .where(service_bay.c.dealership_id == dealership_id)
            .order_by(service_bay.c.id)
        )
        async with self._connect() as conn:
            return [int(r[0]) for r in await conn.execute(stmt)]

    async def appointment(self, dealership_id: int, appointment_id: int) -> Appointment | None:
        stmt = select(*_APPOINTMENT_COLUMNS).where(
            appointment.c.id == appointment_id, appointment.c.dealership_id == dealership_id
        )
        async with self._connect() as conn:
            row = (await conn.execute(stmt)).first()
        return None if row is None else _appointment_of(row)

    async def busy_ranges(self, dealership_id: int, lo: datetime, hi: datetime) -> list[BusyRange]:
        stmt = (
            select(
                appointment.c.bay_id,
                appointment.c.technician_id,
                appointment.c.start_at,
                appointment.c.end_at,
            )
            .where(_busy(dealership_id, lo, hi))
            .order_by(appointment.c.start_at, appointment.c.id)
        )
        async with self._connect() as conn:
            return [
                BusyRange(
                    bay_id=r.bay_id,
                    technician_id=r.technician_id,
                    start_at=r.start_at,
                    end_at=r.end_at,
                )
                for r in await conn.execute(stmt)
            ]

    async def watermark(self) -> datetime:
        """Read freshness: replay timestamp on a replica, ``now()`` on a primary (ADR-010)."""
        async with self._connect() as conn:
            value = (
                await conn.execute(text("SELECT coalesce(pg_last_xact_replay_timestamp(), now())"))
            ).scalar_one()
        assert isinstance(value, datetime)
        return value


class PostgresAppointmentRepository:
    """Write side, bound to the unit of work's connection."""

    def __init__(self, conn: AsyncConnection) -> None:
        self.conn = conn

    async def free_candidates(
        self, dealership_id: int, qualified: list[int], start: datetime, end: datetime
    ) -> list[Candidate]:
        """Cross product of free bays and free qualified technicians for [start, end)."""
        if not qualified:
            return []
        bay_busy = exists().where(
            and_(_busy(dealership_id, start, end), appointment.c.bay_id == service_bay.c.id)
        )
        free_bays = (
            select(service_bay.c.id)
            .where(service_bay.c.dealership_id == dealership_id, ~bay_busy)
            .order_by(service_bay.c.id)
        )
        tech_busy = exists().where(
            and_(
                _busy(dealership_id, start, end),
                appointment.c.technician_id == technician.c.id,
            )
        )
        free_techs = (
            select(technician.c.id)
            .where(technician.c.id.in_(qualified), ~tech_busy)
            .order_by(technician.c.id)
        )
        bays = [int(r[0]) for r in await self.conn.execute(free_bays)]
        techs = [int(r[0]) for r in await self.conn.execute(free_techs)]
        return [Candidate(bay_id=b, technician_id=t) for b in bays for t in techs]

    async def reserve(self, new: NewAppointment, candidate: Candidate) -> Confirmed | ResourceTaken:
        stmt = insert(appointment).values(**row_of(new, candidate)).returning(appointment.c.id)
        try:
            async with self.conn.begin_nested():  # SAVEPOINT; rolled back on exception
                appointment_id = (await self.conn.execute(stmt)).scalar_one()
        except DBAPIError as e:
            orig = e.orig
            if isinstance(orig, psycopg.Error):
                if orig.sqlstate == "23P01":
                    return ResourceTaken(orig.diag.constraint_name, deadlock=False)
                if orig.sqlstate == "40P01":
                    return ResourceTaken(None, deadlock=True)
            raise  # anything else is a 5xx, never "next pair"
        return Confirmed(int(appointment_id))

    async def by_id(self, appointment_id: int) -> Appointment:
        stmt = select(*_APPOINTMENT_COLUMNS).where(appointment.c.id == appointment_id)
        return _appointment_of((await self.conn.execute(stmt)).one())


class PostgresIdempotencyRepository:
    """Key claim and outcome record inside the booking transaction (ADR-008)."""

    def __init__(self, conn: AsyncConnection) -> None:
        self.conn = conn

    async def claim(
        self, dealership_id: int, key: UUID, request_hash: str
    ) -> StoredResponse | None:
        stmt = (
            insert(idempotency_key)
            .values(dealership_id=dealership_id, key=key, request_hash=request_hash)
            .on_conflict_do_nothing(index_elements=["dealership_id", "key"])
            .returning(idempotency_key.c.key)
        )
        if (await self.conn.execute(stmt)).first() is not None:
            return None  # claimed now; nothing stored yet
        row = (
            await self.conn.execute(
                select(
                    idempotency_key.c.request_hash,
                    idempotency_key.c.response_code,
                    idempotency_key.c.response_body,
                ).where(
                    idempotency_key.c.dealership_id == dealership_id, idempotency_key.c.key == key
                )
            )
        ).one()
        return StoredResponse(
            request_hash=row.request_hash, code=row.response_code, body=row.response_body
        )

    async def record(
        self, dealership_id: int, key: UUID, code: str, body: Mapping[str, object]
    ) -> None:
        await self.conn.execute(
            update(idempotency_key)
            .where(idempotency_key.c.dealership_id == dealership_id, idempotency_key.c.key == key)
            .values(response_code=code, response_body=dict(body))
        )


__all__ = [
    "ConnectionFactory",
    "PostgresAppointmentRepository",
    "PostgresIdempotencyRepository",
    "PostgresSchedulingReadRepository",
    "func",
    "row_of",
]
