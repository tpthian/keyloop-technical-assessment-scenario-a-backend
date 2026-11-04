# SPEC-001 final gate audit

Task: SPEC-001 whole, final gate
Base-SHA: `bdb70d0cf04d40f226a6f882cdea3fb4a50e1c8a`
Head-SHA: `377e994eb4733b6478895524870904fa51684664`
Commits:
- 92 preceding SPEC-001 task, status, amendment, audit, and merge commits (97 commits in range total)
- `6a3a0e4 SPEC-001 T13: README evidence, test table and known limitations (design §3, ADR-004, ADR-013)`
- `f208fdf SPEC-001 T2: remove the unused barrier_gate helper (design §5, D-049)`
- `d984a7c SPEC-001 T13: coherence pass, ADR-004 ordering and pool note (design §3, ADR-004, ADR-012)`
- `ca609d9 SPEC-001 T13: coherence fixes cycle 1 (design §3, ADR-004)`
- `377e994 SPEC-001 T13: Codex coherence cross-check (pass)`

Allowed-Paths: `all (whole-SPEC gate)`
Changed-Paths:
- `M .github/workflows/ci.yml`
- `M Makefile`
- `M README.md`
- `M docker-compose.yml`
- `M docs/adr/ADR-004.md`
- `M docs/adr/ADR-008.md`
- `A docs/ai/lessons.md`
- `A docs/ai/reviews/SPEC-001-D048-audit.md`
- `A docs/ai/reviews/SPEC-001-T1-audit.md`
- `A docs/ai/reviews/SPEC-001-T10a-audit.md`
- `A docs/ai/reviews/SPEC-001-T10b-audit.md`
- `A docs/ai/reviews/SPEC-001-T11-audit.md`
- `A docs/ai/reviews/SPEC-001-T12-audit.md`
- `A docs/ai/reviews/SPEC-001-T13-audit.md`
- `A docs/ai/reviews/SPEC-001-T2-audit.md`
- `A docs/ai/reviews/SPEC-001-T3-audit.md`
- `A docs/ai/reviews/SPEC-001-T4-audit.md`
- `A docs/ai/reviews/SPEC-001-T5-audit.md`
- `A docs/ai/reviews/SPEC-001-T6-audit.md`
- `A docs/ai/reviews/SPEC-001-T7-audit.md`
- `A docs/ai/reviews/SPEC-001-T8-audit.md`
- `A docs/ai/reviews/SPEC-001-T9-audit.md`
- `A docs/ai/reviews/SPEC-001-coherence-crosscheck.md`
- `A docs/ai/reviews/SPEC-001-consolidate-a-audit.md`
- `A docs/ai/reviews/SPEC-001-spec-review.md`
- `A docs/ai/specs/SPEC-001-booking-service.md`
- `A docs/ai/specs/SPEC-001-status.md`
- `M docs/design.md`
- `M migrations/env.py`
- `A migrations/versions/0001_schema.py`
- `A migrations/versions/0002_seed.py`
- `M pyproject.toml`
- `D scripts/.gitkeep`
- `A scripts/demo.sh`
- `A src/scheduler/application/__init__.py`
- `A src/scheduler/application/book_appointment.py`
- `A src/scheduler/application/get_appointment.py`
- `A src/scheduler/application/get_availability.py`
- `A src/scheduler/application/outcomes.py`
- `A src/scheduler/application/ports.py`
- `A src/scheduler/application/presenters.py`
- `A src/scheduler/domain/__init__.py`
- `A src/scheduler/domain/attempts.py`
- `A src/scheduler/domain/canonical.py`
- `A src/scheduler/domain/errors.py`
- `A src/scheduler/domain/model.py`
- `A src/scheduler/domain/time_rules.py`
- `A src/scheduler/domain/windows.py`
- `A src/scheduler/infrastructure/__init__.py`
- `A src/scheduler/infrastructure/clock.py`
- `A src/scheduler/infrastructure/postgres/__init__.py`
- `A src/scheduler/infrastructure/postgres/engine.py`
- `A src/scheduler/infrastructure/postgres/repositories.py`
- `A src/scheduler/infrastructure/postgres/schema.py`
- `A src/scheduler/infrastructure/postgres/unit_of_work.py`
- `A src/scheduler/interfaces/__init__.py`
- `A src/scheduler/interfaces/http/__init__.py`
- `A src/scheduler/interfaces/http/appointments.py`
- `A src/scheduler/interfaces/http/availability.py`
- `A src/scheduler/interfaces/http/dependencies.py`
- `A src/scheduler/interfaces/http/errors.py`
- `A src/scheduler/interfaces/http/events.py`
- `A src/scheduler/interfaces/http/health.py`
- `A src/scheduler/interfaces/http/schemas.py`
- `M src/scheduler/main.py`
- `A tests/conftest.py`
- `A tests/fakes.py`
- `A tests/test_architecture.py`
- `A tests/test_attempts.py`
- `A tests/test_availability.py`
- `A tests/test_book_appointment_usecase.py`
- `A tests/test_booking_api.py`
- `A tests/test_canonical.py`
- `A tests/test_concurrency.py`
- `A tests/test_events.py`
- `M tests/test_health.py`
- `A tests/test_idempotency.py`
- `A tests/test_postgres_adapters.py`
- `A tests/test_seed.py`
- `A tests/test_time_rules.py`
- `A tests/test_windows.py`
- `M uv.lock`

Checks:
- `git rev-parse bdb70d0cf04d40f226a6f882cdea3fb4a50e1c8a^{commit} && git rev-parse 377e994^{commit}` — exit `0` — exact base and head resolve to the stated commits.
- `git merge-base --is-ancestor bdb70d0cf04d40f226a6f882cdea3fb4a50e1c8a 377e994` — exit `0` — base is an ancestor of head.
- `git status --short` — exit `0` — clean before this report was added.
- `git diff --name-status bdb70d0cf04d40f226a6f882cdea3fb4a50e1c8a..377e994` — exit `0` — changed paths listed above; every implementation change maps to a SPEC task path or D-044/D-045/D-048/D-049/D-050, with review files as audit artifacts.
- `git diff --check bdb70d0cf04d40f226a6f882cdea3fb4a50e1c8a..377e994` — exit `0` — no whitespace errors.
- `git log --format='%H%x09%s%n%b' --reverse bdb70d0cf04d40f226a6f882cdea3fb4a50e1c8a..377e994` — exit `0` — 97 commits inspected; closing-leg commits all have `Co-Authored-By` trailers; one older subject deviation is recorded below.
- `uv run pytest -q` — exit `1` — 52 passed; 57 database-backed tests errored only during testcontainers setup because this sandbox cannot create/mount the Colima Docker socket. Supplied head evidence on macOS/Colima is `109 passed in 6.56s`.
- `uv run pytest tests/test_architecture.py -q` — exit `0` — `3 passed in 0.15s`.
- `uv run pre-commit run --all-files` — exit `0` — all hooks passed, including ruff, formatting, hardcoded-secret detection, and mypy.
- `uv run mypy src tests/fakes.py` — exit `0` — `Success: no issues found in 34 source files`.
- `grep -Ec '^## (API|Running the demo|Testing)$' README.md` — exit `0` — `3`; line 3 is the required implemented status and the zero-context README diff has only that line and the three named sections.

Contract-Checks:
- `Scope, task paths, and D-040 history` — pass — full range and 97 subjects inspected; task paths, D-044 fixture, D-045 CI evidence, and D-048/D-049/D-050 amendments account for implementation changes. Closing-leg trailers are present.
- `AC-01 / TC-34` — pass — `tests/test_seed.py:50,58,72,82,99,108` asserts extension, constraints, and every seed clause; migration DDL is `migrations/versions/0001_schema.py:27` and seed data is `0002_seed.py:50`.
- `AC-02 / TC-13, TC-25–TC-27` — pass — `tests/test_postgres_adapters.py:100` and `tests/test_booking_api.py:206,236,249,274` assert claim/candidates, GET body, adjacent slots, 201 fields, UTC duration, pickup and vehicle key.
- `AC-03 / TC-01, TC-02, TC-11, TC-12, TC-22, TC-23` — pass — `tests/test_attempts.py:42–111`, `tests/test_book_appointment_usecase.py:183–263`, `tests/test_postgres_adapters.py:58,83`, and `tests/test_booking_api.py:129,160,172` assert pruning, bound, stored finals, rollback contention, savepoint mapping, and 409s.
- `AC-04 / TC-07, TC-09, TC-11, TC-13, TC-15–TC-20, TC-37` — pass — `tests/test_canonical.py:45–74`, `tests/test_book_appointment_usecase.py:107–123`, `tests/test_idempotency.py:73–212`, and `tests/test_concurrency.py:62` cover hashing, claim/replay, every pre-transaction boundary, stored business outcomes, concurrent same-key replay, and ADR-008 precedence.
- `AC-05 / TC-03–TC-06, TC-10, TC-18, TC-21` — pass — `tests/test_time_rules.py:36–90`, `tests/test_book_appointment_usecase.py:150–174`, `tests/test_idempotency.py:141`, and `tests/test_booking_api.py:80–116` assert DST, hours, elapsed duration, pickup, stored failures, and API cases.
- `AC-06 / TC-08, TC-28–TC-30` — pass — `tests/test_windows.py:36–80` and `tests/test_availability.py:73–188` assert interval arithmetic, limits, exact London windows, UTC watermark, open-day bounds, and Sunday absence.
- `AC-07 / TC-20, TC-31` — pass — `tests/test_concurrency.py:62–145` uses a client-side `asyncio.Barrier`, a test-owned 4×4 fixture, exact 4/4 statuses, distinct winners, eight recorded keys, zero overlaps, and event attempts total four; supplied head evidence has 19 green V-002 runs.
- `AC-08 / TC-10, TC-21, TC-23, TC-24` — pass — `tests/test_book_appointment_usecase.py:174`, `tests/test_booking_api.py:88,172,189,195` assert qualification, empty capacity, and both tenancy foreign keys.
- `AC-09 / TC-33` — pass — `tests/test_health.py:40–52` asserts live 200, ready 200, and unreachable-ready 503.
- `AC-10 / TC-31, TC-32` — pass — `tests/test_concurrency.py:132–145` and `tests/test_events.py:124–163` assert booking counters, one ordered 17-key event, final classification, health nulls, and no email/VIN; emission is projected to `EVENT_KEYS` in `src/scheduler/interfaces/http/events.py:33–112`.
- `AC-11 / TC-35` — pass — `scripts/demo.sh:1–228` implements sections 1–8 and terminal overlap assertion; supplied fresh compose evidence exits 0 with final line `0` and the seeded 2/6 race split.
- `AC-12 / TC-36` — pass — required local support checks pass above; supplied head database run is 109 passing tests and the recorded CI-equivalent evidence is green.
- `AC-13 / TC-38` — pass — `README.md:3,45,115,137` and the recorded heading/hunk inspection satisfy the exact README contract.
- `AC-14 / TC-14` — pass — `tests/test_architecture.py:20–121` statically rejects forbidden direction and non-root dual-outer-layer imports; focused command passed.
- `AC-15 / TC-09–TC-11` — pass — fake-backed use-case assertions in `tests/test_book_appointment_usecase.py:107–263`; Protocol conformance is included in the passing mypy command.
- `AC-16 / TC-39` — pass — `tests/test_concurrency.py:149–225` commits the bypass through a separate `engine.begin()` transaction and asserts both remaining-pair 201 and clean one-pair exhaustion, counters, no deadlock, no overlap, and three rows.
- `D-048/D-049/D-050 semantics` — pass — lock is after a new claim and before validation/candidates in `src/scheduler/application/book_appointment.py:71–105`; transaction-scoped advisory lock is `src/scheduler/infrastructure/postgres/unit_of_work.py:62–71`; INSERT-only savepoint/SQLSTATE handling is `src/scheduler/infrastructure/postgres/repositories.py:261–274`; docs agree at `docs/design.md:137`, `docs/adr/ADR-004.md:103`, and SPEC TC rows `:252–253`.
- `Documentation, fixture, and evidence coherence` — pass — README demo describes seed 2×2 while TC-31 is explicitly test-owned 4×4; no active `OUTPUT-PENDING`/`TODO` marker exists in README, design, ADRs, or the SPEC; historical status entries are closed at `docs/ai/specs/SPEC-001-status.md:113`.
- `D-046 lesson IDs and regression hygiene` — pass — source/current contract docs use only the ledger’s `L-nnn` IDs; no active `ERR-`/`LSN-`, xfail, skip, broad database-error-to-success mapping, secret, or PII event path found. The three acknowledged stale test-seam comments remain accepted non-findings per the task instruction.

Findings:
- [low] F-001: `9e3ae18` — `SPEC-001 consolidate-a: Codex audit (pass)` does not use one of D-040’s permitted `SPEC-001 T<n>:`, `status:`, `D-048:`, or merge forms, and its missing design/ADR citation is not listed among the status file’s accepted deviations — record this historical audit-only deviation in `docs/ai/specs/SPEC-001-status.md`; do not rewrite history.

Verdict: pass
