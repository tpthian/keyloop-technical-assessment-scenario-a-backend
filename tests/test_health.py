"""TC-33 / AC-09: liveness and readiness are separate (design §3, ADR-013)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from scheduler.interfaces.http import health
from scheduler.interfaces.http.events import WideEventMiddleware

CLOSED_PORT_URL = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none"  # nothing listens


def _app(engine: AsyncEngine) -> FastAPI:
    app = FastAPI()
    app.add_middleware(WideEventMiddleware)
    app.include_router(health.build_router(engine))
    return app


async def _get(engine: AsyncEngine, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=_app(engine))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest_asyncio.fixture
async def dead_engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(CLOSED_PORT_URL)
    try:
        yield eng
    finally:
        await eng.dispose()


async def test_live_is_200_without_a_database(dead_engine: AsyncEngine) -> None:
    response = await _get(dead_engine, "/health/live")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


async def test_ready_is_200_with_the_database(engine: AsyncEngine) -> None:
    response = await _get(engine, "/health/ready")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


async def test_ready_is_503_with_an_engine_on_a_closed_port(dead_engine: AsyncEngine) -> None:
    response = await _get(dead_engine, "/health/ready")
    assert (response.status_code, response.json()) == (503, {"status": "unavailable"})
