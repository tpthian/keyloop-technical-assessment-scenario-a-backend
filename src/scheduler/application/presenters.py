"""The one place the appointment body is shaped (SPEC-001 Wire formats, ADR-008, ADR-009).

The 201 body, the stored replay body and the ``GET .../appointments/{id}`` body all come from
``appointment_body``, so a replay is byte-for-byte the live answer. Values are JSON-ready
(instants as ISO 8601 UTC strings with ``Z``) because the body is stored as ``jsonb``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from scheduler.domain.model import Appointment, Dealership
from scheduler.domain.time_rules import pickup_from


def _utc(instant: datetime) -> str:
    return instant.astimezone(UTC).isoformat().replace("+00:00", "Z")


def appointment_body(appointment: Appointment, dealership: Dealership) -> dict[str, object]:
    """Wire-format body; adds the derived ``pickup_from`` and the dealership ``timezone``."""
    customer = appointment.customer
    vehicle = appointment.vehicle
    return {
        "appointment_id": appointment.id,
        "dealership_id": appointment.dealership_id,
        "service_type_id": appointment.service_type_id,
        "bay_id": appointment.bay_id,
        "technician_id": appointment.technician_id,
        "status": appointment.status,
        "start_at": _utc(appointment.start_at),
        "end_at": _utc(appointment.end_at),
        "pickup_from": _utc(pickup_from(appointment.end_at, dealership)),
        "timezone": dealership.zone.key,
        "customer": {"id": customer.id, "email": customer.email, "name": customer.name},
        "vehicle": {
            "id": vehicle.id,
            "vin": vehicle.vin,
            "make": vehicle.make,
            "model": vehicle.model,
        },
    }
