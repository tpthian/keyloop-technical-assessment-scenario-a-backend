"""TC-32 / AC-10: one wide event per response, schema v1 (design §5, ADR-013).

The app is built here: the events middleware, the health router on a stub engine, and one
stand-in booking route that copies an outcome into ``request.state.ev`` the way the booking
handler does and echoes the customer and vehicle in its body, as the real 201 body does.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from scheduler.interfaces.http import health
from scheduler.interfaces.http.events import WideEventMiddleware
from tests.conftest import booking_body

KEYS = [
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
]
BOOKING_ONLY = [
    "dealership_id",
    "idempotency_key",
    "service_type_id",
    "attempts",
    "deadlocks",
    "candidates_pruned",
    "replay",
    "bay_id",
    "technician_id",
]
EMAIL = "sam.lee@example.com"
VIN = "WVWZZZ1JZXW000001"
URL = "/dealerships/1/appointments"

# code -> (status, fields the booking handler copies from its Outcome); None: schema 422,
# raised before the use case runs, so only the error handler's code reaches the event.
SCENARIOS: dict[str, tuple[int, dict[str, Any] | None]] = {
    "confirmed": (201, {"final": True, "attempts": 2, "deadlocks": 1, "bay_id": 2}),
    "capacity_exhausted": (409, {"final": True, "attempts": 3, "candidates_pruned": 4}),
    "contention": (409, {"final": False, "attempts": 5, "candidates_pruned": 2}),
    "validation": (422, None),
}


class _Conn:
    async def exec_driver_sql(self, statement: str) -> Any:
        return None


class _Engine:
    @asynccontextmanager
    async def connect(self) -> AsyncIterator[_Conn]:
        yield _Conn()


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(WideEventMiddleware)
    app.include_router(health.build_router(_Engine()))

    @app.post("/dealerships/{dealership_id}/appointments", name="book_appointment")
    async def book(dealership_id: int, scenario: str, request: Request) -> JSONResponse:
        raw = await request.json()
        ev = request.state.ev
        ev["idempotency_key"] = request.headers["Idempotency-Key"]
        status, outcome = SCENARIOS[scenario]
        ev["code"] = scenario
        if outcome is not None:
            ev["service_type_id"] = raw["service_type_id"]
            defaults = {"replay": False, "deadlocks": 0, "candidates_pruned": 0}
            ev.update({**defaults, "bay_id": None, "technician_id": None, **outcome})
        body = {"code": scenario, "customer": raw["customer"], "vehicle": raw["vehicle"]}
        return JSONResponse(body, status_code=status)

    return app


async def _events(capsys: pytest.CaptureFixture[str], *scenarios: str) -> list[str]:
    """Book once per scenario, then hit both health routes; return the stdout lines."""
    capsys.readouterr()
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for scenario in scenarios:
            await client.post(
                URL,
                params={"scenario": scenario},
                json=booking_body(email=EMAIL, vin=VIN),
                headers={"Idempotency-Key": str(uuid4())},
            )
        await client.get("/health/live")
        await client.get("/health/ready")
    return capsys.readouterr().out.splitlines()


def _by_code(lines: list[str]) -> dict[str | None, dict[str, Any]]:
    events = [json.loads(line) for line in lines]
    return {e["code"]: e for e in events if e["route"] == "book_appointment"}


async def test_one_line_per_response(capsys: pytest.CaptureFixture[str]) -> None:
    lines = await _events(capsys, *SCENARIOS)
    assert len(lines) == len(SCENARIOS) + 2
    assert all(isinstance(json.loads(line), dict) for line in lines)


async def test_seventeen_keys_in_order_and_version_1(capsys: pytest.CaptureFixture[str]) -> None:
    for line in await _events(capsys, *SCENARIOS):
        event = json.loads(line)
        assert list(event) == KEYS
        assert event["v"] == 1


async def test_final_true_for_201_final_409_and_422(capsys: pytest.CaptureFixture[str]) -> None:
    events = _by_code(await _events(capsys, "confirmed", "capacity_exhausted", "validation"))
    assert {code: (e["outcome"], e["final"]) for code, e in events.items()} == {
        "confirmed": (201, True),
        "capacity_exhausted": (409, True),
        "validation": (422, True),
    }


async def test_final_false_for_contention(capsys: pytest.CaptureFixture[str]) -> None:
    event = _by_code(await _events(capsys, "contention"))["contention"]
    assert (event["outcome"], event["final"], event["attempts"]) == (409, False, 5)


async def test_health_lines_carry_null_booking_fields(capsys: pytest.CaptureFixture[str]) -> None:
    events = [json.loads(line) for line in await _events(capsys)]
    assert [(e["route"], e["outcome"], e["code"], e["final"]) for e in events] == [
        ("health_live", 200, None, True),
        ("health_ready", 200, None, True),
    ]
    assert all(e[key] is None for e in events for key in BOOKING_ONLY)


async def test_no_email_or_vin_in_any_line(capsys: pytest.CaptureFixture[str]) -> None:
    lines = await _events(capsys, *SCENARIOS)
    assert lines
    assert [line for line in lines if "@" in line or VIN in line] == []
