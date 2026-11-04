# SPEC-001 T5 audit

Task: T5 — Attempt policy
Base: a919ea6fa28b7f2333018f02316c40dbccb0c557
Head: 42e347fa5809a4fdf1513d968b188fe8e5f0e438
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings

None.

## Evidence

- `git diff --name-status a919ea6fa28b7f2333018f02316c40dbccb0c557..HEAD` → only `A src/scheduler/domain/attempts.py` and `A tests/test_attempts.py`, the T5 path list.
- Source review against SPEC § Contract AC-03, § Execution types/functions and the Booking sequence, ADR-004, and design §3 → `Candidate(bay_id, technician_id)`, `Confirmed(appointment_id)`, and `ResourceTaken(constraint: str | None, deadlock: bool)` exactly match the type table; their approved T4-ownership relocation comments are present. `AttemptResult` supplies the use case's required `code` and `appointment_id`; success is exactly `confirmed`. Domain imports are standard-library only.
- Policy review → `RETRY_BOUND == 5`; bay and technician losses remove all candidates sharing the named resource; deadlock, `None`, and unknown constraints remove only the attempted pair; vehicle loss terminates unpruned as `vehicle_already_booked`. The attempted pair is therefore not retried. Counters increment on each actual reserve call, each deadlock, and each candidate removed by pruning. Empty input is `capacity_exhausted` with all counters zero.
- Boundary review → after a fifth loss that empties the list, the loop condition is false and the trailing `capacity_exhausted` return wins; with candidates left, the next loop entry sees `attempts >= bound` and returns `contention`. This matches ADR-004's pruned-list precedence.
- Test review → exactly seven test functions: four TC-01 clauses and three TC-02 clauses. Each uses `ScriptedReserve`, which returns a fixed script and records `seen` candidates.
- Mutation probe (bound check before empty check): `UV_CACHE_DIR=/private/tmp/uv-t5-audit-cache uv run pytest tests/test_attempts.py -q` → `1 failed, 6 passed`; `test_tc02_pruned_list_empty_is_capacity_exhausted` received `contention` instead of `capacity_exhausted`.
- Mutation probe (make deadlock prune the bay): `UV_CACHE_DIR=/private/tmp/uv-t5-audit-cache uv run pytest tests/test_attempts.py -q` → `2 failed, 5 passed`; the deadlock pair-only test observed the wrong next candidate and the bound test stopped after three attempts.
- Restoration check: `git checkout -- src/scheduler/domain/attempts.py` was attempted as required but the sandbox denied creation of the worktree `index.lock`. The mutation was reversed immediately, then `git diff --exit-code HEAD -- src/scheduler/domain/attempts.py tests/test_attempts.py` → exit 0, proving both audited files exactly match HEAD.
- `UV_CACHE_DIR=/private/tmp/uv-t5-audit-cache uv run pytest tests/test_attempts.py tests/test_architecture.py -q` → `9 passed in 0.02s`.
- `UV_CACHE_DIR=/private/tmp/uv-t5-audit-cache uv run pre-commit run --all-files` → trailing whitespace, EOF, YAML, large-file, merge-conflict, ruff check/format, gitleaks, and mypy hooks all `Passed`.
- `UV_CACHE_DIR=/private/tmp/uv-t5-audit-cache uv run mypy src` → `Success: no issues found in 10 source files`.
- `git log a919ea6fa28b7f2333018f02316c40dbccb0c557..HEAD` → both T5 commits have the exact subject `SPEC-001 T5: attempt policy, next pair never same pair (design §3, ADR-004)` and each includes a `Co-Authored-By` trailer.
