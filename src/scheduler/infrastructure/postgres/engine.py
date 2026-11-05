"""Async engine factory (ADR-002): psycopg 3 through SQLAlchemy Core asyncio."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def make_engine(url: str) -> AsyncEngine:
    """Pool sized for the service process: 10 pooled connections plus 10 overflow."""
    return create_async_engine(url, pool_size=10, max_overflow=10)
