# SPEC-001 implementation status

Status: in-progress
Branch: feat/spec-001-booking-service
Base: f0f4117 (T0b, spec approved)

Each task appends one section: commits, test command and result line, audit file and verdict, deviations.

## T1
Commits: a919ea6 (deps, skeleton, test), ca49db0, 1d24569 and one later fix (architecture-scan gaps found by Codex cycles 1–3: nested main.py, package-root aliases, relative imports).
Tests: `uv run pytest tests/test_architecture.py -q` → 3 passed.
Audit: docs/ai/reviews/SPEC-001-T1-audit.md — pass (cycle 4; cycles 1–3 each found a distinct scan gap, all fixed in new commits).
Deviation: audit exceeded the 3-cycle bound by one, orchestrator exception (each cycle raised a new gap, none repeated).

## T2
Commits: 0292cdf (T2a schema migration + Core tables), fd19e99 (T2b test harness), 37c7f41 (downgrade drops btree_gist), 20778e0 (audit); merged add2f0b.
Tests: `uv run pytest tests/test_seed.py tests/test_architecture.py -q` → 4 passed (TC-34 constraint clauses).
Audit: docs/ai/reviews/SPEC-001-T2-audit.md — pass (cycle 2).
Notes: the GRANT is documentary under the superuser test role; testcontainers on colima needs `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock` (Makefile and README carry it, T13).

## T4
Commits: c8ed836 (domain model, time rules, canonical hash), 44c04fd (audit); merged eff7981.
Tests: `uv run pytest tests/test_time_rules.py tests/test_canonical.py -q` → 15 passed (TC-03..TC-07).
Audit: docs/ai/reviews/SPEC-001-T4-audit.md — pass (cycle 1).
Rules fixed where the SPEC was silent: a job ending exactly at closing takes pickup at the next opening; the pickup walk checks 14 local dates from the end's local date. `Contention.result` typed `Any` until T5 merged (consolidation commit).

## T5
Commits: bec479c, 42e347f (attempt policy), ffebff3 (audit); merged e783aed.
Tests: `uv run pytest tests/test_attempts.py -q` → 7 passed (TC-01, TC-02).
Audit: docs/ai/reviews/SPEC-001-T5-audit.md — pass (cycle 1; two deliberate mutations caught by the tests).
Definition fixed: `candidates_pruned` counts every candidate a loss removes, including the pair just tried. `Candidate`, `Confirmed`, `ResourceTaken` defined in attempts.py pending relocation to model.py (consolidation commit).

## T10a
Commits: 3052c50 (window arithmetic), a2887ef (tests cut to TC-08 clauses), 269d94a (audit); merged 8651cbf.
Tests: `uv run pytest tests/test_windows.py -q` → 4 passed (TC-08).
Audit: docs/ai/reviews/SPEC-001-T10a-audit.md — pass (cycle 3; cycles 1–2 were sandbox and amend-policy issues, no code findings).
Rules fixed: the "now" cutoff rounds up to the next whole minute and a start equal to now is allowed. Local `Hours`/`Dealership` stand-ins pending replacement by T4 imports (consolidation commit).

Wave A merged 2026-11-04 22:05: `uv run pytest -q` → 32 passed; pre-commit and `mypy src` green.

## T3
Commits: leg/t3 (seed migration 0002 + TC-34 seed clauses), 5941b6c (audit); merged as the commit above this line's merge.
Tests: `uv run pytest tests/test_seed.py tests/test_architecture.py -q` → 9 passed.
Audit: docs/ai/reviews/SPEC-001-T3-audit.md — pass (cycle 1).
Rules fixed: dealership 1 open Mon–Sat, dealership 2 Mon–Fri, Sunday absent; seed ids < 100 and the five seeded tables' id counters set to 99 (appointment counter untouched, it has no seed rows).

## T6
Commits: leg/t6 (T6a ports and outcomes; T6b BookAppointment use case with fakes), b6b4bf7 (audit); merged as the merge commit following this section's status commit.
Tests: `uv run pytest tests/test_book_appointment_usecase.py tests/test_architecture.py -q` → 17 passed (TC-09, TC-10, TC-11), no database. `uv run mypy src tests/fakes.py` green.
Audit: docs/ai/reviews/SPEC-001-T6-audit.md — pass (cycle 1).
Rules fixed: a replayed 201 carries the stored bay and technician in the Outcome (ADR-013: null only when not a 201); a claimed key row with no recorded outcome raises and becomes a 5xx (cannot occur for a committed row). Note for T7: the unit of work declares `appointments`, `idempotency`, `reads` with the port types, not the adapter classes.

## T7
Commits: 50ba998 (T7a reserve adapter), a974d42 (T7b read, idempotency adapters and unit of work), audit commit; merged after this section's status commit. Written inline by the orchestrator (leg cap), same contract and audit.
Tests: `uv run pytest tests/test_postgres_adapters.py -q` → 4 passed (TC-12 x2, TC-13, end-to-end BookAppointment against PostgreSQL).
Audit: docs/ai/reviews/SPEC-001-T7-audit.md — pass (cycle 1).
Notes: the read repository also carries `bays`, `busy_ranges`, `watermark` (the Protocol requires all methods for structural typing), so T10b adds no repository code.

## T9
Commits: d7c5827 (wide event middleware and health split), 83d5af3 (an exception after the response started now records 500 `error`, not final), 106d78b (audit); merged after this section's status commit.
Tests: `uv run pytest tests/test_events.py tests/test_health.py -q` → 9 passed (TC-32, TC-33).
Audit: docs/ai/reviews/SPEC-001-T9-audit.md — pass (cycle 3; cycle 1 found the started-response status gap; cycle 2 asked for a squash, declined under the commit protocol).
Rules fixed: `health.build_router(engine)` accepts any object with an async `connect()` so the interfaces layer imports no SQLAlchemy; the middleware emits only the 17 schema keys, so no handler can leak an email or VIN into the event; `SELECT 1` readiness, any exception → 503.

## T8
Commits: leg/t8 (T8a HTTP schemas, error mapping, dependencies; T8b appointments router and composition root), 1e2cca6 (T7 fix: `qualified_technicians` inner NOT EXISTS now correlated), b7af954 (audit); merged after this section's status commit.
Tests: `uv run pytest tests/test_booking_api.py tests/test_idempotency.py -q` → 36 passed (TC-15..19, 21..27, 37); TC-19's event assertion runs for real (T9 merged first, no xfail). Full suite 95 passed.
Audit: docs/ai/reviews/SPEC-001-T8-audit.md — pass (cycle 1).
Defect caught by TC-21: an uncorrelated NOT EXISTS in the T7 qualification query made every technician qualified whenever any technician held the skill; fixed in 1e2cca6 (orchestrator-approved fix inside the Contract).
Rules fixed: `route` and `idempotency_key` are written to the event before ADR-008 steps 2–3 so 400/404/422 events carry the key (ADR-013); `service_type_id` is written after schema validation; error handlers set `code` on every error response.
