"""TC-01, TC-02 (AC-03): the attempt policy of ADR-004, pure domain.

A scripted ``reserve`` returns a fixed sequence of results and records every candidate it is
handed, so each test asserts both the classification and the exact pairs that were tried.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from scheduler.domain.attempts import (
    RETRY_BOUND,
    AttemptResult,
    Candidate,
    Confirmed,
    ResourceTaken,
    run_attempts,
    shuffled,
)

BAY = "no_bay_overlap"
TECH = "no_technician_overlap"
VEHICLE = "no_vehicle_overlap"


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


DEADLOCK = ResourceTaken(None, deadlock=True)


# --- TC-01: pruning by constraint name -----------------------------------------------------


async def test_bay_overlap_prunes_every_candidate_with_that_bay() -> None:
    cands = grid([1, 2], [10, 20])  # (1,10) (1,20) (2,10) (2,20)
    reserve = ScriptedReserve([lost(BAY), Confirmed(7)])

    result = await run_attempts(cands, reserve)

    assert reserve.seen == [Candidate(1, 10), Candidate(2, 10)]  # (1,20) skipped: bay 1 lost
    assert result == AttemptResult(
        code="confirmed",
        attempts=2,
        deadlocks=0,
        candidates_pruned=2,
        candidate=Candidate(2, 10),
        appointment_id=7,
    )


async def test_technician_overlap_prunes_every_candidate_with_that_technician() -> None:
    cands = grid([1, 2], [10, 20])
    reserve = ScriptedReserve([lost(TECH), Confirmed(8)])

    result = await run_attempts(cands, reserve)

    assert reserve.seen == [Candidate(1, 10), Candidate(1, 20)]  # (2,10) skipped: tech 10 lost
    assert result.code == "confirmed"
    assert result.candidates_pruned == 2
    assert result.candidate == Candidate(1, 20)
    assert result.appointment_id == 8


async def test_deadlock_prunes_only_the_attempted_pair() -> None:
    cands = grid([1, 2], [10, 20])
    reserve = ScriptedReserve([DEADLOCK, Confirmed(9)])

    result = await run_attempts(cands, reserve)

    # (1,20) still shares bay 1 and is tried next: a deadlock names no resource
    assert reserve.seen == [Candidate(1, 10), Candidate(1, 20)]
    assert result.code == "confirmed"
    assert result.attempts == 2
    assert result.deadlocks == 1
    assert result.candidates_pruned == 1


async def test_unknown_constraint_prunes_only_the_attempted_pair() -> None:
    cands = grid([1, 2], [10])
    reserve = ScriptedReserve([lost("some_future_constraint"), Confirmed(3)])

    result = await run_attempts(cands, reserve)

    assert reserve.seen == [Candidate(1, 10), Candidate(2, 10)]
    assert result.code == "confirmed"
    assert result.deadlocks == 0
    assert result.candidates_pruned == 1


async def test_23p01_without_a_constraint_name_prunes_only_the_pair() -> None:
    cands = grid([1], [10, 20])
    reserve = ScriptedReserve([ResourceTaken(None, deadlock=False), Confirmed(4)])

    result = await run_attempts(cands, reserve)

    assert reserve.seen == [Candidate(1, 10), Candidate(1, 20)]
    assert result.deadlocks == 0
    assert result.candidates_pruned == 1


async def test_vehicle_overlap_stops_with_vehicle_already_booked() -> None:
    cands = grid([1, 2], [10, 20])
    reserve = ScriptedReserve([lost(VEHICLE)])  # a second call would fail the script

    result = await run_attempts(cands, reserve)

    assert reserve.seen == [Candidate(1, 10)]
    assert result == AttemptResult(
        code="vehicle_already_booked",
        attempts=1,
        deadlocks=0,
        candidates_pruned=0,
        candidate=None,
        appointment_id=None,
    )


async def test_vehicle_overlap_after_earlier_losses_keeps_the_counts() -> None:
    cands = grid([1, 2], [10, 20])
    reserve = ScriptedReserve([DEADLOCK, lost(BAY), lost(VEHICLE)])

    result = await run_attempts(cands, reserve)

    # (1,10) deadlock -> pair pruned; (1,20) bay 1 -> (1,20) pruned; (2,10) vehicle clash
    assert reserve.seen == [Candidate(1, 10), Candidate(1, 20), Candidate(2, 10)]
    assert result.code == "vehicle_already_booked"
    assert result.attempts == 3
    assert result.deadlocks == 1
    assert result.candidates_pruned == 2


async def test_next_pair_is_never_the_same_pair() -> None:
    cands = grid([1, 2, 3], [10, 20, 30])
    script: list[Confirmed | ResourceTaken] = [DEADLOCK, lost("x"), DEADLOCK, lost("y")]
    reserve = ScriptedReserve([*script, Confirmed(1)])

    await run_attempts(cands, reserve)

    assert len(reserve.seen) == len(set(reserve.seen)) == 5


async def test_first_attempt_wins_with_no_pruning() -> None:
    cands = grid([1, 2], [10, 20])
    reserve = ScriptedReserve([Confirmed(42)])

    result = await run_attempts(cands, reserve)

    assert reserve.seen == [Candidate(1, 10)]
    assert result == AttemptResult(
        code="confirmed",
        attempts=1,
        deadlocks=0,
        candidates_pruned=0,
        candidate=Candidate(1, 10),
        appointment_id=42,
    )


async def test_input_list_is_not_mutated() -> None:
    cands = grid([1, 2], [10, 20])
    before = list(cands)
    await run_attempts(cands, ScriptedReserve([lost(BAY), Confirmed(1)]))
    assert cands == before


# --- TC-02: bound and the empty list -------------------------------------------------------


def test_retry_bound_is_five() -> None:
    assert RETRY_BOUND == 5


async def test_bound_hit_with_candidates_left_is_contention() -> None:
    cands = grid([1, 2, 3], [10, 20, 30])  # 9 pairs; 5 deadlocks prune 5, leaving 4
    reserve = ScriptedReserve([DEADLOCK] * RETRY_BOUND)  # a sixth call would fail the script

    result = await run_attempts(cands, reserve)

    assert len(reserve.seen) == RETRY_BOUND
    assert result == AttemptResult(
        code="contention",
        attempts=5,
        deadlocks=5,
        candidates_pruned=5,
        candidate=None,
        appointment_id=None,
    )


async def test_pruned_list_empty_is_capacity_exhausted() -> None:
    cands = grid([1, 2], [10])  # (1,10) (2,10)
    reserve = ScriptedReserve([lost(TECH)])  # tech 10 lost -> both pairs pruned

    result = await run_attempts(cands, reserve)

    assert reserve.seen == [Candidate(1, 10)]
    assert result == AttemptResult(
        code="capacity_exhausted",
        attempts=1,
        deadlocks=0,
        candidates_pruned=2,
        candidate=None,
        appointment_id=None,
    )


async def test_list_emptied_exactly_on_the_last_allowed_attempt_is_capacity_exhausted() -> None:
    # empty list wins over the bound: the 409 code is decided on the pruned list (ADR-004)
    cands = grid([1, 2, 3, 4, 5], [10])
    reserve = ScriptedReserve([lost(BAY)] * RETRY_BOUND)

    result = await run_attempts(cands, reserve)

    assert len(reserve.seen) == RETRY_BOUND
    assert result.code == "capacity_exhausted"
    assert result.attempts == RETRY_BOUND
    assert result.candidates_pruned == 5


async def test_one_candidate_left_after_the_bound_is_contention() -> None:
    cands = grid([1, 2, 3, 4, 5, 6], [10])
    reserve = ScriptedReserve([lost(BAY)] * RETRY_BOUND)

    result = await run_attempts(cands, reserve)

    assert result.code == "contention"
    assert result.attempts == RETRY_BOUND
    assert result.candidates_pruned == 5


async def test_empty_input_is_capacity_exhausted_with_zero_attempts() -> None:
    reserve = ScriptedReserve([])

    result = await run_attempts([], reserve)

    assert reserve.seen == []
    assert result == AttemptResult(
        code="capacity_exhausted",
        attempts=0,
        deadlocks=0,
        candidates_pruned=0,
        candidate=None,
        appointment_id=None,
    )


async def test_custom_bound_is_honoured() -> None:
    cands = grid([1, 2, 3], [10])
    reserve = ScriptedReserve([DEADLOCK, DEADLOCK])

    result = await run_attempts(cands, reserve, bound=2)

    assert len(reserve.seen) == 2
    assert result.code == "contention"


# --- shuffled ------------------------------------------------------------------------------


def test_shuffled_is_a_permutation_and_leaves_the_input_alone() -> None:
    cands = grid([1, 2, 3], [10, 20, 30])
    before = list(cands)

    out = shuffled(cands)

    assert sorted(out, key=lambda c: (c.bay_id, c.technician_id)) == before
    assert cands == before
    assert out is not cands


def test_shuffled_varies_the_order() -> None:
    cands = grid([1, 2, 3], [10, 20, 30])  # 9! orders; 50 identical draws is ~0 probability
    orders = {tuple(shuffled(cands)) for _ in range(50)}
    assert len(orders) > 1


def test_shuffled_empty() -> None:
    assert shuffled([]) == []


@pytest.mark.parametrize("deadlock", [True, False])
def test_resource_taken_is_frozen(deadlock: bool) -> None:
    taken = ResourceTaken(None, deadlock=deadlock)
    with pytest.raises(AttributeError):
        taken.deadlock = not deadlock  # type: ignore[misc]
