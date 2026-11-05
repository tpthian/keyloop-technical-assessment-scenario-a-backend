"""Domain errors (SPEC-001 § Execution, Interfaces). HTTP mapping lives in the interface layer."""

from __future__ import annotations

from scheduler.domain.attempts import AttemptResult


class DomainError(Exception):
    """Base of every error the domain and application layers raise on purpose."""


class GapTime(DomainError, ValueError):  # noqa: N818 (name fixed by the SPEC interface)
    """The local wall time does not exist in the zone (spring-forward gap, ADR-009)."""


class NoOpeningInstant(DomainError):  # noqa: N818 (name fixed by the SPEC interface)
    """``pickup_from`` found no opening instant within ``PICKUP_WALK_DAYS`` (ADR-009)."""


class NotFound(DomainError):  # noqa: N818 (name fixed by the SPEC interface)
    def __init__(self, what: str) -> None:
        super().__init__(f"{what} not found")
        self.what = what


class ValidationFailed(DomainError):  # noqa: N818 (name fixed by the SPEC interface)
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ReplayConflict(DomainError):  # noqa: N818 (name fixed by the SPEC interface)
    """Same idempotency key, different canonical request (ADR-008)."""


class Contention(DomainError):  # noqa: N818 (name fixed by the SPEC interface)
    """Bound of attempts hit with candidates left; the booking transaction rolls back (ADR-008)."""

    def __init__(self, result: AttemptResult) -> None:
        super().__init__("bound of attempts reached with candidates left")
        self.result = result
