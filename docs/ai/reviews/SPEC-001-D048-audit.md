# SPEC-001 D-048 audit

Task: D-048
Base: `a57b5b2717f44d839ceebb431882b9277ef5c6a6`
Head: `7ed95e0cdadec80fae23750df9d8416408ba6cfd`
Date: 2026-11-04
Reviewer: Codex
Cycle: 2

Verdict: revise

## Findings

- Cycle 2 — Severity: high
  File: `tests/test_concurrency.py` (missing); `tests/conftest.py:179-190`; `docs/ai/specs/SPEC-001-booking-service.md:205,251,774-821`
  What: SPEC TC-31 is not exercised: its named test file does not exist. Moreover, the retained specified implementation of TC-31 gives `barrier_gate(8)` to `BookAppointment`. D-048 correctly takes the dealership advisory lock before the gate (`book_appointment.py:71-105`), so the first request holds that lock while waiting at the eight-party gate; the other seven wait at `pg_advisory_xact_lock` and cannot reach the gate. `barrier_gate` therefore raises `TimeoutError` after 10 seconds. The implementer's reported `106 passed` cannot demonstrate the D-048 concurrency acceptance criterion.
  Required fix: Restore and exercise TC-31 with a concurrency arrangement compatible with post-claim serialisation—for example, synchronize client task start before `execute`/the claim (or do not inject the attempt gate), then assert the required deterministic serialized outcomes. Update the SPEC's TC-31/V-002 example to that arrangement. Keep TC-11's separate assertion that `serialise` is after claim and before the gate.

## Out-of-scope divergences (for the orchestrator)

These paths were intentionally outside D-048. They do not independently change the verdict.

- Severity: documentation
  File: `docs/design.md:7`
  What: States that every loser moves to the next pair; a 40P01 loss now retains the pair.
  Required fix: Limit the statement to a named 23P01 resource conflict and describe the 40P01 exception.

- Severity: documentation
  File: `docs/design.md:13`
  What: States that 23P01 and 40P01 both mean “next pair.”
  Required fix: State that 40P01 counts the attempt and deadlock but prunes nothing; add the post-claim advisory-lock step.

- Severity: documentation
  File: `docs/design.md:115-120`
  What: The booking sequence omits `serialise` after the successful claim and joins 23P01 and 40P01 under “prune lost resource, next pair.”
  Required fix: Insert the advisory-lock step after the no-row claim branch, and split the 23P01 and 40P01 attempt outcomes.

- Severity: documentation
  File: `docs/design.md:204`
  What: States “next pair never same pair.”
  Required fix: Qualify the principle as applying to named resource losses only.

- Severity: documentation
  File: `docs/adr/ADR-008.md:19-21`
  What: The request order moves directly from claim to business validation and candidate query, omitting the required post-claim serialisation.
  Required fix: Add `UnitOfWork.serialise(dealership_id)` after a no-row claim and before business validation.

- Severity: documentation
  File: `docs/adr/ADR-008.md:28`
  What: States that every candidate containing the lost resource is pruned for 23P01 or 40P01; a 40P01 names no resource and now prunes nothing.
  Required fix: Restrict resource pruning to named 23P01 conflicts and refer to the D-048 40P01 rule.

- Severity: documentation
  File: `docs/adr/ADR-008.md:53`
  What: States that 40P01 prunes the attempted pair.
  Required fix: State that 40P01 increments `attempts` and `deadlocks`, retains the candidate list, and remains bounded.

- Severity: documentation
  File: `README.md:150`
  What: States that 40P01 prunes only the pair.
  Required fix: Describe the amended 40P01 rule: no pruning and retry of the same pair, bounded by five attempts.

Additional stale consequence wording remains at `docs/design.md:133,135`, `docs/adr/ADR-008.md:36`, and `README.md:172`: D-048 serialises writers of one dealership, so 40P01 is no longer an expected attempt-path race cost. Those descriptions should distinguish historical/unexpected 40P01 handling from normal booking behaviour.

## Evidence

- Cycle-1 finding resolved: the T5 task block at `docs/ai/specs/SPEC-001-booking-service.md:745` keeps the landed commit title verbatim and immediately qualifies it: a named 23P01 never reuses the pair, while 40P01 keeps it. A full SPEC search found no other statement that says 40P01 prunes a pair or leaves “never same pair” unqualified.
- Lock placement/replay: `book_appointment.py:71-105` claims first; both stored-row paths return before `serialise`; `serialise` precedes validation, candidate reads, the attempt gate, and `run_attempts`. `test_serialise_after_claim_before_any_reserve_and_never_on_replay` exercises this as TC-11.
- Adapter/port: `unit_of_work.py:37-75` begins the transaction before retaining the connection; `serialise` executes `pg_advisory_xact_lock(CAST(:key AS bigint))` on that transaction connection; `__aexit__` commits or rolls back and closes it. `test_serialise_holds_the_dealership_lock_until_commit` verifies it is held until commit and then released.
- Attempt policy: `attempts.py:86-105` counts 40P01 attempts and deadlocks, prunes nothing, retries the same pair, and returns `contention` at the bound. TC-01 and TC-02 assert the retained pair and bound. Named 23P01 pruning and `no_vehicle_overlap` remain distinct.
- ADR-004's D-048 amendment matches this implementation: post-claim transaction-scoped per-dealership locking; replay bypass; 40P01 retained and bounded. `docs/ai/lessons.md` contains L-005. No `ERR-nnn` or `LSN-*` IDs occur in the D-048 diff. The HEAD trailer uses the accepted `Claude Opus 5.5 <noreply@anthropic.com>` attribution.
- `git diff --check a57b5b2717f44d839ceebb431882b9277ef5c6a6..HEAD` — no output.
- `UV_CACHE_DIR=/private/tmp/codex-uv-cache-d048-a62b3e43bb3630172 uv run mypy src tests/fakes.py` — passed: 34 source files.
- `UV_CACHE_DIR=/private/tmp/codex-uv-cache-d048-a62b3e43bb3630172 uv run pre-commit run --all-files` — passed all hooks.
- `UV_CACHE_DIR=/private/tmp/codex-uv-cache-d048-a62b3e43bb3630172 uv run pytest -q tests/test_attempts.py tests/test_book_appointment_usecase.py` — 22 passed in 0.04 s.
- Docker-backed tests were not run in this sandbox. The implementer reports `106 passed` at HEAD; that result does not exercise missing TC-31.
