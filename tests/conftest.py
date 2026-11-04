"""Test harness on testcontainers (ADR-002).

One PostgreSQL 16 container per session, migrated with ``alembic upgrade head`` exactly as
``make migrate`` does, so the tests run against the real DDL. Each test gets a fresh async
engine (SQLAlchemy 2 asyncio + psycopg) on that database; rows the tests write are removed
before and after every test, while reference rows below id 100 (the seed, T3) are kept.

Helpers for later test modules (import them from ``tests.conftest``): ``make_dealership``,
``booking_body``, ``overlap_count``, ``barrier_gate``.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping, Sequence
from datetime import time
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.community.postgres import PostgresContainer

ROOT = Path(__file__).resolve().parent.parent
POSTGRES_IMAGE = "postgres:16-alpine"  # the compose image (docker-compose.yml)
FIXTURE_ID_FLOOR = 100  # test-owned rows use ids >= 100; the seed stays below

# Mon-Sat 08:00-18:00, Sunday closed: the hours of seeded dealership 1 (T3).
DEFAULT_HOURS: Mapping[int, tuple[time, time]] = {
    weekday: (time(8, 0), time(18, 0)) for weekday in range(6)
}

_CLEANUP: tuple[str, ...] = (
    "TRUNCATE appointment, idempotency_key",
    "DELETE FROM technician_skill WHERE technician_id >= :floor OR skill_id >= :floor",
    "DELETE FROM service_type_required_skill WHERE service_type_id >= :floor OR skill_id >= :floor",
    "DELETE FROM technician WHERE id >= :floor OR dealership_id >= :floor",
    "DELETE FROM service_bay WHERE id >= :floor OR dealership_id >= :floor",
    "DELETE FROM opening_hours WHERE dealership_id >= :floor",
    "DELETE FROM service_type WHERE id >= :floor",
    "DELETE FROM skill WHERE id >= :floor",
    "DELETE FROM dealership WHERE id >= :floor",
)

# design §5 / ADR-013: overlapping appointments per bay, per technician, per vehicle_key.
# Must be 0 whatever happened; the exclusion constraints make any other value impossible.
OVERLAP_SQL = """
SELECT count(*) FROM appointment a JOIN appointment b ON a.id < b.id
 AND (a.bay_id = b.bay_id
      OR a.technician_id = b.technician_id
      OR (a.dealership_id = b.dealership_id AND a.vehicle_key = b.vehicle_key))
 AND tstzrange(a.start_at, a.end_at) && tstzrange(b.start_at, b.end_at)
"""


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """Start PostgreSQL 16, run ``alembic upgrade head`` against it, yield its psycopg URL."""
    with PostgresContainer(POSTGRES_IMAGE, driver="psycopg") as pg:
        url = pg.get_connection_url()
        # migrations/env.py reads DATABASE_URL through scheduler.settings, as in production.
        # A subprocess keeps Alembic's logging configuration out of the test process.
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env={**os.environ, "DATABASE_URL": url},
            check=True,
            capture_output=True,
            text=True,
        )
        yield url


async def _clean(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for statement in _CLEANUP:
            await conn.execute(text(statement), {"floor": FIXTURE_ID_FLOOR})


@pytest_asyncio.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    """Async engine on the migrated database; test rows removed before and after the test.

    Pool sized as production (``pool_size=10, max_overflow=10``) so the race test runs.
    """
    eng = create_async_engine(database_url, pool_size=10, max_overflow=10)
    try:
        await _clean(eng)
        yield eng
        await _clean(eng)
    finally:
        await eng.dispose()


async def make_dealership(
    engine: AsyncEngine,
    dealership_id: int,
    *,
    timezone: str = "Europe/London",
    hours: Mapping[int, tuple[time, time]] | None = None,
    bays: Sequence[int] = (),
    technicians: Mapping[int, Sequence[int]] | None = None,
) -> None:
    """Write a test dealership (id >= 100) with its hours, bays and technicians.

    ``hours`` maps weekday (0 = Monday) to ``(opens_at, closes_at)``; a missing weekday is
    closed; default Mon-Sat 08:00-18:00. ``technicians`` maps technician id to the skill ids it
    holds (skills must exist, e.g. the seeded ``general`` = 1, ``bodywork`` = 2).
    """
    ids = [dealership_id, *bays, *(technicians or {})]
    if min(ids) < FIXTURE_ID_FLOOR:
        raise ValueError(f"fixture ids must be >= {FIXTURE_ID_FLOOR}, got {sorted(ids)}")
    hours = DEFAULT_HOURS if hours is None else hours
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO dealership (id, name, timezone) VALUES (:id, :name, :tz)"),
            {"id": dealership_id, "name": f"Test dealership {dealership_id}", "tz": timezone},
        )
        if hours:
            await conn.execute(
                text(
                    "INSERT INTO opening_hours (dealership_id, weekday, opens_at, closes_at)"
                    " VALUES (:d, :weekday, :opens, :closes)"
                ),
                [
                    {"d": dealership_id, "weekday": wd, "opens": o, "closes": c}
                    for wd, (o, c) in hours.items()
                ],
            )
        if bays:
            await conn.execute(
                text("INSERT INTO service_bay (id, dealership_id, name) VALUES (:id, :d, :name)"),
                [{"id": b, "d": dealership_id, "name": f"Bay {b}"} for b in bays],
            )
        for tech_id, skills in (technicians or {}).items():
            await conn.execute(
                text("INSERT INTO technician (id, dealership_id, name) VALUES (:id, :d, :name)"),
                {"id": tech_id, "d": dealership_id, "name": f"Technician {tech_id}"},
            )
            if skills:
                await conn.execute(
                    text("INSERT INTO technician_skill (technician_id, skill_id) VALUES (:t, :s)"),
                    [{"t": tech_id, "s": s} for s in skills],
                )


def booking_body(
    *,
    service_type_id: int = 1,
    start_at: str = "2027-03-26T09:00:00",
    customer_id: str | None = "C-42",
    email: str | None = None,
    name: str | None = "Sam Lee",
    vehicle_id: str | None = None,
    vin: str | None = "WVWZZZ1JZXW000001",
    make: str | None = "VW",
    model: str | None = "Golf",
) -> dict[str, Any]:
    """A booking request body in the SPEC wire format; defaults are the SPEC example."""
    return {
        "service_type_id": service_type_id,
        "start_at": start_at,
        "customer": {"id": customer_id, "email": email, "name": name},
        "vehicle": {"id": vehicle_id, "vin": vin, "make": make, "model": model},
    }


async def overlap_count(engine: AsyncEngine) -> int:
    """The overlap SQL of design §5: committed appointments sharing a resource in time."""
    async with engine.connect() as conn:
        return int((await conn.execute(text(OVERLAP_SQL))).scalar_one())


def barrier_gate(n: int, timeout_s: float = 10.0) -> Callable[[], Awaitable[None]]:
    """An ``AttemptGate`` releasing ``n`` bookings together before their first reserve.

    Raises ``TimeoutError`` after ``timeout_s`` if fewer than ``n`` arrive, so a broken test
    fails instead of hanging.
    """
    barrier = asyncio.Barrier(n)

    async def gate() -> None:
        async with asyncio.timeout(timeout_s):
            await barrier.wait()

    return gate
