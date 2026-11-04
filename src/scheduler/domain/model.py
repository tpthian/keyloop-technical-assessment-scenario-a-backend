"""Domain types (SPEC-001 § Execution, Interfaces; design §2, ADR-007, ADR-009).

Frozen dataclasses only. Instants are aware UTC ``datetime`` values; the one naive value is
``BookingCommand.start_local``, the wall time as the client sent it in the dealership zone.
``AttemptResult`` lives in ``domain/attempts.py`` with the attempt policy.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Hours:
    """Opening hours of one weekday; same-day, ``opens_at < closes_at`` (CHECK in the schema)."""

    weekday: int  # 0 = Monday, as ``date.weekday()``
    opens_at: time
    closes_at: time


@dataclass(frozen=True)
class Dealership:
    id: int
    name: str
    zone: ZoneInfo
    hours: Mapping[int, Hours]  # keyed by weekday; a missing weekday is closed (ADR-009)


@dataclass(frozen=True)
class ServiceType:
    id: int
    name: str
    duration_minutes: int


@dataclass(frozen=True)
class Customer:
    """Snapshot; ``id`` or ``email`` is required (checked at the interface, ADR-007)."""

    id: str | None
    email: str | None
    name: str | None


@dataclass(frozen=True)
class Vehicle:
    """Snapshot; ``id`` or ``vin`` is required (checked at the interface, ADR-007).

    ``vin`` is already normalised by ``canonical.normalise_vin``.
    """

    id: str | None
    vin: str | None
    make: str | None
    model: str | None


@dataclass(frozen=True)
class BookingCommand:
    dealership_id: int
    service_type_id: int
    start_local: datetime  # naive wall time in the dealership zone, whole minutes
    customer: Customer
    vehicle: Vehicle
    idempotency_key: UUID

    @property
    def vehicle_key(self) -> str:
        """The VIN when given, else ``id:<vehicle id>`` (design §2, ``no_vehicle_overlap``)."""
        if self.vehicle.vin is not None:
            return self.vehicle.vin
        if self.vehicle.id is not None:
            return f"id:{self.vehicle.id}"
        # the interface guarantees an identifier; never fabricate a key such as "id:None"
        raise ValueError("vehicle has neither vin nor id")


@dataclass(frozen=True)
class Candidate:
    bay_id: int
    technician_id: int


@dataclass(frozen=True)
class NewAppointment:
    dealership_id: int
    service_type_id: int
    start_at: datetime  # aware UTC
    end_at: datetime  # aware UTC, start_at + elapsed duration (ADR-009)
    customer: Customer
    vehicle: Vehicle
    vehicle_key: str


@dataclass(frozen=True)
class Appointment:
    """A stored appointment.

    ``pickup_from`` is derived at response time by ``time_rules.pickup_from``, never stored
    (ADR-009).
    """

    id: int
    dealership_id: int
    service_type_id: int
    bay_id: int
    technician_id: int
    status: str
    start_at: datetime
    end_at: datetime
    customer: Customer
    vehicle: Vehicle


@dataclass(frozen=True)
class Confirmed:
    appointment_id: int


@dataclass(frozen=True)
class ResourceTaken:
    """A lost attempt: constraint name from 23P01, or ``None`` with ``deadlock=True`` for 40P01."""

    constraint: str | None
    deadlock: bool


@dataclass(frozen=True)
class BusyRange:
    bay_id: int
    technician_id: int
    start_at: datetime
    end_at: datetime


@dataclass(frozen=True)
class StoredResponse:
    """An idempotency row; ``code is None`` while claimed and not yet recorded (ADR-008)."""

    request_hash: str
    code: str | None
    body: Mapping[str, object] | None
