"""TC-28 to TC-30: advisory availability through the API (AC-06, ADR-010).

Requests go through ``create_app`` on the testcontainers database with the clock fixed at the
issue time of the ADR-010 worked example, 2027-03-25T16:00:00Z (Known Facts). Test dealerships
have ids >= 100, in ``Europe/London``, open Mon-Sat 08:00-18:00, Sunday closed; clocks go
forward on Sun 2027-03-28, so Friday and Saturday are GMT and Monday is BST. Seeded service
types: 1 Oil change, 60 min, ``general``; 3 Bodywork, 4,320 min, ``bodywork``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from scheduler.main import create_app
from tests.conftest import make_dealership
from tests.fakes import FixedClock

FIXED_NOW = datetime(2027, 3, 25, 16, 0, tzinfo=UTC)  # issue time of the ADR-010 example
DEALERSHIP = 100
URL = f"/dealerships/{DEALERSHIP}/availability"
GENERAL, BODYWORK = 1, 2  # seeded skills
OIL_CHANGE, BODYWORK_72H = 1, 3  # seeded service types
BAY, TECH = 100, 100


@pytest_asyncio.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(engine=engine, clock=FixedClock(FIXED_NOW))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _one_pair(engine: AsyncEngine) -> None:
    await make_dealership(engine, DEALERSHIP, bays=[BAY], technicians={TECH: [GENERAL, BODYWORK]})


async def _get(
    client: httpx.AsyncClient,
    service_type_id: int = BODYWORK_72H,
    from_: str = "2027-03-26",
    to: str = "2027-03-30",
    url: str = URL,
) -> httpx.Response:
    params = {"service_type_id": service_type_id, "from": from_, "to": to}
    return await client.get(url, params=params)


def _assert_business_422(response: httpx.Response, message: str) -> None:
    assert response.status_code == 422
    assert response.json() == {"code": "validation", "message": message}


def _window(day: str, earliest: str, latest: str) -> dict[str, object]:
    return {
        "bay_id": BAY,
        "technician_id": TECH,
        "date": day,
        "earliest_start": earliest,
        "latest_start": latest,
    }


# TC-28: the request window and the service type are validated; the dealership must exist.


async def test_fifteen_day_window_is_422(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    await _one_pair(engine)
    response = await _get(client, from_="2027-03-26", to="2027-04-10")
    _assert_business_422(response, "from to to spans more than 14 days")


async def test_to_not_after_from_is_422(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    await _one_pair(engine)
    response = await _get(client, from_="2027-03-26", to="2027-03-26")
    _assert_business_422(response, "to must be after from")


async def test_to_beyond_horizon_is_422(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    await _one_pair(engine)
    # today is 2027-03-25 in London; today + 90 days is 2027-06-23
    response = await _get(client, from_="2027-06-20", to="2027-06-24")
    _assert_business_422(response, "to is more than 90 days ahead")


async def test_unknown_service_type_is_422(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    await _one_pair(engine)
    response = await _get(client, service_type_id=999)
    _assert_business_422(response, "service type 999 does not exist")


async def test_unknown_dealership_is_404(client: httpx.AsyncClient) -> None:
    response = await _get(client, url="/dealerships/999/availability")
    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "dealership not found"}


# TC-29: the ADR-010 worked example. E1 ends Fri 09:00 GMT; E2 is Mon 12:00-14:00 BST.

_EXISTING = text(
    "INSERT INTO appointment"
    " (dealership_id, bay_id, technician_id, service_type_id, start_at, end_at, vehicle_key)"
    " VALUES (:d, :bay, :tech, 1, :start, :end, :vehicle)"
)


async def _worked_example(engine: AsyncEngine) -> None:
    await _one_pair(engine)
    async with engine.begin() as conn:
        await conn.execute(
            _EXISTING,
            [
                {
                    "d": DEALERSHIP,
                    "bay": BAY,
                    "tech": TECH,
                    "start": datetime(2027, 3, 26, 8, 0, tzinfo=UTC),
                    "end": datetime(2027, 3, 26, 9, 0, tzinfo=UTC),  # E1
                    "vehicle": "E1",
                },
                {
                    "d": DEALERSHIP,
                    "bay": BAY,
                    "tech": TECH,
                    "start": datetime(2027, 3, 29, 11, 0, tzinfo=UTC),  # E2, 12:00 BST
                    "end": datetime(2027, 3, 29, 13, 0, tzinfo=UTC),  # 14:00 BST
                    "vehicle": "E2",
                },
            ],
        )


async def test_worked_example_returns_exactly_the_two_windows(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _worked_example(engine)
    response = await _get(client)
    assert response.status_code == 200
    body = response.json()
    assert {k: v for k, v in body.items() if k not in ("as_of", "windows")} == {
        "dealership_id": DEALERSHIP,
        "service_type_id": BODYWORK_72H,
        "from": "2027-03-26",
        "to": "2027-03-30",
    }
    assert body["windows"] == [
        _window("2027-03-26", "2027-03-26T09:00:00Z", "2027-03-26T11:00:00Z"),
        _window("2027-03-29", "2027-03-29T13:00:00Z", "2027-03-29T16:59:00Z"),
    ]


async def test_worked_example_as_of_is_aware_utc(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _worked_example(engine)
    as_of = (await _get(client)).json()["as_of"]
    assert as_of.endswith("Z")
    assert datetime.fromisoformat(as_of).utcoffset() == UTC.utcoffset(None)


# TC-30: with no appointments every open day is [opens, closes - 1 min].


async def test_no_appointments_every_open_day_is_opens_to_closes_minus_one_minute(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    response = await _get(client, service_type_id=OIL_CHANGE)
    assert response.status_code == 200
    assert response.json()["windows"] == [
        _window("2027-03-26", "2027-03-26T08:00:00Z", "2027-03-26T17:59:00Z"),  # Fri GMT
        _window("2027-03-27", "2027-03-27T08:00:00Z", "2027-03-27T17:59:00Z"),  # Sat GMT
        _window("2027-03-29", "2027-03-29T07:00:00Z", "2027-03-29T16:59:00Z"),  # Mon BST
    ]


async def test_no_appointments_sunday_is_absent(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    await _one_pair(engine)
    windows = (await _get(client, service_type_id=OIL_CHANGE)).json()["windows"]
    assert "2027-03-28" not in {w["date"] for w in windows}
