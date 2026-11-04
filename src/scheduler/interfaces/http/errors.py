"""Code to status, and the error body of every non-2xx (SPEC-001 Wire formats, ADR-008).

``STATUS_OF_CODE`` is the one table mapping a domain code to an HTTP status (Known Facts 8): the
application layer stores and returns codes only. The handlers below turn the exceptions of the
request path into ``{"code", "message", "errors"?}`` bodies and write the code into the wide
event, so every error line carries its ``code`` (ADR-013). ``errors`` appears only on a schema
422 and holds ``loc``, ``msg`` and ``type`` per item.

Responses of ADR-008 steps 1 to 3 (400 malformed JSON or key, 404 unknown dealership, schema
422) are produced here and never reach the idempotency store.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from scheduler.domain.errors import NotFound, ReplayConflict, ValidationFailed
from scheduler.interfaces.http.schemas import error_items

VALIDATION = "validation"
NOT_FOUND = "not_found"
REPLAY_CONFLICT = "replay_conflict"

STATUS_OF_CODE: Mapping[str, int] = {
    "confirmed": 201,
    VALIDATION: 422,  # schema 422 before BEGIN and business 422 after the claim; 400s are below
    NOT_FOUND: 404,
    REPLAY_CONFLICT: 422,
    "capacity_exhausted": 409,
    "vehicle_already_booked": 409,
    "contention": 409,  # with Retry-After: 1, set by the booking handler
    "error": 500,
}
BAD_REQUEST = 400  # malformed JSON, missing or non-UUID Idempotency-Key: code ``validation``
SCHEMA_MESSAGE = "request does not match the schema"


class BadRequest(Exception):  # noqa: N818 (a 400, named for the status it answers)
    """A request refused before anything else is read: missing or non-UUID key (ADR-008 step 1)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def error_response(
    request: Request,
    status: int,
    code: str,
    message: str,
    errors: Sequence[Mapping[str, Any]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """The wire error body; records ``code`` on the request's wide event."""
    ev = getattr(request.state, "ev", None)
    if ev is not None:
        ev["code"] = code
    body: dict[str, Any] = {"code": code, "message": message}
    if errors is not None:
        body["errors"] = list(errors)
    return JSONResponse(body, status_code=status, headers=dict(headers) if headers else None)


async def _bad_request(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, BadRequest)
    return error_response(request, BAD_REQUEST, VALIDATION, exc.message)


async def _malformed_json(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, json.JSONDecodeError)
    message = f"json_invalid: request body is not valid JSON ({exc.msg} at position {exc.pos})"
    return error_response(request, BAD_REQUEST, VALIDATION, message)


async def _schema_invalid(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ValidationError | RequestValidationError)
    errors = error_items(exc.errors())
    return error_response(request, STATUS_OF_CODE[VALIDATION], VALIDATION, SCHEMA_MESSAGE, errors)


async def _not_found(request: Request, exc: Exception) -> JSONResponse:
    return error_response(request, STATUS_OF_CODE[NOT_FOUND], NOT_FOUND, str(exc))


async def _replay_conflict(request: Request, exc: Exception) -> JSONResponse:
    message = "idempotency key was already used with a different request"
    return error_response(request, STATUS_OF_CODE[REPLAY_CONFLICT], REPLAY_CONFLICT, message)


async def _validation_failed(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ValidationFailed)
    return error_response(request, STATUS_OF_CODE[VALIDATION], VALIDATION, exc.message)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    """Framework 4xx (unknown path, method not allowed) in the wire error body."""
    assert isinstance(exc, StarletteHTTPException)
    code = NOT_FOUND if exc.status_code == 404 else VALIDATION
    return error_response(request, exc.status_code, code, str(exc.detail), headers=exc.headers)


def register_handlers(app: FastAPI) -> None:
    """Mount every handler; a domain error not listed here is a 5xx through the middleware."""
    app.add_exception_handler(BadRequest, _bad_request)
    app.add_exception_handler(json.JSONDecodeError, _malformed_json)
    app.add_exception_handler(ValidationError, _schema_invalid)
    app.add_exception_handler(RequestValidationError, _schema_invalid)
    app.add_exception_handler(NotFound, _not_found)
    app.add_exception_handler(ReplayConflict, _replay_conflict)
    app.add_exception_handler(ValidationFailed, _validation_failed)
    app.add_exception_handler(StarletteHTTPException, _http_error)
