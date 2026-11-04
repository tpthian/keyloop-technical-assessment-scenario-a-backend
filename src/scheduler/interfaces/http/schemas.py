"""Request and response models of the booking API (SPEC-001 Wire formats, ADR-007, ADR-008).

``BookingRequest`` is validated explicitly by the booking handler after the dealership is
loaded (ADR-008 step 3), never by FastAPI before the handler runs. ``to_command`` is the one
mapping from the wire model to the domain ``BookingCommand``; the duplication between the two
shapes is accepted (D-041). ``AppointmentOut`` and ``ErrorOut`` document the bodies in
``/docs``; the handlers return the presenter's dict, so nothing is re-serialised through them.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, NaiveDatetime, field_validator, model_validator

from scheduler.domain import model as domain
from scheduler.domain.canonical import normalise_vin

_FORBID = ConfigDict(extra="forbid")


class Customer(BaseModel):
    """``id`` or ``email`` is required (ADR-007)."""

    model_config = _FORBID

    id: str | None = None
    email: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def _has_identifier(self) -> Customer:
        if self.id is None and self.email is None:
            raise ValueError("customer needs an id or an email")
        return self


class Vehicle(BaseModel):
    """``id`` or ``vin`` is required (ADR-007); ``vin`` is normalised before the check."""

    model_config = _FORBID

    id: str | None = None
    vin: str | None = None
    make: str | None = None
    model: str | None = None

    @field_validator("vin", mode="after")
    @classmethod
    def _normalise_vin(cls, value: str | None) -> str | None:
        return normalise_vin(value)

    @model_validator(mode="after")
    def _has_identifier(self) -> Vehicle:
        if self.id is None and self.vin is None:
            raise ValueError("vehicle needs an id or a vin")
        return self


class BookingRequest(BaseModel):
    """``start_at`` is the naive wall time in the dealership zone, whole minutes (D-041 item 2).

    An offset fails ``NaiveDatetime``; seconds or microseconds fail ``_whole_minutes``; an
    unknown field fails ``extra="forbid"``. Each is a schema 422, never stored (ADR-008 step 3).
    """

    model_config = _FORBID

    service_type_id: int
    start_at: NaiveDatetime
    customer: Customer
    vehicle: Vehicle

    @field_validator("start_at", mode="after")
    @classmethod
    def _whole_minutes(cls, value: datetime) -> datetime:
        if value.second or value.microsecond:
            raise ValueError("start_at must be whole minutes")
        return value


def to_command(req: BookingRequest, dealership_id: int, key: UUID) -> domain.BookingCommand:
    """The one mapping from the wire model to the domain command; no HTTP type crosses it."""
    customer, vehicle = req.customer, req.vehicle
    return domain.BookingCommand(
        dealership_id=dealership_id,
        service_type_id=req.service_type_id,
        start_local=req.start_at,
        customer=domain.Customer(id=customer.id, email=customer.email, name=customer.name),
        vehicle=domain.Vehicle(
            id=vehicle.id, vin=vehicle.vin, make=vehicle.make, model=vehicle.model
        ),
        idempotency_key=key,
    )


class CustomerOut(BaseModel):
    id: str | None
    email: str | None
    name: str | None


class VehicleOut(BaseModel):
    id: str | None
    vin: str | None
    make: str | None
    model: str | None


class AppointmentOut(BaseModel):
    """The 201 body, also the body of ``GET .../appointments/{id}``; instants in UTC with ``Z``."""

    appointment_id: int
    dealership_id: int
    service_type_id: int
    bay_id: int
    technician_id: int
    status: str
    start_at: datetime
    end_at: datetime
    pickup_from: datetime
    timezone: str
    customer: CustomerOut
    vehicle: VehicleOut


class ErrorItem(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ErrorOut(BaseModel):
    """Every non-2xx body; ``errors`` appears only on a schema 422."""

    code: str
    message: str
    errors: list[ErrorItem] | None = None


def error_items(errors: Sequence[Any]) -> list[dict[str, Any]]:
    """``loc``, ``msg``, ``type`` of each pydantic error; ``input``, ``url``, ``ctx`` dropped."""
    return [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in errors]
