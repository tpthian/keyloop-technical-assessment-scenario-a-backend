"""In-memory fakes of the application ports (SPEC-001 T6, AC-15, D-041).

They implement the Protocols of ``scheduler.application.ports`` structurally, like the
PostgreSQL adapters; ``uv run mypy tests/fakes.py`` checks the conformance through the typed
``_conformance`` function at the bottom. No database is involved.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from types import TracebackType
from uuid import UUID

from scheduler.application.ports import (
    AppointmentRepository,
    AttemptGate,
    Clock,
    IdempotencyRepository,
    SchedulingReadRepository,
    UnitOfWork,
    UnitOfWorkFactory,
)
from scheduler.domain.model import (
    Appointment,
    BusyRange,
    Candidate,
    Confirmed,
    Dealership,
    NewAppointment,
    ResourceTaken,
    ServiceType,
    StoredResponse,
)


class FakeReads:
    """Reference data in dicts; counts ``dealership`` lookups (TC-09: never called)."""

    def __init__(
        self,
        dealerships: Iterable[Dealership] = (),
        service_types: Iterable[ServiceType] = (),
        qualification: Mapping[tuple[int, int], Sequence[int]] | None = None,
        bays: Mapping[int, Sequence[int]] | None = None,
        appointments: Iterable[Appointment] = (),
        watermark: datetime | None = None,
    ) -> None:
        self.dealerships = {d.id: d for d in dealerships}
        self.service_types = {s.id: s for s in service_types}
        self.qualification = dict(qualification or {})  # (dealership_id, service_type_id)
        self.bay_ids = dict(bays or {})
        self.appointments = {(a.dealership_id, a.id): a for a in appointments}
        self._watermark = watermark
        self.dealership_calls = 0

    async def dealership(self, dealership_id: int) -> Dealership | None:
        self.dealership_calls += 1
        return self.dealerships.get(dealership_id)

    async def service_type(self, service_type_id: int) -> ServiceType | None:
        return self.service_types.get(service_type_id)

    async def qualified_technicians(self, dealership_id: int, service_type_id: int) -> list[int]:
        return list(self.qualification.get((dealership_id, service_type_id), ()))

    async def bays(self, dealership_id: int) -> list[int]:
        return list(self.bay_ids.get(dealership_id, ()))

    async def appointment(self, dealership_id: int, appointment_id: int) -> Appointment | None:
        return self.appointments.get((dealership_id, appointment_id))

    async def busy_ranges(self, dealership_id: int, lo: datetime, hi: datetime) -> list[BusyRange]:
        return [
            BusyRange(a.bay_id, a.technician_id, a.start_at, a.end_at)
            for a in self.appointments.values()
            if a.dealership_id == dealership_id and a.start_at < hi and lo < a.end_at
        ]

    async def watermark(self) -> datetime:
        if self._watermark is None:
            raise AssertionError("FakeReads has no watermark configured")
        return self._watermark


class FakeAppointments:
    """Scripted ``reserve`` results; a ``Confirmed`` result stores the inserted row.

    ``log`` is shared with ``CountingGate`` so a test can see the gate ran before any reserve.
    """

    def __init__(
        self,
        candidates: Sequence[Candidate] = (),
        script: Sequence[Confirmed | ResourceTaken] = (),
        log: list[str] | None = None,
    ) -> None:
        self.candidates = list(candidates)
        self.script = list(script)
        self.log = log if log is not None else []
        self.tried: list[Candidate] = []
        self.rows: dict[int, Appointment] = {}

    async def free_candidates(
        self, dealership_id: int, qualified: list[int], start: datetime, end: datetime
    ) -> list[Candidate]:
        return [c for c in self.candidates if c.technician_id in qualified]

    async def reserve(self, new: NewAppointment, candidate: Candidate) -> Confirmed | ResourceTaken:
        self.log.append("reserve")
        self.tried.append(candidate)
        if not self.script:
            raise AssertionError(f"reserve called more often than scripted: {candidate}")
        result = self.script.pop(0)
        if isinstance(result, Confirmed):
            self.rows[result.appointment_id] = Appointment(
                id=result.appointment_id,
                dealership_id=new.dealership_id,
                service_type_id=new.service_type_id,
                bay_id=candidate.bay_id,
                technician_id=candidate.technician_id,
                status="confirmed",
                start_at=new.start_at,
                end_at=new.end_at,
                customer=new.customer,
                vehicle=new.vehicle,
            )
        return result

    async def by_id(self, appointment_id: int) -> Appointment:
        return self.rows[appointment_id]


class FakeIdempotency:
    """Key rows in a dict keyed by ``(dealership_id, key)``; ``claim`` inserts or returns.

    ``claim`` writes ``"claim"`` into ``log``; a test shares the log to see the call order.
    """

    def __init__(
        self,
        rows: Mapping[tuple[int, UUID], StoredResponse] | None = None,
        log: list[str] | None = None,
    ) -> None:
        self.rows: dict[tuple[int, UUID], StoredResponse] = dict(rows or {})
        self.log = log if log is not None else []

    async def claim(
        self, dealership_id: int, key: UUID, request_hash: str
    ) -> StoredResponse | None:
        self.log.append("claim")
        existing = self.rows.get((dealership_id, key))
        if existing is not None:
            return existing
        self.rows[(dealership_id, key)] = StoredResponse(request_hash, None, None)
        return None

    async def record(
        self, dealership_id: int, key: UUID, code: str, body: Mapping[str, object]
    ) -> None:
        row = self.rows[(dealership_id, key)]
        self.rows[(dealership_id, key)] = replace(row, code=code, body=dict(body))


class FakeUnitOfWork:
    """Snapshot on enter, restore on exception, so a rollback is observable.

    The port attributes are typed with the port Protocols (they are invariant); tests keep
    their own handles to the concrete fakes passed in. ``serialise`` writes ``"serialise"`` into
    the log shared with ``FakeAppointments``.
    """

    def __init__(
        self, reads: FakeReads, appointments: FakeAppointments, idempotency: FakeIdempotency
    ) -> None:
        self._fake_appointments = appointments
        self._fake_idempotency = idempotency
        self.appointments: AppointmentRepository = appointments
        self.idempotency: IdempotencyRepository = idempotency
        self.reads: SchedulingReadRepository = reads
        self.committed = False
        self.rolled_back = False
        self._snapshot: tuple[dict[int, Appointment], dict[tuple[int, UUID], StoredResponse]]
        self._snapshot = ({}, {})

    async def serialise(self, dealership_id: int) -> None:
        self._fake_appointments.log.append("serialise")

    async def __aenter__(self) -> FakeUnitOfWork:
        self.committed = self.rolled_back = False
        self._snapshot = (dict(self._fake_appointments.rows), dict(self._fake_idempotency.rows))
        return self

    async def __aexit__(
        self,
        et: type[BaseException] | None,
        ev: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if et is None:
            self.committed = True
            return
        self._fake_appointments.rows, self._fake_idempotency.rows = self._snapshot
        self.rolled_back = True


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class CountingGate:
    """Counts awaits and writes ``"gate"`` into the shared log."""

    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.calls = 0

    async def __call__(self) -> None:
        self.calls += 1
        self.log.append("gate")


def factory(uow: FakeUnitOfWork) -> UnitOfWorkFactory:
    """A ``UnitOfWorkFactory`` handing out the one fake unit of work."""
    return lambda: uow


def _conformance(
    reads: FakeReads,
    appointments: FakeAppointments,
    idempotency: FakeIdempotency,
    uow: FakeUnitOfWork,
    clock: FixedClock,
    gate: CountingGate,
) -> None:
    """Never called; mypy checks each fake against its Protocol through these assignments."""
    _reads: SchedulingReadRepository = reads
    _appointments: AppointmentRepository = appointments
    _idempotency: IdempotencyRepository = idempotency
    _uow: UnitOfWork = uow
    _clock: Clock = clock
    _gate: AttemptGate = gate
