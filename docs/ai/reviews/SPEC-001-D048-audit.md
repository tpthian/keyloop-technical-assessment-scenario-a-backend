# SPEC-001 D-048 audit

Task: D-048
Base-SHA: `a57b5b2717f44d839ceebb431882b9277ef5c6a6`
Head-SHA: `918ecb809ffd345f7c956ca5308b639544154b8a`
Cycle: 4
Commits:
- `440c37a SPEC-001 T7: advisory lock adapter for UnitOfWork.serialise (ADR-004 amendment, D-048)`
- `3d3e403 SPEC-001 T6: serialise bookings per dealership after the key claim (ADR-004 amendment, D-048)`
- `687fb04 SPEC-001 T5: a deadlock loss keeps the pair in the candidate list (ADR-004 amendment, D-048)`
- `5433422 SPEC-001 T0e: ADR-004 amendment and scope row for D-048 (ADR-004)`
- `752bcb4 SPEC-001 T0e: SPEC Interfaces wording for D-048 (ADR-004)`
- `7ed95e0 SPEC-001 T0e: T5 task block qualifies never-same-pair for 40P01 (D-048 audit cycle 1)`
- `9a6a682 SPEC-001 T0f: TC-31 synchronises the clients before they send, not the attempts (ADR-004, D-049; D-048 audit cycle 2)`
- `918ecb8 SPEC-001 T0f: retry loop as the fallback behind the lock; TC-39 bypass test; TC-31 attempts total (ADR-004, D-050; D-048 audit cycle 3)`

Allowed-Paths: `src/scheduler/application/book_appointment.py`, `src/scheduler/application/ports.py`, `src/scheduler/domain/attempts.py`, `src/scheduler/infrastructure/postgres/unit_of_work.py`, `tests/fakes.py`, `tests/test_attempts.py`, `tests/test_book_appointment_usecase.py`, `tests/test_postgres_adapters.py`, `docs/adr/ADR-004.md`, `docs/ai/lessons.md`, `docs/ai/specs/SPEC-001-booking-service.md`; audit-report exception: `docs/ai/reviews/SPEC-001-D048-audit.md`
Changed-Paths:
- `M docs/adr/ADR-004.md`
- `M docs/ai/lessons.md`
- `A docs/ai/reviews/SPEC-001-D048-audit.md`
- `M docs/ai/specs/SPEC-001-booking-service.md`
- `M src/scheduler/application/book_appointment.py`
- `M src/scheduler/application/ports.py`
- `M src/scheduler/domain/attempts.py`
- `M src/scheduler/infrastructure/postgres/unit_of_work.py`
- `M tests/fakes.py`
- `M tests/test_attempts.py`
- `M tests/test_book_appointment_usecase.py`
- `M tests/test_postgres_adapters.py`

Checks:
- `git rev-parse --verify a57b5b2717f44d839ceebb431882b9277ef5c6a6^{commit}` — exit 0 — base commit exists.
- `git rev-parse --verify 918ecb809ffd345f7c956ca5308b639544154b8a^{commit}` — exit 0 — head commit exists.
- `git merge-base --is-ancestor a57b5b2717f44d839ceebb431882b9277ef5c6a6 918ecb809ffd345f7c956ca5308b639544154b8a` — exit 0 — base is an ancestor of head.
- `git status --short` — exit 0 — clean before this report overwrite; no source, test, or configuration worktree changes.
- `git diff --name-status a57b5b2717f44d839ceebb431882b9277ef5c6a6..918ecb809ffd345f7c956ca5308b639544154b8a` — exit 0 — all 12 changed paths are allowed or the report exception.
- `git log --format='%H%x09%s%n%b' --reverse a57b5b2717f44d839ceebb431882b9277ef5c6a6..918ecb809ffd345f7c956ca5308b639544154b8a` — exit 0 — eight task commits inspected; subjects use the required `SPEC-001 T<n>:` form and every commit has an accepted Claude attribution trailer.
- `git diff --check a57b5b2717f44d839ceebb431882b9277ef5c6a6..918ecb809ffd345f7c956ca5308b639544154b8a` — exit 0 — no whitespace errors.
- `uv run pytest tests/test_attempts.py tests/test_book_appointment_usecase.py -q` — exit 0 — 22 passed in 0.04s.
- `uv run pytest tests/test_architecture.py -q` — exit 0 — 3 passed in 0.05s.
- `uv run pre-commit run --all-files` — exit 0 — all hooks passed, including ruff, formatting, secrets, and mypy.
- `uv run mypy src tests/fakes.py` — exit 0 — success; no issues in 34 source files.
- `uv run pytest tests/test_postgres_adapters.py -q` — not run — Docker-backed check unavailable in this sandbox; recorded implementation-suite evidence at `7ed95e0` is 106 passed.

Contract-Checks:
- Range, scope, and commit protocol — pass — exact base-to-head diff inspected; all implementation changes are in the supplied allow-list, and each trailer is `Claude Fable 5.1` or `Claude Opus 5.5`.
- AC-03 / TC-01 40P01 handling — pass — `src/scheduler/domain/attempts.py:96-103` counts a deadlock and retains the same candidate; `tests/test_attempts.py:58-69` asserts the repeated pair and zero pruning.
- AC-03 / TC-02 classification and bound — pass — `src/scheduler/domain/attempts.py:86-104` bounds attempts at five, returns contention with candidates remaining, and returns capacity exhausted only when the list is empty; focused tests pass.
- AC-04 / TC-11 ordering and replay — pass — `src/scheduler/application/book_appointment.py:71-105` claims first, returns replays before locking, serialises before validation/candidate reads/gate/reserve, and awaits the gate once before the first reserve; `tests/test_book_appointment_usecase.py:245-263` asserts both call orders.
- D-048 advisory lock lifecycle — pass — `src/scheduler/infrastructure/postgres/unit_of_work.py:62-71` takes `pg_advisory_xact_lock` on the transaction connection; `:73-88` commits or rolls back then closes, and `tests/test_postgres_adapters.py:151-163` proves it remains held until commit.
- D-049 / AC-07 / TC-31 implementability — pass — `docs/ai/specs/SPEC-001-booking-service.md:780-825` uses an `asyncio.Barrier(8)` before POSTs and constructs `create_app` without an attempt gate. With the lock before candidate reads (`book_appointment.py:78-93`), the first four serial bookings each reserve one distinct bay and technician; the next four read no candidates, yielding the required `{201: 4, 409: 4}` and attempts total of four.
- D-050 / AC-16 / TC-39 fallback — pass — the gate is after the candidate read and before the first INSERT (`book_appointment.py:89-105`). A separately committed bypass row therefore yields a named 23P01; `_prune` removes the named bay or technician (`attempts.py:67-72`). In case (a), the shuffled first candidate is either free bay 101 (one attempt) or occupied bay 100 then bay 101 (two attempts and one prune); in case (b), the sole candidate is removed, producing one-attempt `capacity_exhausted`. `docs/ai/specs/SPEC-001-booking-service.md:253,836-837` specifies this test without turning TC-31 into an attempt-gated race.
- Layer direction and error boundary — pass — `uv run pytest tests/test_architecture.py -q` passes; domain imports only standard-library modules, application imports domain ports/types, and `book_appointment.py:136-145` catches only `Contention` rather than converting database errors to success.
- Regression and evidence review — pass — no new xfails, skips, broad exception-to-success mapping, unbounded retry, or attempt-gated TC-31 text in the amended SPEC or ADR; the adapter remains the SQLSTATE boundary.

## Accepted deviations

- `7ed95e0` cites D-048 audit cycle 1 rather than a design section or ADR in its subject. Per the cycle-3 ruling, this is an accepted recorded deviation to be listed in the status file at merge and is not a finding.

Findings:
- None.

Verdict: pass
