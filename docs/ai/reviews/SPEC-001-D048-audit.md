# SPEC-001 D-048 audit

Task: D-048
Base: `a57b5b2717f44d839ceebb431882b9277ef5c6a6`
Head: `752bcb47bf51710a781148e64eb446fa18b850b1`
Date: 2026-11-04
Reviewer: Codex

Verdict: revise

## Findings

- Severity: medium
  File: `docs/ai/specs/SPEC-001-booking-service.md:745`
  What: The T5 task block still states “next pair never same pair.” This contradicts the D-048 TC-01 amendment and the implementation: a 40P01 retains and retries the same pair.
  Required fix: Amend the T5 task-block wording to limit the no-retry rule to named 23P01 resource losses, and state that a 40P01 keeps the pair.

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

- `git diff --check a57b5b2717f44d839ceebb431882b9277ef5c6a6..HEAD` — no output.
- `git diff --stat a57b5b2717f44d839ceebb431882b9277ef5c6a6..HEAD` — 11 files changed, 130 insertions, 28 deletions.
- Source inspection: `book_appointment.py:71-105` claims first, returns/raises for both stored-row paths before `serialise`, then serialises before validation, candidate reads, gate, and `run_attempts`. Under READ COMMITTED, the subsequent candidate query observes the preceding lock holder's committed rows.
- Source inspection: `unit_of_work.py:42-71` begins before assigning `_conn`; `serialise` executes `pg_advisory_xact_lock(CAST(:key AS bigint))` on that connection. `__aexit__` commits or rolls back, clears `_conn`, and closes the connection. No adapter path can acquire the lock before `BEGIN` or retain it after transaction exit; no explicit unlock exists.
- Source and test inspection: `attempts.py:86-104` counts a 40P01 attempt and deadlock without pruning; named 23P01 pruning and `no_vehicle_overlap` classification remain intact. `tests/test_attempts.py:60-69` cites D-048 as superseding the old pair-pruning rule.
- Test inspection: `tests/test_book_appointment_usecase.py:250-261` asserts `claim -> serialise -> gate -> reserve` and replay `claim` only. `tests/test_postgres_adapters.py:151-163` checks `pg_try_advisory_xact_lock` is false while the first transaction holds the lock and true after commit. Existing changed expectations concern only the amended deadlock-pruning values and the new log entry.
- `git log --reverse a57b5b2717f44d839ceebb431882b9277ef5c6a6..HEAD` — five commits, each with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Ordering is sound: T7 (`440c37a`) adds the adapter and its test before T6 (`3d3e403`) requires the port method, keeping the later Protocol/use-case change compatible with the adapter.
- `git diff --unified=0 a57b5b2717f44d839ceebb431882b9277ef5c6a6..HEAD | rg 'ERR-[0-9]+|LSN-[A-Za-z0-9_-]'` — no matches. `docs/ai/lessons.md:11` adds repository-local L-005 only.
- `export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock; uv run pytest -q` — blocked before collection: shared uv cache access denied by sandbox.
- `UV_CACHE_DIR=/private/tmp/spec001-d048-uv-cache TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest -q` — 52 passed, 54 errors in 5.31s; every error was testcontainers unable to connect to the Docker socket (`PermissionError: [Errno 1] Operation not permitted`), not a test assertion failure.
- `UV_CACHE_DIR=/private/tmp/spec001-d048-uv-cache uv run pytest -q tests/test_attempts.py tests/test_book_appointment_usecase.py` — 22 passed in 0.04s.
- `UV_CACHE_DIR=/private/tmp/spec001-d048-uv-cache uv run mypy src tests/fakes.py` — `Success: no issues found in 34 source files`.
- `UV_CACHE_DIR=/private/tmp/spec001-d048-uv-cache uv run pre-commit run --all-files` — all hooks Passed.

Changed file under this audit: `docs/ai/reviews/SPEC-001-D048-audit.md`.
