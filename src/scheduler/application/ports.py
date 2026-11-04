"""Ports owned by the application layer (SPEC-001 § Execution, Interfaces; design §2, D-041).

Adapters in ``scheduler.infrastructure`` and the in-memory fakes in ``tests/fakes.py``
implement these structurally; nothing subclasses them. Protocol attributes are invariant, so an
implementation declares ``appointments``, ``idempotency`` and ``reads`` with the port types
below, not with its concrete class.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

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


class Clock(Protocol):
    def now(self) -> datetime: ...  # aware UTC


class AttemptGate(Protocol):
    async def __call__(self) -> None: ...  # awaited once per booking before the first reserve


class SchedulingReadRepository(Protocol):
    """Reference data and read-only appointment queries. Usable outside a transaction."""

    async def dealership(self, dealership_id: int) -> Dealership | None: ...
    async def service_type(self, service_type_id: int) -> ServiceType | None: ...
    async def qualified_technicians(
        self, dealership_id: int, service_type_id: int
    ) -> list[int]: ...
    async def bays(self, dealership_id: int) -> list[int]: ...
    async def appointment(self, dealership_id: int, appointment_id: int) -> Appointment | None: ...
    async def busy_ranges(
        self, dealership_id: int, lo: datetime, hi: datetime
    ) -> list[BusyRange]: ...
    async def watermark(self) -> datetime: ...  # coalesce(pg_last_xact_replay_timestamp(), now())


class AppointmentRepository(Protocol):
    """Write side; bound to the unit of work's transaction."""

    async def free_candidates(
        self, dealership_id: int, qualified: list[int], start: datetime, end: datetime
    ) -> list[Candidate]: ...
    async def reserve(
        self, new: NewAppointment, candidate: Candidate
    ) -> Confirmed | ResourceTaken: ...
    async def by_id(self, appointment_id: int) -> Appointment: ...


class IdempotencyRepository(Protocol):
    """Bound to the unit of work's transaction."""

    async def claim(
        self, dealership_id: int, key: UUID, request_hash: str
    ) -> StoredResponse | None: ...
    async def record(
        self, dealership_id: int, key: UUID, code: str, body: Mapping[str, object]
    ) -> None: ...


class UnitOfWork(Protocol):
    """One transaction: BEGIN on enter; COMMIT on clean exit; ROLLBACK on exception.

    Sets ``SET LOCAL deadlock_timeout = '100ms'`` and ``statement_timeout = '2s'`` on enter
    (ADR-004).
    """

    appointments: AppointmentRepository
    idempotency: IdempotencyRepository
    reads: SchedulingReadRepository  # same connection, for in-transaction reference reads

    async def serialise(self, dealership_id: int) -> None:
        """Transaction-scoped advisory lock, so bookings of one dealership run one at a time.

        Held until COMMIT or ROLLBACK. Every booking of a dealership takes the same single lock
        before its first attempt, so attempts form no lock cycles and no 40P01 arises under
        contention (ADR-004 amendment, D-048).
        """
        ...

    async def __aenter__(self) -> UnitOfWork: ...
    async def __aexit__(
        self,
        et: type[BaseException] | None,
        ev: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


UnitOfWorkFactory = Callable[[], UnitOfWork]
