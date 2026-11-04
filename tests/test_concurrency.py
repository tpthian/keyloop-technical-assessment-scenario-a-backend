"""TC-20, TC-31 and TC-39 / AC-07, AC-16: concurrency evidence (design §3, §5, V-002, ADR-004,
ADR-013).

Every test runs through ``create_app`` on the testcontainers database, so every request takes
the production path: the booking transaction with its ``SET LOCAL`` retry policy (bound 5,
``deadlock_timeout`` 100 ms; L-002), the dealership advisory lock after the key claim, one
savepoint per attempt, three exclusion constraints. Requests are concurrent coroutines on one
event loop, each on its own pooled connection.

TC-31 uses a test-owned dealership of 4 bays x 4 qualified technicians (ids >= 100; D-044):
the seed's 2 x 2 allows only 2 concurrent winners. A client-side barrier releases the 8
clients together before they send (D-049); no attempt gate is injected, because a gate inside
the transaction would deadlock against the advisory lock taken before it. Inside the service
the bookings of the dealership queue on that lock (ADR-004 amendment, D-048), so no 40P01 is
expected and the split is exact. The SQLSTATE rule of L-001 still holds: any mix of 23P01 and
40P01 is accepted, the invariant is what is asserted.

TC-39 proves the retry loop as the fallback behind the lock (D-050): the attempt gate stands
for a writer that bypasses the lock and commits a conflicting appointment between the
candidate read and the first INSERT.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncEngine

from scheduler.application.ports import AttemptGate
from scheduler.domain.model import Candidate, Customer, NewAppointment, Vehicle
from scheduler.infrastructure.postgres.repositories import row_of
from scheduler.infrastructure.postgres.schema import appointment
from scheduler.main import create_app
from tests.conftest import booking_body, make_dealership, overlap_count
from tests.fakes import FixedClock

FIXED_NOW = datetime(2027, 3, 25, 16, 0, tzinfo=UTC)  # inside the horizon of the default slot
DEALERSHIP = 100
URL = f"/dealerships/{DEALERSHIP}/appointments"
GENERAL = 1  # seeded skill required by service type 1 (Oil change, 60 min)
# The slot of booking_body(): 2027-03-26 09:00 Europe/London, 60 minutes.
SLOT_START = datetime(2027, 3, 26, 9, 0, tzinfo=ZoneInfo("Europe/London")).astimezone(UTC)
SLOT_END = SLOT_START + timedelta(minutes=60)
BYPASS_VIN = "BYPASSVIN0000001"


def _book_events(out: str) -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in out.splitlines() if '"book_appointment"' in ln]


async def test_parallel_same_key_same_body_books_once(engine: AsyncEngine) -> None:
    """TC-20: the second claim waits on the first's key row, then replays its stored 201."""
    await make_dealership(engine, DEALERSHIP, bays=[100], technicians={100: [GENERAL]})
    app = create_app(engine=engine, clock=FixedClock(FIXED_NOW))
    headers = {"Idempotency-Key": str(uuid4())}
    body = booking_body()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first, second = await asyncio.gather(
            client.post(URL, json=body, headers=headers),
            client.post(URL, json=body, headers=headers),
        )

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json() == second.json()  # same body, so the same appointment_id
    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT id FROM appointment"))).scalars().all()
        keys = (await conn.execute(text("SELECT count(*) FROM idempotency_key"))).scalar_one()
    assert list(rows) == [first.json()["appointment_id"]]
    assert keys == 1


async def test_v002_race_eight_clients_four_pairs(
    engine: AsyncEngine, capsys: pytest.CaptureFixture[str]
) -> None:
    """TC-31: production retry policy (bound 5, deadlock_timeout 100 ms); either SQLSTATE
    accepted (L-001).

    The clients are released together by a barrier before they send (D-049); inside the service
    the bookings of the dealership queue on the advisory lock (ADR-004 amendment, D-048), so no
    attempt gate is injected and no 40P01 is expected.
    """
    bays = [100, 101, 102, 103]
    await make_dealership(
        engine, DEALERSHIP, bays=bays, technicians={t: [GENERAL] for t in (100, 101, 102, 103)}
    )
    n, pairs = 8, 4
    app = create_app(engine=engine, clock=FixedClock(FIXED_NOW))
    start = asyncio.Barrier(n)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:

        async def one(i: int) -> httpx.Response:
            async with asyncio.timeout(10):
                await start.wait()
            return await client.post(
                URL,
                json=booking_body(vin=f"RACEVIN{i:02d}"),
                headers={"Idempotency-Key": str(uuid4())},
            )

        started = time.perf_counter()
        responses = await asyncio.gather(*(one(i) for i in range(n)))
        elapsed_ms = (time.perf_counter() - started) * 1000

    statuses = Counter(r.status_code for r in responses)
    assert statuses == {201: pairs, 409: n - pairs}, [r.json() for r in responses]
    winners = [r.json() for r in responses if r.status_code == 201]
    assert len({w["bay_id"] for w in winners}) == pairs
    assert len({w["technician_id"] for w in winners}) == pairs
    assert all(r.json()["code"] == "capacity_exhausted" for r in responses if r.status_code == 409)
    assert await overlap_count(engine) == 0
    async with engine.connect() as conn:
        booked = (await conn.execute(text("SELECT count(*) FROM appointment"))).scalar_one()
        keys = (
            await conn.execute(text("SELECT count(*), count(response_code) FROM idempotency_key"))
        ).one()
    assert booked == pairs
    assert tuple(keys) == (n, n)  # every key row committed with its recorded response

    evs = _book_events(capsys.readouterr().out)
    attempts = sum(e["attempts"] for e in evs)
    assert len(evs) == n and attempts == pairs  # serialised: one per winner, no retries
    assert all(e["attempts"] == 0 for e in evs if e["code"] == "capacity_exhausted")
    deadlocks = sum(e["deadlocks"] for e in evs)
    pruned = sum(e["candidates_pruned"] for e in evs)
    with capsys.disabled():  # capsys captures stdout even under -s; the evidence line must show
        print(
            f"\nV-002: {n} clients, {pairs} pairs, statuses={dict(sorted(statuses.items()))},"
            f" attempts={attempts}, deadlocks={deadlocks}, candidates_pruned={pruned},"
            f" max latency_ms={max(e['latency_ms'] for e in evs)}, wall={elapsed_ms:.0f} ms,"
            " overlaps=0"
        )


def _bypass_gate(
    engine: AsyncEngine, dealership_id: int, bay_id: int, technician_id: int
) -> AttemptGate:
    """An attempt gate that commits, on its own connection and without the dealership lock, an
    appointment occupying ``bay_id`` for the slot of ``booking_body()`` (D-050)."""
    new = NewAppointment(
        dealership_id,
        GENERAL,  # service type 1
        SLOT_START,
        SLOT_END,
        Customer(id="C-BYPASS", email=None, name="Bypass writer"),
        Vehicle(id=None, vin=BYPASS_VIN, make="VW", model="Polo"),
        BYPASS_VIN,
    )
    row = row_of(new, Candidate(bay_id, technician_id))

    async def gate() -> None:
        async with engine.begin() as conn:
            await conn.execute(insert(appointment).values(row))

    return gate


async def _book_once(app: FastAPI, dealership_id: int) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(
            f"/dealerships/{dealership_id}/appointments",
            json=booking_body(),
            headers={"Idempotency-Key": str(uuid4())},
        )


async def test_retry_fallback_when_a_writer_bypasses_the_lock(
    engine: AsyncEngine, capsys: pytest.CaptureFixture[str]
) -> None:
    """TC-39: a writer around the lock costs one attempt per lost resource (AC-16, D-050).

    One app per case, so each gate writes into the dealership it serves. The bypass row's
    technician holds no skill and is never a candidate: the row takes the bay only.
    """
    # (a) 2 bays x 1 qualified technician; the bypass takes bay 100, bay 101 stays free.
    await make_dealership(
        engine, DEALERSHIP, bays=[100, 101], technicians={100: [GENERAL], 109: []}
    )
    app_a = create_app(
        engine=engine,
        clock=FixedClock(FIXED_NOW),
        attempt_gate=_bypass_gate(engine, DEALERSHIP, 100, 109),
    )
    first = await _book_once(app_a, DEALERSHIP)
    assert first.status_code == 201, first.json()
    assert first.json()["bay_id"] == 101
    (ev_a,) = _book_events(capsys.readouterr().out)
    assert ev_a["attempts"] == 1 + ev_a["candidates_pruned"]  # the shuffle may try bay 100 first
    assert ev_a["candidates_pruned"] <= 1
    assert ev_a["deadlocks"] == 0

    # (b) 1 bay x 1 qualified technician; the bypass takes the only bay.
    await make_dealership(engine, 110, bays=[110], technicians={110: [GENERAL], 119: []})
    app_b = create_app(
        engine=engine,
        clock=FixedClock(FIXED_NOW),
        attempt_gate=_bypass_gate(engine, 110, 110, 119),
    )
    second = await _book_once(app_b, 110)
    assert second.status_code == 409, second.json()
    assert second.json()["code"] == "capacity_exhausted"
    (ev_b,) = _book_events(capsys.readouterr().out)
    assert ev_b["attempts"] == 1
    assert ev_b["candidates_pruned"] == 1

    assert await overlap_count(engine) == 0
    async with engine.connect() as conn:
        booked = (await conn.execute(text("SELECT count(*) FROM appointment"))).scalar_one()
    assert booked == 3  # the two bypass rows and the booking of case (a)
