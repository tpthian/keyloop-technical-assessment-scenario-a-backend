"""Appointment routes: book and read (design §3, ADR-008 steps 1 to 4, Known Facts 9).

The booking route declares no typed body parameter, so FastAPI validates nothing before the
handler runs and the ADR-008 order holds: key (dependency) and JSON parse → load the dealership
(404) → schema validation (422) → command → ``BookAppointment.execute`` with the loaded
dealership. ``openapi_extra`` carries ``BookingRequest``'s schema for ``/docs``.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import ValidationError

from scheduler.domain.errors import NotFound
from scheduler.interfaces.http.dependencies import UseCases, idempotency_key
from scheduler.interfaces.http.errors import STATUS_OF_CODE
from scheduler.interfaces.http.schemas import AppointmentOut, BookingRequest, ErrorOut, to_command


def _inline_defs(schema: dict[str, Any]) -> dict[str, Any]:
    """Replace every ``#/$defs/<name>`` reference with the definition itself.

    ``openapi_extra`` places the schema inside ``requestBody``, where Swagger UI cannot resolve
    Pydantic's ``$defs`` block; inlining keeps one self-contained schema in the contract.
    """
    defs: dict[str, Any] = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                return walk(defs[ref.removeprefix("#/$defs/")])
            return {k: walk(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    result: dict[str, Any] = walk(schema)
    return result


BOOKING_BODY: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {"schema": _inline_defs(BookingRequest.model_json_schema())}
        },
    }
}
BOOKING_RESPONSES: dict[int | str, dict[str, Any]] = {
    201: {"model": AppointmentOut},
    **{status: {"model": ErrorOut} for status in (400, 404, 409, 413, 422)},
}
OUTCOME_FIELDS = (
    "code",
    "final",
    "replay",
    "attempts",
    "deadlocks",
    "candidates_pruned",
    "bay_id",
    "technician_id",
)


def build_router(uc: UseCases) -> APIRouter:
    router = APIRouter(prefix="/dealerships/{dealership_id}/appointments")

    @router.post(
        "",
        status_code=201,
        name="book_appointment",
        openapi_extra=BOOKING_BODY,
        responses=BOOKING_RESPONSES,
    )
    async def book_appointment(
        dealership_id: int,
        request: Request,
        response: Response,
        key: Annotated[UUID, Depends(idempotency_key)],  # ADR-008 step 1: header first
        idempotency_key_header: Annotated[
            str | None,
            Header(
                alias="Idempotency-Key",
                description="Client UUID; the same key replays the stored response (ADR-008)",
            ),
        ] = None,  # declared for the OpenAPI contract and Swagger UI only; `key` enforces it
    ) -> dict[str, Any]:
        del idempotency_key_header
        return await _book(uc, dealership_id, request, response, key)

    @router.get(
        "/{appointment_id}",
        name="get_appointment",
        responses={200: {"model": AppointmentOut}, 404: {"model": ErrorOut}},
    )
    async def get_appointment(dealership_id: int, appointment_id: int) -> dict[str, Any]:
        return dict(await uc.get_appointment.execute(dealership_id, appointment_id))

    return router


async def _book(
    uc: UseCases, dealership_id: int, request: Request, response: Response, key: UUID
) -> dict[str, Any]:
    ev = request.state.ev
    ev["route"] = "book_appointment"
    ev["idempotency_key"] = str(key)  # a valid UUID; null only when missing or invalid (ADR-013)
    raw = await request.json()  # step 1: json.JSONDecodeError -> 400 (errors.py)
    dealership = await uc.reads.dealership(dealership_id)
    if dealership is None:  # step 2: before schema validation
        raise NotFound("dealership")  # -> 404 not_found (errors.py)
    try:
        req = BookingRequest.model_validate(raw)  # step 3: pydantic.ValidationError -> 422
    except ValidationError as exc:
        raise exc  # handled in errors.py; explicit for readers
    ev["service_type_id"] = req.service_type_id  # null before schema validation (ADR-013)
    cmd = to_command(req, dealership_id, key)  # step 4: command carries no HTTP types
    outcome = await uc.book_appointment.execute(cmd, dealership)  # steps 5-7 inside the use case
    for field in OUTCOME_FIELDS:
        ev[field] = getattr(outcome, field)
    response.status_code = STATUS_OF_CODE[outcome.code]
    if outcome.code == "contention":
        response.headers["Retry-After"] = "1"
    return dict(outcome.body)
