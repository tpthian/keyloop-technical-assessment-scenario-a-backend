"""System clock adapter for the ``Clock`` port (SPEC-001 § Execution; D-041)."""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
