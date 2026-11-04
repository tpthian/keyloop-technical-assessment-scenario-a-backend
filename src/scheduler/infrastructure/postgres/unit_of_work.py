"""PostgreSQL unit of work: one transaction per booking (ADR-004, ADR-008)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import TracebackType

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from scheduler.application.ports import (
    AppointmentRepository,
    IdempotencyRepository,
    SchedulingReadRepository,
)
from scheduler.infrastructure.postgres.repositories import (
    PostgresAppointmentRepository,
    PostgresIdempotencyRepository,
    PostgresSchedulingReadRepository,
)

DEADLOCK_TIMEOUT = "100ms"
STATEMENT_TIMEOUT = "2s"


class PostgresUnitOfWork:
    """BEGIN and the two ``SET LOCAL`` on enter; COMMIT on clean exit; ROLLBACK on exception.

    The three adapters share the transaction's connection, so a key claim, the reference reads
    and every reserve attempt see one snapshot and commit or roll back together.
    """

    appointments: AppointmentRepository
    idempotency: IdempotencyRepository
    reads: SchedulingReadRepository

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._conn: AsyncConnection | None = None

    async def __aenter__(self) -> PostgresUnitOfWork:
        conn = await self._engine.connect()
        try:
            await conn.begin()
            await conn.execute(text(f"SET LOCAL deadlock_timeout = '{DEADLOCK_TIMEOUT}'"))
            await conn.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
        except BaseException:
            await conn.close()
            raise
        self._conn = conn

        @asynccontextmanager
        async def same_connection() -> AsyncIterator[AsyncConnection]:
            yield conn

        self.appointments = PostgresAppointmentRepository(conn)
        self.idempotency = PostgresIdempotencyRepository(conn)
        self.reads = PostgresSchedulingReadRepository(same_connection)
        return self

    async def __aexit__(
        self,
        et: type[BaseException] | None,
        ev: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        conn = self._conn
        assert conn is not None
        try:
            if et is None:
                await conn.commit()
            else:
                await conn.rollback()
        finally:
            self._conn = None
            await conn.close()
