"""Attempt policy: a lost resource is never tried again (design §3, ADR-004 pruning clause).

``run_attempts`` walks the candidate list in the order given (the use case passes it through
``shuffled`` first) and calls ``reserve`` at most ``bound`` times. After each lost attempt the
list is pruned by what the loss names:

- ``no_bay_overlap``: every candidate with that bay;
- ``no_technician_overlap``: every candidate with that technician;
- any other constraint name: only the attempted pair;
- a deadlock (40P01): nothing; a deadlock names no resource and the pair may still be free, so
  the attempt and the deadlock are counted and the same pair is tried again (ADR-004
  amendment, D-048);
- ``no_vehicle_overlap``: nothing is pruned; the request ends with ``vehicle_already_booked``.

Every pruning rule removes the attempted pair, so a pair lost to 23P01 is never tried again.
Bookings of one dealership are serialised (``UnitOfWork.serialise``), so a 40P01 is not
expected; keeping the pair stops a deadlock from turning a free pair into a false
``capacity_exhausted``, and the bound still ends a run of deadlocks. When the pruned list is
empty the result is ``capacity_exhausted`` (decided before the bound, so a list emptied on the
last allowed attempt is still final); when the bound is hit with pairs left it is
``contention``.
"""

from __future__ import annotations

import random
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from scheduler.domain.model import Candidate, Confirmed, ResourceTaken

RETRY_BOUND = 5

NO_BAY_OVERLAP = "no_bay_overlap"
NO_TECHNICIAN_OVERLAP = "no_technician_overlap"
NO_VEHICLE_OVERLAP = "no_vehicle_overlap"

CONFIRMED = "confirmed"
CAPACITY_EXHAUSTED = "capacity_exhausted"
VEHICLE_ALREADY_BOOKED = "vehicle_already_booked"
CONTENTION = "contention"


@dataclass(frozen=True)
class AttemptResult:
    """``code`` is one of ``confirmed``, ``capacity_exhausted``, ``vehicle_already_booked``,
    ``contention``. ``candidate`` and ``appointment_id`` are set only when confirmed.
    ``candidates_pruned`` counts every candidate removed by a loss, the attempted one included.
    """

    code: str
    attempts: int
    deadlocks: int
    candidates_pruned: int
    candidate: Candidate | None
    appointment_id: int | None


Reserve = Callable[[Candidate], Awaitable[Confirmed | ResourceTaken]]


def shuffled(candidates: Sequence[Candidate]) -> list[Candidate]:
    """A new list in random order, so simultaneous requests spread over pairs (ADR-004)."""
    return random.sample(list(candidates), k=len(candidates))


def _prune(remaining: list[Candidate], tried: Candidate, taken: ResourceTaken) -> list[Candidate]:
    if taken.constraint == NO_BAY_OVERLAP:
        return [c for c in remaining if c.bay_id != tried.bay_id]
    if taken.constraint == NO_TECHNICIAN_OVERLAP:
        return [c for c in remaining if c.technician_id != tried.technician_id]
    return [c for c in remaining if c != tried]  # unknown constraint: the pair only


async def run_attempts(
    candidates: Sequence[Candidate],
    reserve: Reserve,
    bound: int = RETRY_BOUND,
) -> AttemptResult:
    remaining = list(candidates)
    attempts = deadlocks = pruned = 0

    def result(code: str) -> AttemptResult:
        return AttemptResult(code, attempts, deadlocks, pruned, None, None)

    while remaining:
        if attempts >= bound:
            return result(CONTENTION)
        candidate = remaining[0]
        attempts += 1
        outcome = await reserve(candidate)
        if isinstance(outcome, Confirmed):
            return AttemptResult(
                CONFIRMED, attempts, deadlocks, pruned, candidate, outcome.appointment_id
            )
        if outcome.deadlock:
            deadlocks += 1  # the pair stays: a deadlock names no resource (D-048)
            continue
        if outcome.constraint == NO_VEHICLE_OVERLAP:
            return result(VEHICLE_ALREADY_BOOKED)
        after = _prune(remaining, candidate, outcome)
        pruned += len(remaining) - len(after)
        remaining = after
    return result(CAPACITY_EXHAUSTED)
