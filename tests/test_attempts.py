"""TC-01, TC-02 (AC-03): the attempt policy of ADR-004, pure domain.

One test per TC clause. A scripted ``reserve`` returns a fixed sequence of results and records
every candidate it is handed, so each test asserts the classification and the pairs tried.
"""

from __future__ import annotations

from collections.abc import Sequence

from scheduler.domain.attempts import (
    RETRY_BOUND,
    AttemptResult,
    Candidate,
    Confirmed,
    ResourceTaken,
    run_attempts,
)

DEADLOCK = ResourceTaken(None, deadlock=True)


class ScriptedReserve:
    """Returns ``script`` in order; records the candidates it saw."""

    def __init__(self, script: Sequence[Confirmed | ResourceTaken]) -> None:
        self._script = list(script)
        self.seen: list[Candidate] = []

    async def __call__(self, candidate: Candidate) -> Confirmed | ResourceTaken:
        self.seen.append(candidate)
        if not self._script:
            raise AssertionError(f"reserve called more often than scripted: {candidate}")
        return self._script.pop(0)


def grid(bays: Sequence[int], techs: Sequence[int]) -> list[Candidate]:
    return [Candidate(b, t) for b in bays for t in techs]


def lost(constraint: str) -> ResourceTaken:
    return ResourceTaken(constraint, deadlock=False)


# --- TC-01 ---------------------------------------------------------------------------------


async def test_tc01_bay_overlap_prunes_every_candidate_with_that_bay() -> None:
    reserve = ScriptedReserve([lost("no_bay_overlap"), Confirmed(7)])

    result = await run_attempts(grid([1, 2], [10, 20]), reserve)

    assert reserve.seen == [Candidate(1, 10), Candidate(2, 10)]  # (1,20) skipped: bay 1 lost
    assert result == AttemptResult("confirmed", 2, 0, 2, Candidate(2, 10), 7)


async def test_tc01_technician_overlap_prunes_every_candidate_with_that_technician() -> None:
    reserve = ScriptedReserve([lost("no_technician_overlap"), Confirmed(8)])

    result = await run_attempts(grid([1, 2], [10, 20]), reserve)

    assert reserve.seen == [Candidate(1, 10), Candidate(1, 20)]  # (2,10) skipped: tech 10 lost
    assert result == AttemptResult("confirmed", 2, 0, 2, Candidate(1, 20), 8)


async def test_tc01_deadlock_prunes_only_the_pair() -> None:
    reserve = ScriptedReserve([DEADLOCK, Confirmed(9)])

    result = await run_attempts(grid([1, 2], [10, 20]), reserve)

    # (1,20) shares bay 1 and is still tried next: a deadlock names no resource
    assert reserve.seen == [Candidate(1, 10), Candidate(1, 20)]
    assert result == AttemptResult("confirmed", 2, 1, 1, Candidate(1, 20), 9)


async def test_tc01_vehicle_overlap_stops_with_vehicle_already_booked() -> None:
    reserve = ScriptedReserve([lost("no_vehicle_overlap")])  # a second call fails the script

    result = await run_attempts(grid([1, 2], [10, 20]), reserve)

    assert reserve.seen == [Candidate(1, 10)]
    assert result == AttemptResult("vehicle_already_booked", 1, 0, 0, None, None)


# --- TC-02 ---------------------------------------------------------------------------------


async def test_tc02_bound_of_five_with_candidates_left_is_contention() -> None:
    assert RETRY_BOUND == 5
    reserve = ScriptedReserve([DEADLOCK] * 5)  # 9 pairs, 5 pruned, 4 left; a sixth call fails

    result = await run_attempts(grid([1, 2, 3], [10, 20, 30]), reserve)

    assert len(reserve.seen) == 5
    assert result == AttemptResult("contention", 5, 5, 5, None, None)


async def test_tc02_pruned_list_empty_is_capacity_exhausted() -> None:
    # the list empties on the fifth and last allowed attempt: the empty list decides the code,
    # so the result is the final capacity_exhausted, not the transient contention (ADR-004)
    reserve = ScriptedReserve([lost("no_bay_overlap")] * 5)

    result = await run_attempts(grid([1, 2, 3, 4, 5], [10]), reserve)

    assert len(reserve.seen) == 5
    assert result == AttemptResult("capacity_exhausted", 5, 0, 5, None, None)


async def test_tc02_empty_input_is_capacity_exhausted_with_zero_attempts() -> None:
    reserve = ScriptedReserve([])

    result = await run_attempts([], reserve)

    assert reserve.seen == []
    assert result == AttemptResult("capacity_exhausted", 0, 0, 0, None, None)
