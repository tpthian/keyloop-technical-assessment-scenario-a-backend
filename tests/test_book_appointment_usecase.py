"""TC-09, TC-10, TC-11 (AC-03, AC-04, AC-05, AC-08, AC-15): ``BookAppointment`` on fakes.

One test per TC clause; no database. Dealership 1 is London, Mon-Sat 08:00-18:00; the clock is
fixed at 2027-03-25T16:00:00Z (a Thursday, before the 2027-03-28 DST change, so London is UTC+0).
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from scheduler.application.book_appointment import BookAppointment
from scheduler.application.outcomes import Outcome
from scheduler.domain.canonical import canonical_hash
from scheduler.domain.errors import ReplayConflict
from scheduler.domain.model import (
    BookingCommand,
    Candidate,
    Confirmed,
    Customer,
    Dealership,
    Hours,
    ResourceTaken,
    ServiceType,
    StoredResponse,
    Vehicle,
)
from tests.fakes import (
    CountingGate,
    FakeAppointments,
    FakeIdempotency,
    FakeReads,
    FakeUnitOfWork,
    FixedClock,
    factory,
)

LONDON = Dealership(
    id=1,
    name="Riverside Motors",
    zone=ZoneInfo("Europe/London"),
    hours={d: Hours(d, time(8), time(18)) for d in range(6)},
)
OIL = ServiceType(1, "Oil change", 60)
UNSTAFFED = ServiceType(3, "Bodywork", 4320)  # no technician qualified at dealership 1
NOW = datetime(2027, 3, 25, 16, 0, tzinfo=UTC)
KEY = UUID("00000000-0000-4000-8000-000000000001")
GRID = [Candidate(b, t) for b in (1, 2) for t in (1, 2)]
DEADLOCK = ResourceTaken(None, deadlock=True)


def command(start_local: datetime, service_type_id: int = OIL.id) -> BookingCommand:
    return BookingCommand(
        dealership_id=LONDON.id,
        service_type_id=service_type_id,
        start_local=start_local,
        customer=Customer("C-42", None, "Sam Lee"),
        vehicle=Vehicle(None, "WVWZZZ1JZXW000001", "VW", "Golf"),
        idempotency_key=KEY,
    )


FRIDAY_9 = command(datetime(2027, 3, 26, 9, 0))


class World:
    """The fakes of one test, wired into a ``BookAppointment``."""

    def __init__(
        self,
        candidates: list[Candidate] | None = None,
        script: list[Confirmed | ResourceTaken] | None = None,
        stored: StoredResponse | None = None,
    ) -> None:
        self.log: list[str] = []
        self.reads = FakeReads(
            dealerships=[LONDON],
            service_types=[OIL, UNSTAFFED],
            qualification={(LONDON.id, OIL.id): [1, 2]},
        )
        self.appointments = FakeAppointments(
            candidates=GRID if candidates is None else candidates,
            script=script or [],
            log=self.log,
        )
        self.idempotency = FakeIdempotency(
            {(LONDON.id, KEY): stored} if stored else None, log=self.log
        )
        self.uow = FakeUnitOfWork(self.reads, self.appointments, self.idempotency)
        self.gate = CountingGate(self.log)
        self.use_case = BookAppointment(factory(self.uow), FixedClock(NOW), self.gate)

    async def book(self, cmd: BookingCommand = FRIDAY_9) -> Outcome:
        return await self.use_case.execute(cmd, LONDON)

    @property
    def key_row(self) -> StoredResponse | None:
        return self.idempotency.rows.get((LONDON.id, KEY))


# --- TC-09: dealership argument, replay conflict, replay -----------------------------------


async def test_dealership_arrives_as_argument_and_is_never_looked_up() -> None:
    world = World(script=[Confirmed(7)])
    outcome = await world.book()
    assert outcome.code == "confirmed"
    assert world.reads.dealership_calls == 0


async def test_claim_with_other_hash_raises_replay_conflict() -> None:
    original = StoredResponse("other-hash", "confirmed", {"appointment_id": 3})
    world = World(stored=original)
    with pytest.raises(ReplayConflict):
        await world.book()
    assert world.key_row == original  # the original row is unchanged
    assert world.appointments.tried == []


async def test_claim_with_same_hash_replays_without_attempt() -> None:
    body = {"code": "capacity_exhausted", "message": "stored"}
    stored = StoredResponse(canonical_hash(FRIDAY_9, LONDON.zone), "capacity_exhausted", body)
    world = World(stored=stored)
    outcome = await world.book()
    assert outcome == Outcome("capacity_exhausted", body, final=True, replay=True)
    assert world.appointments.tried == []
    assert world.gate.calls == 0


# --- TC-10: business failures are stored 422s, no attempt ----------------------------------


async def assert_validation_recorded(cmd: BookingCommand, message_part: str) -> None:
    world = World(script=[Confirmed(7)])
    outcome = await world.book(cmd)
    assert outcome.code == "validation"
    assert outcome.final is True and outcome.replay is False
    assert message_part in str(outcome.body["message"])
    assert world.key_row == StoredResponse(
        canonical_hash(cmd, LONDON.zone), "validation", dict(outcome.body)
    )
    assert world.uow.committed is True
    assert world.appointments.tried == []
    assert world.gate.calls == 0


async def test_unknown_service_type_is_validation_recorded() -> None:
    await assert_validation_recorded(
        command(datetime(2027, 3, 26, 9, 0), service_type_id=999), "service type 999"
    )


async def test_gap_time_is_validation_recorded() -> None:
    # 2027-03-28 01:30 does not exist in London (clocks go 01:00 -> 02:00)
    await assert_validation_recorded(command(datetime(2027, 3, 28, 1, 30)), "does not exist")


async def test_past_start_is_validation_recorded() -> None:
    await assert_validation_recorded(command(datetime(2027, 3, 25, 9, 0)), "past")


async def test_start_beyond_horizon_is_validation_recorded() -> None:
    # 2027-06-25 09:00 BST = 08:00Z, past NOW + 90 days = 2027-06-23T16:00Z
    await assert_validation_recorded(command(datetime(2027, 6, 25, 9, 0)), "90 days")


async def test_start_outside_hours_is_validation_recorded() -> None:
    await assert_validation_recorded(command(datetime(2027, 3, 26, 18, 0)), "opening hours")


async def test_no_qualified_technician_is_validation_recorded() -> None:
    await assert_validation_recorded(
        command(datetime(2027, 3, 26, 9, 0), service_type_id=UNSTAFFED.id), "qualified"
    )


# --- TC-11: scripted reserve results ----------------------------------------------------------


async def test_confirmed_is_recorded() -> None:
    world = World(candidates=[Candidate(2, 1)], script=[Confirmed(7)])
    outcome = await world.book()
    expected_body = {
        "appointment_id": 7,
        "dealership_id": 1,
        "service_type_id": 1,
        "bay_id": 2,
        "technician_id": 1,
        "status": "confirmed",
        "start_at": "2027-03-26T09:00:00Z",
        "end_at": "2027-03-26T10:00:00Z",
        "pickup_from": "2027-03-26T10:00:00Z",
        "timezone": "Europe/London",
        "customer": {"id": "C-42", "email": None, "name": "Sam Lee"},
        "vehicle": {"id": None, "vin": "WVWZZZ1JZXW000001", "make": "VW", "model": "Golf"},
    }
    assert outcome == Outcome(
        "confirmed", expected_body, final=True, attempts=1, bay_id=2, technician_id=1
    )
    assert world.key_row == StoredResponse(
        canonical_hash(FRIDAY_9, LONDON.zone), "confirmed", expected_body
    )
    assert world.uow.committed is True
    assert 7 in world.appointments.rows


async def test_capacity_exhausted_is_recorded() -> None:
    world = World(
        candidates=[Candidate(1, 1)], script=[ResourceTaken("no_bay_overlap", deadlock=False)]
    )
    outcome = await world.book()
    assert (outcome.code, outcome.final) == ("capacity_exhausted", True)
    assert (outcome.attempts, outcome.candidates_pruned) == (1, 1)
    assert world.key_row is not None and world.key_row.code == "capacity_exhausted"
    assert world.key_row.body == outcome.body
    assert world.uow.committed is True


async def test_vehicle_already_booked_is_recorded() -> None:
    world = World(script=[ResourceTaken("no_vehicle_overlap", deadlock=False)])
    outcome = await world.book()
    assert (outcome.code, outcome.final, outcome.attempts) == ("vehicle_already_booked", True, 1)
    assert world.key_row is not None and world.key_row.code == "vehicle_already_booked"
    assert world.key_row.body == outcome.body
    assert world.uow.committed is True


async def test_contention_rolls_back_and_records_nothing() -> None:
    candidates = [Candidate(b, t) for b in (1, 2, 3) for t in (1, 2)]  # 6 pairs, bound is 5
    world = World(candidates=candidates, script=[DEADLOCK] * 5)
    outcome = await world.book()
    assert (outcome.code, outcome.final) == ("contention", False)
    assert (outcome.attempts, outcome.deadlocks, outcome.candidates_pruned) == (5, 5, 0)
    assert world.uow.rolled_back is True and world.uow.committed is False
    assert world.key_row is None  # the claim is discarded with the transaction
    assert world.appointments.rows == {}


async def test_attempt_gate_awaited_once_before_first_reserve() -> None:
    world = World(script=[DEADLOCK, DEADLOCK, Confirmed(7)])
    outcome = await world.book()
    assert outcome.code == "confirmed"
    assert world.gate.calls == 1
    assert world.log == ["claim", "serialise", "gate", "reserve", "reserve", "reserve"]


async def test_serialise_after_claim_before_any_reserve_and_never_on_replay() -> None:
    """TC-11 (D-048): a booking takes the dealership lock after the claim and before the gate and
    the first reserve; a replay returns after the claim without taking it."""
    booking = World(script=[Confirmed(7)])
    await booking.book()
    assert booking.log == ["claim", "serialise", "gate", "reserve"]

    body = {"code": "capacity_exhausted", "message": "stored"}
    stored = StoredResponse(canonical_hash(FRIDAY_9, LONDON.zone), "capacity_exhausted", body)
    replay = World(stored=stored)
    await replay.book()
    assert replay.log == ["claim"]
