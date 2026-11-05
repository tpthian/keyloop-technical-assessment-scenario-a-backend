"""Composition root (SPEC-001 Architecture, design §2, D-041): the only module importing both
``scheduler.infrastructure`` and ``scheduler.interfaces``.

``create_app`` builds the adapters, injects them into the use cases, hands one ``UseCases``
container to each router factory and mounts the wide-event and body-cap middleware and the error
handlers.
Nothing but the engine goes on ``app.state`` (readiness only, Known Facts 3). ``uvicorn
scheduler.main:create_app --factory`` calls it with no arguments: the engine then comes from
``DATABASE_URL`` and is disposed when the app shuts down; an engine passed in belongs to the
caller and is left open.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from scheduler.application.book_appointment import BookAppointment
from scheduler.application.get_appointment import GetAppointment
from scheduler.application.get_availability import GetAvailability
from scheduler.application.ports import AttemptGate, Clock
from scheduler.infrastructure.clock import SystemClock
from scheduler.infrastructure.postgres.engine import make_engine
from scheduler.infrastructure.postgres.repositories import PostgresSchedulingReadRepository
from scheduler.infrastructure.postgres.unit_of_work import PostgresUnitOfWork
from scheduler.interfaces.http import appointments, availability, health
from scheduler.interfaces.http.dependencies import UseCases
from scheduler.interfaces.http.errors import register_handlers
from scheduler.interfaces.http.events import WideEventMiddleware
from scheduler.interfaces.http.limits import BodySizeLimitMiddleware
from scheduler.settings import get_settings


def create_app(
    engine: AsyncEngine | None = None,
    clock: Clock | None = None,
    attempt_gate: AttemptGate | None = None,
) -> FastAPI:
    owns_engine = engine is None
    db = make_engine(get_settings().DATABASE_URL) if engine is None else engine
    reads = PostgresSchedulingReadRepository(db.connect)
    the_clock: Clock = SystemClock() if clock is None else clock  # one clock for every use case
    uc = UseCases(
        reads=reads,
        book_appointment=BookAppointment(
            uow=lambda: PostgresUnitOfWork(db),
            clock=the_clock,
            # test seam for a writer that bypasses the dealership lock (TC-39); None in production
            gate=attempt_gate,
        ),
        get_appointment=GetAppointment(reads),
        get_availability=GetAvailability(reads, the_clock),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if owns_engine:
                await db.dispose()

    app = FastAPI(title="Unified Service Scheduler", lifespan=lifespan)
    app.state.engine = db  # readiness only; nothing else lives on app.state
    app.include_router(appointments.build_router(uc))
    app.include_router(availability.build_router(uc))
    app.include_router(health.build_router(db))
    app.add_middleware(BodySizeLimitMiddleware)  # inside the wide event: a 413 is logged (ADR-014)
    app.add_middleware(WideEventMiddleware)
    register_handlers(app)
    return app
