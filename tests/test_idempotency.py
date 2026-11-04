"""TC-15 to TC-19, TC-37 / AC-04: the idempotency boundary at the HTTP layer (ADR-008).

Requests go through ``create_app`` on the testcontainers database with a fixed clock inside the
90-day horizon. Responses of ADR-008 steps 1 to 3 (400, 404, schema 422) must leave no key row;
business 422 and 201 are stored and replayed.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from scheduler.main import create_app
from tests.conftest import booking_body, make_dealership
from tests.fakes import FixedClock

FIXED_NOW = datetime(2027, 3, 25, 16, 0, tzinfo=UTC)  # issue time of the ADR-010 example
DEALERSHIP = 100
URL = f"/dealerships/{DEALERSHIP}/appointments"
UNKNOWN_URL = "/dealerships/999/appointments"


@pytest_asyncio.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    await make_dealership(engine, DEALERSHIP, bays=[100], technicians={100: [1]})
    app = create_app(engine=engine, clock=FixedClock(FIXED_NOW))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid4())}


async def _key_rows(engine: AsyncEngine) -> list[tuple[Any, ...]]:
    async with engine.connect() as conn:
        rows = await conn.execute(text("SELECT key, response_code FROM idempotency_key"))
        return [tuple(r) for r in rows]


async def _appointment_count(engine: AsyncEngine) -> int:
    async with engine.connect() as conn:
        return int((await conn.execute(text("SELECT count(*) FROM appointment"))).scalar_one())


async def _post_raw(client: httpx.AsyncClient, url: str, content: bytes) -> httpx.Response:
    headers = {**_key(), "Content-Type": "application/json"}
    return await client.post(url, content=content, headers=headers)


async def _schema_422(client: httpx.AsyncClient, engine: AsyncEngine, body: Any) -> None:
    response = await client.post(URL, json=body, headers=_key())
    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "validation" and payload["errors"]
    assert all(set(item) == {"loc", "msg", "type"} for item in payload["errors"])
    assert await _key_rows(engine) == []


# TC-15: malformed JSON, missing key, non-UUID key -> 400, no key row.


async def test_malformed_json_is_400_without_key_row(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    response = await _post_raw(client, URL, b'{"service_type_id": 1,')
    assert response.status_code == 400 and response.json()["code"] == "validation"
    assert await _key_rows(engine) == []


async def test_missing_key_is_400_without_key_row(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    response = await client.post(URL, json=booking_body())
    assert response.status_code == 400 and response.json()["code"] == "validation"
    assert await _key_rows(engine) == []


async def test_non_uuid_key_is_400_without_key_row(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    response = await client.post(URL, json=booking_body(), headers={"Idempotency-Key": "abc-1"})
    assert response.status_code == 400 and response.json()["code"] == "validation"
    assert await _key_rows(engine) == []


# TC-16


async def test_unknown_dealership_is_404_without_key_row(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    response = await client.post(UNKNOWN_URL, json=booking_body(), headers=_key())
    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "dealership not found"}
    assert await _key_rows(engine) == []


# TC-17: schema 422 with errors and no key row; a corrected body under the same key -> 201.


async def test_schema_422_no_identifier(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    await _schema_422(client, engine, booking_body(customer_id=None, email=None))


async def test_schema_422_unknown_field(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    await _schema_422(client, engine, {**booking_body(), "priority": "high"})


async def test_schema_422_offset(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    await _schema_422(client, engine, booking_body(start_at="2027-03-26T09:00:00+00:00"))


async def test_schema_422_seconds(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    await _schema_422(client, engine, booking_body(start_at="2027-03-26T09:00:30"))


async def test_corrected_body_under_same_key_is_201(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    key = _key()
    invalid = await client.post(URL, json=booking_body(customer_id=None), headers=key)
    assert invalid.status_code == 422
    corrected = await client.post(URL, json=booking_body(), headers=key)
    assert corrected.status_code == 201, corrected.json()


# TC-18: business 422 (outside hours) is stored on the key.


async def test_business_422_replays_for_same_body(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    key, body = _key(), booking_body(start_at="2027-03-26T19:00:00")
    first = await client.post(URL, json=body, headers=key)
    second = await client.post(URL, json=body, headers=key)
    assert first.status_code == second.status_code == 422
    assert (
        first.json()
        == second.json()
        == {
            "code": "validation",
            "message": "start_at is outside opening hours",
        }
    )
    assert [code for _, code in await _key_rows(engine)] == ["validation"]


async def test_business_422_key_with_different_body_is_replay_conflict(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    key = _key()
    await client.post(URL, json=booking_body(start_at="2027-03-26T19:00:00"), headers=key)
    response = await client.post(URL, json=booking_body(), headers=key)
    assert response.status_code == 422 and response.json()["code"] == "replay_conflict"
    assert [code for _, code in await _key_rows(engine)] == ["validation"]  # row unchanged


# TC-19: a 201 replays with the same status and body, and one appointment row.


async def test_201_replays_same_status_and_body_one_row(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    key = _key()
    first = await client.post(URL, json=booking_body(), headers=key)
    second = await client.post(URL, json=booking_body(), headers=key)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert await _appointment_count(engine) == 1


async def test_201_replay_event_has_replay_true(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    key = _key()
    capsys.readouterr()
    await client.post(URL, json=booking_body(), headers=key)
    await client.post(URL, json=booking_body(), headers=key)
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    booking = [e for e in events if e["route"] == "book_appointment"]
    assert [(e["outcome"], e["replay"]) for e in booking] == [(201, False), (201, True)]


# TC-37: ADR-008 precedence on an unknown dealership.


async def test_unknown_dealership_beats_schema_invalid_body(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    body = {**booking_body(customer_id=None, email=None), "priority": "high"}
    response = await client.post(UNKNOWN_URL, json=body, headers=_key())
    assert response.status_code == 404 and response.json()["code"] == "not_found"
    assert await _key_rows(engine) == []


async def test_malformed_json_on_unknown_dealership_is_400(client: httpx.AsyncClient) -> None:
    response = await _post_raw(client, UNKNOWN_URL, b"not json")
    assert response.status_code == 400 and response.json()["code"] == "validation"


async def test_missing_key_on_unknown_dealership_is_400(client: httpx.AsyncClient) -> None:
    response = await client.post(UNKNOWN_URL, json=booking_body())
    assert response.status_code == 400 and response.json()["code"] == "validation"
