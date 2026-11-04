"""Request dependencies and the use-case container (SPEC-001 § Execution, HTTP layer; ADR-008).

``UseCases`` is built once by ``create_app`` and handed to each router factory
(``build_router(uc)``); handlers close over it. It is never stored on ``app.state``, which holds
only the engine for readiness (Known Facts 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Request

from scheduler.application.book_appointment import BookAppointment
from scheduler.application.get_appointment import GetAppointment
from scheduler.application.get_availability import GetAvailability
from scheduler.application.ports import SchedulingReadRepository
from scheduler.interfaces.http.errors import BadRequest

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"


def idempotency_key(request: Request) -> UUID:
    """The ``Idempotency-Key`` header as a UUID; 400 ``validation`` when missing or not a UUID.

    Resolved before the handler body runs, so a bad key is refused before the JSON is parsed or
    the dealership loaded (ADR-008 step 1). A UUID cannot carry personal data, so the key is
    safe to write into the wide event (ADR-013).
    """
    raw = request.headers.get(IDEMPOTENCY_KEY_HEADER)
    if raw is None:
        raise BadRequest(f"{IDEMPOTENCY_KEY_HEADER} header is required")
    try:
        return UUID(raw)
    except ValueError:
        raise BadRequest(f"{IDEMPOTENCY_KEY_HEADER} must be a UUID") from None


@dataclass(frozen=True)
class UseCases:
    reads: SchedulingReadRepository  # ADR-008 step 2: the dealership is loaded before BEGIN
    book_appointment: BookAppointment
    get_appointment: GetAppointment
    get_availability: GetAvailability
