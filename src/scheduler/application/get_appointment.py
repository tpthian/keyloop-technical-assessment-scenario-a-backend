"""``GetAppointment``: read one appointment of one dealership (design §3, SPEC-001 Interfaces)."""

from __future__ import annotations

from collections.abc import Mapping

from scheduler.application.ports import SchedulingReadRepository
from scheduler.application.presenters import appointment_body
from scheduler.domain.errors import NotFound


class GetAppointment:
    def __init__(self, reads: SchedulingReadRepository) -> None:
        self.reads = reads

    async def execute(self, dealership_id: int, appointment_id: int) -> Mapping[str, object]:
        """The appointment body; ``NotFound`` for an unknown dealership or an appointment
        outside it (the read is scoped by dealership, so another tenant's id is not found)."""
        dealership = await self.reads.dealership(dealership_id)
        if dealership is None:
            raise NotFound("dealership")
        appointment = await self.reads.appointment(dealership_id, appointment_id)
        if appointment is None:
            raise NotFound("appointment")
        return appointment_body(appointment, dealership)
