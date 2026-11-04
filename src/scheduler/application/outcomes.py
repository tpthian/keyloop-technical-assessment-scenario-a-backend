"""The booking ``Outcome`` and the error bodies the use case stores (design §2, ADR-008).

An ``Outcome`` carries a domain ``code``, never an HTTP status: the interface layer maps code to
status with one table (SPEC-001 Known Facts 8). Error bodies follow the wire format
``{"code": ..., "message": ...}``; ``errors`` belongs to schema 422s only, which happen before
the use case runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from scheduler.domain.attempts import (
    CAPACITY_EXHAUSTED,
    CONFIRMED,
    CONTENTION,
    VEHICLE_ALREADY_BOOKED,
)
from scheduler.domain.model import StoredResponse

VALIDATION = "validation"

_CONFLICT_MESSAGES = {
    CAPACITY_EXHAUSTED: "no free bay and qualified technician for the requested time",
    VEHICLE_ALREADY_BOOKED: "the vehicle already has an appointment overlapping this time",
}


@dataclass(frozen=True)
class Outcome:
    code: str
    body: Mapping[str, object]
    final: bool
    replay: bool = False
    attempts: int = 0
    deadlocks: int = 0
    candidates_pruned: int = 0
    bay_id: int | None = None
    technician_id: int | None = None


def validation_body(message: str) -> dict[str, object]:
    """Body of a business 422 (ADR-008 step 6), stored on the key."""
    return {"code": VALIDATION, "message": message}


def conflict_body(code: str) -> dict[str, object]:
    """Body of a final 409: ``capacity_exhausted`` or ``vehicle_already_booked``."""
    return {"code": code, "message": _CONFLICT_MESSAGES[code]}


def contention_body() -> dict[str, object]:
    """Body of the transient 409; never stored, the claim rolls back (ADR-008)."""
    return {
        "code": CONTENTION,
        "message": "too many concurrent bookings for this time; retry with the same key",
    }


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def replay_outcome(stored: StoredResponse) -> Outcome:
    """The stored outcome of an earlier request with the same key and hash: final, replayed.

    No attempt runs, so the counters stay 0. A replayed ``confirmed`` carries the winning bay
    and technician from the stored body, since its response is a 201 (ADR-013: null only when
    not a 201).
    """
    if stored.code is None or stored.body is None:
        # A committed key row always has its outcome: record runs before COMMIT (ADR-008).
        raise RuntimeError("idempotency key is claimed but carries no recorded outcome")
    bay_id = technician_id = None
    if stored.code == CONFIRMED:
        bay_id = _int_or_none(stored.body.get("bay_id"))
        technician_id = _int_or_none(stored.body.get("technician_id"))
    return Outcome(
        stored.code,
        stored.body,
        final=True,
        replay=True,
        bay_id=bay_id,
        technician_id=technician_id,
    )
