"""One wide event per request (design §5, ADR-013, schema v1).

``WideEventMiddleware`` is a plain ASGI middleware. It puts ``request.state.ev`` in place with
the 17 keys of schema v1 in order, lets handlers fill the fields they own, times the call and
writes exactly one JSON line to ``sys.stdout`` when the call ends, including when the call
raises. Only the 17 keys are written, whatever else a handler put in the dict, so the event
carries identifiers only and never an email, VIN or ``vehicle_key``.

Defaults filled by the middleware: ``route`` from the matched route name; ``outcome`` from the
response status; ``dealership_id`` from an integer ``dealership_id`` path parameter; ``final``
false for any 5xx and otherwise true unless the handler set it; ``latency_ms``. An unhandled
exception becomes a 500 ``error`` event with ``final`` false; the middleware answers with the
error body when no response has started, then re-raises so the server logs the traceback on
stderr.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Awaitable, Callable, MutableMapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

SCHEMA_VERSION = 1
EVENT_KEYS: tuple[str, ...] = (
    "v",
    "ts",
    "request_id",
    "route",
    "outcome",
    "code",
    "final",
    "dealership_id",
    "idempotency_key",
    "service_type_id",
    "attempts",
    "deadlocks",
    "candidates_pruned",
    "replay",
    "bay_id",
    "technician_id",
    "latency_ms",
)
UNMATCHED_ROUTE = "unmatched"  # no route matched, e.g. a 404 on an unknown path
ERROR_BODY = b'{"code":"error","message":"internal error"}'


def new_event() -> dict[str, Any]:
    """A schema v1 event with every key present, in order; ``v``, ``ts``, ``request_id`` set."""
    ev: dict[str, Any] = dict.fromkeys(EVENT_KEYS)
    ev["v"] = SCHEMA_VERSION
    ev["ts"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ev["request_id"] = str(uuid4())
    return ev


def _route_name(scope: Scope) -> str:
    name = getattr(scope.get("route"), "name", None)
    return name if isinstance(name, str) and name else UNMATCHED_ROUTE


def _dealership_id(scope: Scope) -> int | None:
    raw = (scope.get("path_params") or {}).get("dealership_id")
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None  # never copy a non-identifier from the path into the event


def emit(ev: MutableMapping[str, Any]) -> None:
    """Write one JSON line with exactly the 17 schema keys, in order, to the current stdout."""
    line = json.dumps({key: ev.get(key) for key in EVENT_KEYS}, separators=(",", ":"))
    print(line, file=sys.stdout, flush=True)


class WideEventMiddleware:
    """Mount with ``app.add_middleware(WideEventMiddleware)``."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ev = new_event()
        scope.setdefault("state", {})["ev"] = ev  # read back by handlers as request.state.ev
        status: int | None = None
        started = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            ev["code"] = "error"
            ev["final"] = False
            if status is None:  # nothing sent yet: answer with the error body
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": ERROR_BODY})
            status = 500  # the event records 500 even if a response had already started
            raise
        finally:
            _finish(ev, scope, 500 if status is None else status, started)
            emit(ev)


def _finish(ev: dict[str, Any], scope: Scope, status: int, started: float) -> None:
    ev["outcome"] = status
    if ev["route"] is None:
        ev["route"] = _route_name(scope)
    if ev["dealership_id"] is None:
        ev["dealership_id"] = _dealership_id(scope)
    if status >= 500:
        ev["final"] = False  # 5xx is transient (ADR-013)
        if ev["code"] is None:
            ev["code"] = "error"
    elif ev["final"] is None:
        ev["final"] = True
    ev["latency_ms"] = round((time.perf_counter() - started) * 1000)
