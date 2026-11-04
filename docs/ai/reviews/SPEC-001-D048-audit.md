# SPEC-001 D-048 audit

Task: D-048
Base-SHA: `a57b5b2717f44d839ceebb431882b9277ef5c6a6`
Head-SHA: `9a6a68293c54d21404208fa6b1e678fbfb637aa4`
Cycle: 3
Commits:
- `440c37a SPEC-001 T7: advisory lock adapter for UnitOfWork.serialise (ADR-004 amendment, D-048)`
- `3d3e403 SPEC-001 T6: serialise bookings per dealership after the key claim (ADR-004 amendment, D-048)`
- `687fb04 SPEC-001 T5: a deadlock loss keeps the pair in the candidate list (ADR-004 amendment, D-048)`
- `5433422 SPEC-001 T0e: ADR-004 amendment and scope row for D-048 (ADR-004)`
- `752bcb4 SPEC-001 T0e: SPEC Interfaces wording for D-048 (ADR-004)`
- `7ed95e0 SPEC-001 T0e: T5 task block qualifies never-same-pair for 40P01 (D-048 audit cycle 1)`
- `9a6a682 SPEC-001 T0f: TC-31 synchronises the clients before they send, not the attempts (ADR-004, D-049; D-048 audit cycle 2)`

Allowed-Paths: `src/scheduler/application/book_appointment.py`, `src/scheduler/application/ports.py`, `src/scheduler/domain/attempts.py`, `src/scheduler/infrastructure/postgres/unit_of_work.py`, `tests/fakes.py`, `tests/test_attempts.py`, `tests/test_book_appointment_usecase.py`, `tests/test_postgres_adapters.py`, `docs/adr/ADR-004.md`, `docs/ai/lessons.md`, `docs/ai/specs/SPEC-001-booking-service.md`; exception: `docs/ai/reviews/SPEC-001-D048-audit.md`
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
- `git rev-parse --verify a57b5b2717f44d839ceebb431882b9277ef5c6a6^{commit}` — exit `0` — base exists.
- `git rev-parse --verify 9a6a68293c54d21404208fa6b1e678fbfb637aa4^{commit}` — exit `0` — head exists.
- `git merge-base --is-ancestor a57b5b2717f44d839ceebb431882b9277ef5c6a6 9a6a68293c54d21404208fa6b1e678fbfb637aa4` — exit `0` — base is an ancestor of head.
- `git status --short` — exit `0` — clean before this report overwrite; no source, test, or configuration worktree changes.
- `git diff --name-status a57b5b2717f44d839ceebb431882b9277ef5c6a6..9a6a68293c54d21404208fa6b1e678fbfb637aa4` — exit `0` — 12 changed paths, all allowed or the report exception.
- `git log --reverse --format='%h %s%n%b' a57b5b2717f44d839ceebb431882b9277ef5c6a6..9a6a68293c54d21404208fa6b1e678fbfb637aa4` — exit `0` — all seven commits have an accepted Claude attribution trailer; one subject lacks a design/ADR citation (F-002).
- `git diff --check a57b5b2717f44d839ceebb431882b9277ef5c6a6..9a6a68293c54d21404208fa6b1e678fbfb637aa4` — exit `0` — no whitespace errors.
- `uv run pytest tests/test_attempts.py tests/test_book_appointment_usecase.py -q` — exit `0` — 22 passed in 0.04s.
- `uv run pytest tests/test_architecture.py -q` — exit `0` — 3 passed in 0.06s.
- `uv run pre-commit run --all-files` — exit `0` — all hooks, including Ruff and mypy, passed.
- `uv run mypy src tests/fakes.py` — exit `0` — success, no issues in 34 source files.
- `uv run pytest tests/test_postgres_adapters.py -q` — exit `n/a` — not run: Docker-backed check is unavailable in this sandbox; implementer recorded 106 passed at `7ed95e0` and `9a6a682` changes documentation only.

Contract-Checks:
- Range, paths, and worktree — pass — exact specified range inspected; `git diff --name-status` lists only allowed paths and the report exception.
- Commit protocol and attribution — fail — all subjects have the `SPEC-001 T<n>:` prefix and accepted trailers, but `7ed95e0` cites neither a design section nor ADR (F-002).
- AC-03 / TC-01 / TC-02 — pass — `src/scheduler/domain/attempts.py:86-103` counts a 40P01 and retains its candidate, bounds five attempts, prunes named 23P01 resources, and stops vehicle conflicts; focused tests pass.
- AC-04 / TC-11 ordering — pass — `src/scheduler/application/book_appointment.py:70-105` claims first, returns replay/conflict before `serialise`, then locks before validation, reads, gate, and reserve; `tests/test_book_appointment_usecase.py:242-261` asserts the sequence and replay bypass.
- Advisory-lock lifetime — pass — `src/scheduler/infrastructure/postgres/unit_of_work.py:62-88` uses `pg_advisory_xact_lock` on the transaction connection and commits or rolls back before closing; `tests/test_postgres_adapters.py:151-163` specifies held-until-commit behavior.
- 40P01 / 23P01 adapter boundary — pass — `src/scheduler/infrastructure/postgres/repositories.py:261-274` catches those SQLSTATEs only around the savepoint INSERT, re-raises all other database errors; the D-048 domain policy preserves the deadlocked pair.
- Layer direction — pass — `tests/test_architecture.py` passed; the changed domain module imports standard-library modules only, application imports domain only, and infrastructure imports application/domain.
- D-049 gate removal — pass — SPEC AC-07 and TC-31 at `docs/ai/specs/SPEC-001-booking-service.md:205,251` and the T11 example at `:777-798` synchronise clients before POSTs and inject no attempt gate; ADR-004 says clients, not attempts, start behind a barrier.
- TC-31 event-attempt assertion — fail — under the required serial execution the first four requests each reserve once and the next four read no candidates, so `run_attempts` returns zero attempts (`src/scheduler/domain/attempts.py:86-104`); the stated `sum(e["attempts"] for e in evs) >= 8` at `docs/ai/specs/SPEC-001-booking-service.md:822` cannot hold (F-001).
- Regression / weakened-test review — pass — no new xfail, swallowed exception, broad exception-to-success mapping, or unbounded nondeterministic seam in the range; the changed tests exercise the amended behaviors.

Findings:
- [high] F-001: `docs/ai/specs/SPEC-001-booking-service.md:251,822` — TC-31/T11 still requires event attempts to sum to at least 8, but D-048 serialises the eight distinct-key requests. Four winners reserve once and the four capacity-exhausted requests have an empty candidate list and make zero attempts, for an exact total of 4. This violates the amended ADR-004 consequence and makes T11 unimplementable as specified — change the TC-31 row and T11 assertion to the deterministic total `== 4` (or another assertion consistent with four successful reserves and four zero-attempt capacity results).
- [low] F-002: `7ed95e0 subject` — the cycle-1 task commit is `SPEC-001 T0e: ... (D-048 audit cycle 1)` and cites neither a task design section nor an ADR, contrary to the SPEC commit protocol — rewrite its subject to cite the applicable source, for example `(ADR-004, D-048 audit cycle 1)`, and rebase descendants as needed.

Verdict: revise
