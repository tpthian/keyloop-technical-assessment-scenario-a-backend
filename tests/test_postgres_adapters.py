"""TC-12, TC-13 and the end-to-end booking against the real adapters (SPEC-001 T7).

Infrastructure layer: the savepoint and SQLSTATE boundary of ``reserve`` (ADR-004), the key claim
and record (ADR-008), the candidate query, and one real ``BookAppointment`` run.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from scheduler.application.book_appointment import BookAppointment
from scheduler.domain.model import (
    BookingCommand,
    Candidate,
    Confirmed,
    Customer,
    NewAppointment,
    ResourceTaken,
    Vehicle,
)
from scheduler.infrastructure.clock import SystemClock
from scheduler.infrastructure.postgres.repositories import PostgresSchedulingReadRepository
from scheduler.infrastructure.postgres.unit_of_work import PostgresUnitOfWork
from tests.conftest import make_dealership
from tests.fakes import FixedClock

DEALERSHIP = 100
BAYS = (101, 102)
TECHS = (103, 104)
ALL_SKILLS = [1, 2]  # seeded: general, bodywork
START = datetime(2027, 3, 29, 9, 0, tzinfo=UTC)  # a Monday
END = START + timedelta(hours=1)


def _new(vehicle_key: str, start: datetime = START, end: datetime = END) -> NewAppointment:
    return NewAppointment(
        dealership_id=DEALERSHIP,
        service_type_id=1,
        start_at=start,
        end_at=end,
        customer=Customer(id="c1", email=None, name=None),
        vehicle=Vehicle(id=None, vin=vehicle_key, make=None, model=None),
        vehicle_key=vehicle_key,
    )


async def _fixture(engine: AsyncEngine) -> None:
    await make_dealership(engine, DEALERSHIP, bays=BAYS, technicians={t: ALL_SKILLS for t in TECHS})


async def test_reserve_confirms_free_pair_and_loses_to_named_constraints(
    engine: AsyncEngine,
) -> None:
    """TC-12: Confirmed on a free pair; bay clash → ``no_bay_overlap`` and the transaction
    continues (a later INSERT in the same transaction succeeds); vehicle clash →
    ``no_vehicle_overlap``."""
    await _fixture(engine)
    async with PostgresUnitOfWork(engine) as tx:
        first = await tx.appointments.reserve(_new("VIN1"), Candidate(101, 103))
        assert isinstance(first, Confirmed)
        bay_clash = await tx.appointments.reserve(_new("VIN2"), Candidate(101, 104))
        assert bay_clash == ResourceTaken("no_bay_overlap", deadlock=False)
        vehicle_clash = await tx.appointments.reserve(_new("VIN1"), Candidate(102, 104))
        assert vehicle_clash == ResourceTaken("no_vehicle_overlap", deadlock=False)
        second = await tx.appointments.reserve(_new("VIN2"), Candidate(102, 104))
        assert isinstance(second, Confirmed)  # savepoint scope: the transaction survived losses
    async with engine.connect() as conn:
        count = (
            await conn.execute(
                text("SELECT count(*) FROM appointment WHERE dealership_id = :d"), {"d": DEALERSHIP}
            )
        ).scalar_one()
    assert count == 2


async def test_reserve_reraises_non_constraint_errors(engine: AsyncEngine) -> None:
    """TC-12: anything other than 23P01/40P01 propagates (here a foreign-key failure)."""
    await _fixture(engine)
    bad = NewAppointment(
        dealership_id=DEALERSHIP,
        service_type_id=999_999,
        start_at=START,
        end_at=END,
        customer=Customer(id="c1", email=None, name=None),
        vehicle=Vehicle(id=None, vin="VIN9", make=None, model=None),
        vehicle_key="VIN9",
    )
    with pytest.raises(DBAPIError):
        async with PostgresUnitOfWork(engine) as tx:
            await tx.appointments.reserve(bad, Candidate(101, 103))


async def test_claim_record_and_free_candidates(engine: AsyncEngine) -> None:
    """TC-13: ``claim`` returns None on first insert and the stored row on the second; ``record``
    fills code and body; ``free_candidates`` excludes busy bays and technicians and lists only
    qualified technicians."""
    await _fixture(engine)
    key = uuid4()
    async with PostgresUnitOfWork(engine) as tx:
        assert await tx.idempotency.claim(DEALERSHIP, key, "h1") is None
        stored = await tx.idempotency.claim(DEALERSHIP, key, "h1")
        assert stored is not None and stored.code is None and stored.request_hash == "h1"
        await tx.idempotency.record(DEALERSHIP, key, "capacity_exhausted", {"code": "x"})
        stored = await tx.idempotency.claim(DEALERSHIP, key, "h1")
        assert stored is not None
        assert (stored.code, stored.body) == ("capacity_exhausted", {"code": "x"})

        booked = await tx.appointments.reserve(_new("VIN1"), Candidate(101, 103))
        assert isinstance(booked, Confirmed)
        free = await tx.appointments.free_candidates(DEALERSHIP, [103, 104], START, END)
        assert free == [Candidate(102, 104)]  # bay 101 and technician 103 are busy
        only_qualified = await tx.appointments.free_candidates(DEALERSHIP, [104], START, END)
        assert only_qualified == [Candidate(102, 104)]
        later = await tx.appointments.free_candidates(
            DEALERSHIP, [103, 104], END, END + timedelta(hours=1)
        )
        assert later == [Candidate(b, t) for b in BAYS for t in TECHS]  # back-to-back is free


async def test_book_appointment_end_to_end_against_real_adapters(engine: AsyncEngine) -> None:
    """T7 done-when: ``BookAppointment`` with the PostgreSQL adapters books one appointment."""
    await _fixture(engine)
    reads = PostgresSchedulingReadRepository(engine.connect)
    dealership = await reads.dealership(DEALERSHIP)
    assert dealership is not None and dealership.zone == ZoneInfo("Europe/London")
    assert SystemClock().now().tzinfo is not None  # the production clock is aware UTC
    clock = FixedClock(datetime(2027, 3, 25, 16, 0, tzinfo=UTC))  # inside the 90-day horizon
    use_case = BookAppointment(uow=lambda: PostgresUnitOfWork(engine), clock=clock)
    cmd = BookingCommand(
        dealership_id=DEALERSHIP,
        service_type_id=1,
        start_local=datetime(2027, 3, 29, 9, 0),
        customer=Customer(id="c1", email=None, name=None),
        vehicle=Vehicle(id=None, vin="WVWZZZ1", make=None, model=None),
        idempotency_key=uuid4(),
    )
    outcome = await use_case.execute(cmd, dealership)
    assert outcome.code == "confirmed", outcome
    stored = await reads.appointment(DEALERSHIP, int(outcome.body["appointment_id"]))  # type: ignore[call-overload]
    assert stored is not None and stored.vehicle.vin == "WVWZZZ1"
    assert outcome.bay_id in BAYS and outcome.technician_id in TECHS
