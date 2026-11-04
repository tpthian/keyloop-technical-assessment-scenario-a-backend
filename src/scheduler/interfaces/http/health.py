"""Liveness and readiness, separate endpoints (design §3, ADR-013).

``/health/live`` answers 200 while the process serves requests. ``/health/ready`` runs
``SELECT 1`` through the engine and answers 503 on any exception, so a database outage takes
the instance out of rotation without getting a healthy process restarted.

``build_router`` takes any object shaped like SQLAlchemy's ``AsyncEngine`` (``connect()``
giving an async context manager whose connection has ``exec_driver_sql``), so this module names
no SQLAlchemy type and the interfaces layer keeps the layer rule (design §4).
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol

from fastapi import APIRouter
from fastapi.responses import JSONResponse


class Connection(Protocol):
    async def exec_driver_sql(self, statement: str) -> Any: ...


class Connectable(Protocol):
    """The part of ``sqlalchemy.ext.asyncio.AsyncEngine`` that readiness uses."""

    def connect(self) -> AbstractAsyncContextManager[Connection]: ...


OK = {"status": "ok"}
UNAVAILABLE = {"status": "unavailable"}


def build_router(engine: Connectable) -> APIRouter:
    router = APIRouter(prefix="/health")

    @router.get("/live", name="health_live")
    async def live() -> dict[str, str]:
        return OK

    @router.get("/ready", name="health_ready", response_model=None)
    async def ready() -> dict[str, str] | JSONResponse:
        try:
            async with engine.connect() as conn:
                await conn.exec_driver_sql("SELECT 1")
        except Exception:
            return JSONResponse(UNAVAILABLE, status_code=503)
        return OK

    return router
