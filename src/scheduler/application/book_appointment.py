"""``BookAppointment``: the only writer and transaction owner (design §2, §3, ADR-004, ADR-008).

ADR-008 steps 1 to 3 (parse, load the dealership, schema validation) happen in the interface
layer before this runs; the loaded ``Dealership`` arrives as an argument, so this use case never
looks one up and never raises ``NotFound`` (SPEC-001 Known Facts 9). Steps 4 to 7 are below, in
one transaction: hash, claim, business validation, candidates, attempts, record, COMMIT.

Rules kept here:

- ``ReplayConflict`` is raised inside the block; the rollback writes nothing, because the
  original key row belongs to another, committed transaction.
- ``contention`` leaves the block by raising ``Contention``, so the unit of work rolls back and
  the claim is discarded; it is caught outside the block and returned as a transient outcome.
- Every stored outcome is recorded before the block exits, so key, appointment and response
  commit together.
- Database errors are never caught here; the reserve adapter is the only place that reads
  SQLSTATE (ADR-004).
"""

from __future__ import annotations

from datetime import datetime

from scheduler.application.outcomes import (
    VALIDATION,
    Outcome,
    conflict_body,
    contention_body,
    replay_outcome,
    validation_body,
)
from scheduler.application.ports import (
    AttemptGate,
    Clock,
    SchedulingReadRepository,
    UnitOfWorkFactory,
)
from scheduler.application.presenters import appointment_body
from scheduler.domain.attempts import (
    CAPACITY_EXHAUSTED,
    CONFIRMED,
    CONTENTION,
    VEHICLE_ALREADY_BOOKED,
    run_attempts,
    shuffled,
)
from scheduler.domain.canonical import canonical_hash
from scheduler.domain.errors import Contention, GapTime, ReplayConflict
from scheduler.domain.model import BookingCommand, Dealership, NewAppointment, ServiceType
from scheduler.domain.time_rules import HORIZON, end_at, local_to_utc, start_in_hours

_Validated = tuple[str, None, None] | tuple[None, ServiceType, datetime]


class BookAppointment:
    def __init__(
        self, uow: UnitOfWorkFactory, clock: Clock, gate: AttemptGate | None = None
    ) -> None:
        self.uow = uow
        self.clock = clock
        self.gate = gate  # test seam for the barrier race (TC-31); None in production

    async def execute(self, cmd: BookingCommand, dealership: Dealership) -> Outcome:
        # dealership already loaded by the interface layer, before BEGIN (design §2, ADR-008 step 2)
        request_hash = canonical_hash(cmd, dealership.zone)
        try:
            async with self.uow() as tx:  # BEGIN + SET LOCAL
                stored = await tx.idempotency.claim(
                    cmd.dealership_id, cmd.idempotency_key, request_hash
                )
                if stored is not None:
                    if stored.request_hash != request_hash:
                        raise ReplayConflict()
                    return replay_outcome(stored)  # final=True, replay=True
                failure, service_type, start_utc = await self._validate(tx.reads, dealership, cmd)
                if failure is not None:
                    body = validation_body(failure)
                    await tx.idempotency.record(
                        cmd.dealership_id, cmd.idempotency_key, VALIDATION, body
                    )
                    return Outcome(VALIDATION, body, final=True)
                assert service_type is not None and start_utc is not None  # narrowed by _validate
                end_utc = end_at(start_utc, service_type.duration_minutes)
                qualified = await tx.reads.qualified_technicians(cmd.dealership_id, service_type.id)
                candidates = shuffled(
                    await tx.appointments.free_candidates(
                        cmd.dealership_id, qualified, start_utc, end_utc
                    )
                )
                new = NewAppointment(
                    cmd.dealership_id,
                    service_type.id,
                    start_utc,
                    end_utc,
                    cmd.customer,
                    cmd.vehicle,
                    cmd.vehicle_key,
                )
                if self.gate is not None:
                    await self.gate()  # test seam: first INSERTs leave together
                result = await run_attempts(candidates, lambda c: tx.appointments.reserve(new, c))
                if result.code == CONFIRMED:
                    assert result.appointment_id is not None  # set whenever confirmed
                    appointment = await tx.appointments.by_id(result.appointment_id)
                    body = appointment_body(appointment, dealership)
                    await tx.idempotency.record(
                        cmd.dealership_id, cmd.idempotency_key, CONFIRMED, body
                    )
                    return Outcome(
                        CONFIRMED,
                        body,
                        final=True,
                        attempts=result.attempts,
                        deadlocks=result.deadlocks,
                        candidates_pruned=result.candidates_pruned,
                        bay_id=appointment.bay_id,
                        technician_id=appointment.technician_id,
                    )
                if result.code in (CAPACITY_EXHAUSTED, VEHICLE_ALREADY_BOOKED):
                    body = conflict_body(result.code)
                    await tx.idempotency.record(
                        cmd.dealership_id, cmd.idempotency_key, result.code, body
                    )
                    return Outcome(
                        result.code,
                        body,
                        final=True,
                        attempts=result.attempts,
                        deadlocks=result.deadlocks,
                        candidates_pruned=result.candidates_pruned,
                    )
                raise Contention(result)  # leaves the block: ROLLBACK, claim discarded
        except Contention as c:
            return Outcome(
                CONTENTION,
                contention_body(),
                final=False,
                attempts=c.result.attempts,
                deadlocks=c.result.deadlocks,
                candidates_pruned=c.result.candidates_pruned,
            )

    async def _validate(
        self, reads: SchedulingReadRepository, dealership: Dealership, cmd: BookingCommand
    ) -> _Validated:
        """Business validation, ADR-008 step 6, in the SPEC order; each failure is a stored 422.

        Returns ``(message, None, None)`` on the first failure, else
        ``(None, service_type, start_utc)``.
        """
        service_type = await reads.service_type(cmd.service_type_id)
        if service_type is None:
            return f"service type {cmd.service_type_id} does not exist", None, None
        try:
            start_utc = local_to_utc(cmd.start_local, dealership.zone)
        except GapTime as gap:
            return str(gap), None, None  # "<wall time> does not exist in <zone>"
        now = self.clock.now()
        if start_utc < now:
            return "start_at is in the past", None, None
        if start_utc > now + HORIZON:
            return f"start_at is more than {HORIZON.days} days ahead", None, None
        if not start_in_hours(cmd.start_local, dealership):
            return "start_at is outside opening hours", None, None
        if not await reads.qualified_technicians(cmd.dealership_id, service_type.id):
            return "no technician is qualified for this service type", None, None
        return None, service_type, start_utc
