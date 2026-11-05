"""TC-21 to TC-27 and TC-40: booking and reading appointments through the API (AC-02, AC-03,
AC-05, AC-08, AC-17).

Requests go through ``create_app`` on the testcontainers database with a fixed clock inside the
90-day horizon. Test dealerships have ids >= 100, in ``Europe/London``, open Mon-Sat 08:00-18:00;
on 2027-03-26 London is on GMT, so local wall time equals UTC. Seeded service types: 1 Oil
change, 60 min, ``general``; 2 Major service, 180 min, ``general``.
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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from scheduler.interfaces.http.limits import MAX_BODY_BYTES
from scheduler.main import create_app
from tests.conftest import booking_body, make_dealership
from tests.fakes import FixedClock

FIXED_NOW = datetime(2027, 3, 25, 16, 0, tzinfo=UTC)  # issue time of the ADR-010 example
DEALERSHIP = 100
URL = f"/dealerships/{DEALERSHIP}/appointments"
GENERAL, BODYWORK = 1, 2  # seeded skills


@pytest_asyncio.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(engine=engine, clock=FixedClock(FIXED_NOW))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _one_pair(engine: AsyncEngine) -> None:
    await make_dealership(engine, DEALERSHIP, bays=[100], technicians={100: [GENERAL]})


async def _book(
    client: httpx.AsyncClient, body: dict[str, Any], key: str | None = None
) -> httpx.Response:
    return await client.post(URL, json=body, headers={"Idempotency-Key": key or str(uuid4())})


async def _stored_code(engine: AsyncEngine, key: str) -> str | None:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT response_code FROM idempotency_key WHERE key = :k"), {"k": key}
        )
        return result.scalar_one_or_none()


async def _stored_business_422(
    client: httpx.AsyncClient, engine: AsyncEngine, body: dict[str, Any]
) -> str:
    """Post ``body``; assert a 422 ``validation`` stored on the key; return the message."""
    key = str(uuid4())
    response = await _book(client, body, key)
    assert response.status_code == 422 and response.json()["code"] == "validation"
    assert "errors" not in response.json()  # a business 422, not a schema 422
    assert await _stored_code(engine, key) == "validation"
    return str(response.json()["message"])


def _booking_events(out: str) -> list[dict[str, Any]]:
    events = [json.loads(line) for line in out.splitlines()]
    return [e for e in events if e["route"] == "book_appointment"]


# TC-21: business validation failures are stored 422s.


async def test_unknown_service_type_is_stored_422(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    message = await _stored_business_422(client, engine, booking_body(service_type_id=999))
    assert message == "service type 999 does not exist"


async def test_no_qualified_technician_is_stored_422(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await make_dealership(engine, DEALERSHIP, bays=[100], technicians={100: [BODYWORK]})
    message = await _stored_business_422(client, engine, booking_body())
    assert message == "no technician is qualified for this service type"


async def test_start_in_the_past_is_stored_422(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    message = await _stored_business_422(
        client, engine, booking_body(start_at="2027-03-25T09:00:00")
    )
    assert message == "start_at is in the past"


async def test_start_beyond_90_days_is_stored_422(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    message = await _stored_business_422(
        client, engine, booking_body(start_at="2027-07-01T09:00:00")
    )
    assert message == "start_at is more than 90 days ahead"


async def test_gap_time_is_stored_422_does_not_exist(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    message = await _stored_business_422(
        client, engine, booking_body(start_at="2027-03-28T01:30:00")
    )
    assert "does not exist" in message


# TC-22: the same vehicle cannot be booked twice at overlapping times.


async def test_same_vin_overlapping_is_409_stored_and_replayed(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await make_dealership(
        engine, DEALERSHIP, bays=[100, 101], technicians={100: [GENERAL], 101: [GENERAL]}
    )
    assert (await _book(client, booking_body())).status_code == 201
    key, overlapping = str(uuid4()), booking_body(start_at="2027-03-26T09:30:00")
    first = await _book(client, overlapping, key)
    replay = await _book(client, overlapping, key)
    assert first.status_code == replay.status_code == 409
    assert first.json()["code"] == "vehicle_already_booked"
    assert replay.json() == first.json()
    assert await _stored_code(engine, key) == "vehicle_already_booked"


async def test_vin_spacing_and_case_normalise(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await make_dealership(
        engine, DEALERSHIP, bays=[100, 101], technicians={100: [GENERAL], 101: [GENERAL]}
    )
    booked = await _book(client, booking_body(vin="WVWZZZ"))
    assert booked.status_code == 201 and booked.json()["vehicle"]["vin"] == "WVWZZZ"
    response = await _book(client, booking_body(vin=" wvw zzz ", start_at="2027-03-26T09:30:00"))
    assert response.status_code == 409 and response.json()["code"] == "vehicle_already_booked"


# TC-23: no free pair -> capacity_exhausted.


async def test_every_pair_busy_is_capacity_exhausted_with_zero_attempts(
    client: httpx.AsyncClient, engine: AsyncEngine, capsys: pytest.CaptureFixture[str]
) -> None:
    await _one_pair(engine)
    assert (await _book(client, booking_body(vin="VINONE"))).status_code == 201
    capsys.readouterr()
    response = await _book(client, booking_body(vin="VINTWO"))
    assert response.status_code == 409 and response.json()["code"] == "capacity_exhausted"
    [event] = _booking_events(capsys.readouterr().out)
    assert (event["code"], event["attempts"], event["final"]) == ("capacity_exhausted", 0, True)


async def test_dealership_without_bays_is_capacity_exhausted(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await make_dealership(engine, DEALERSHIP, technicians={100: [GENERAL]})
    response = await _book(client, booking_body())
    assert response.status_code == 409 and response.json()["code"] == "capacity_exhausted"


# TC-24: tenancy is held by the database (seed: bay 3 and technician 3 belong to dealership 2).

_INSERT = text(
    "INSERT INTO appointment"
    " (dealership_id, bay_id, technician_id, service_type_id, start_at, end_at, vehicle_key)"
    " VALUES (1, :bay, :tech, 1, '2027-03-26T09:00Z', '2027-03-26T10:00Z', 'TENANCY')"
)


async def test_other_dealerships_bay_violates_bay_in_dealership(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError, match="bay_in_dealership"):
        async with engine.begin() as conn:
            await conn.execute(_INSERT, {"bay": 3, "tech": 1})


async def test_other_dealerships_technician_violates_technician_in_dealership(
    engine: AsyncEngine,
) -> None:
    with pytest.raises(IntegrityError, match="technician_in_dealership"):
        async with engine.begin() as conn:
            await conn.execute(_INSERT, {"bay": 1, "tech": 3})


# TC-25: GET one appointment, scoped by dealership.


async def test_get_appointment_returns_the_201_body(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    booked = (await _book(client, booking_body())).json()
    response = await client.get(f"{URL}/{booked['appointment_id']}")
    assert response.status_code == 200 and response.json() == booked


async def test_get_another_dealerships_appointment_is_404(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    await make_dealership(engine, 101, bays=[101], technicians={101: [GENERAL]})
    booked = (await _book(client, booking_body())).json()
    response = await client.get(f"/dealerships/101/appointments/{booked['appointment_id']}")
    assert response.status_code == 404 and response.json()["code"] == "not_found"


async def test_get_unknown_appointment_is_404(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    response = await client.get(f"{URL}/999999")
    assert response.status_code == 404 and response.json()["code"] == "not_found"


# TC-26


async def test_back_to_back_on_one_pair_both_201(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    first = await _book(client, booking_body(vin="VINONE", start_at="2027-03-26T09:00:00"))
    second = await _book(client, booking_body(vin="VINTWO", start_at="2027-03-26T10:00:00"))
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["end_at"] == second.json()["start_at"] == "2027-03-26T10:00:00Z"


# TC-40: request bounds (ADR-014, D-058).


async def test_oversized_body_is_413_and_over_long_string_is_422(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    key = str(uuid4())
    oversized = b" " * (MAX_BODY_BYTES + 1)
    response = await client.post(
        URL,
        content=oversized,
        headers={"Idempotency-Key": key, "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json() == {
        "code": "validation",
        "message": f"request body exceeds {MAX_BODY_BYTES} bytes",
    }
    assert await _stored_code(engine, key) is None

    key = str(uuid4())
    response = await _book(client, booking_body(name="x" * 201), key)
    assert response.status_code == 422
    body = response.json()
    assert (body["code"], body["message"]) == ("validation", "request does not match the schema")
    assert body["errors"] == [
        {
            "loc": ["customer", "name"],
            "msg": "String should have at most 200 characters",
            "type": "string_too_long",
        }
    ]
    assert await _stored_code(engine, key) is None


# TC-27: happy path.


async def test_happy_path_201_body_end_at_and_pickup_from(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    # Major service, 180 min, from Fri 16:00: ends 19:00Z after the 18:00 close, so the car
    # is ready from Saturday's opening, 08:00 GMT.
    response = await _book(client, booking_body(service_type_id=2, start_at="2027-03-26T16:00:00"))
    assert response.status_code == 201, response.json()
    body = response.json()
    assert isinstance(body.pop("appointment_id"), int)
    assert body == {
        "dealership_id": DEALERSHIP,
        "service_type_id": 2,
        "bay_id": 100,
        "technician_id": 100,
        "status": "confirmed",
        "start_at": "2027-03-26T16:00:00Z",
        "end_at": "2027-03-26T19:00:00Z",
        "pickup_from": "2027-03-27T08:00:00Z",
        "timezone": "Europe/London",
        "customer": {"id": "C-42", "email": None, "name": "Sam Lee"},
        "vehicle": {"id": None, "vin": "WVWZZZ1JZXW000001", "make": "VW", "model": "Golf"},
    }


async def test_vehicle_key_is_id_prefixed_when_only_id_given(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    response = await _book(client, booking_body(vehicle_id="V-9", vin=None))
    assert response.status_code == 201, response.json()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT vehicle_key FROM appointment WHERE id = :id"),
            {"id": response.json()["appointment_id"]},
        )
        assert result.scalar_one() == "id:V-9"
