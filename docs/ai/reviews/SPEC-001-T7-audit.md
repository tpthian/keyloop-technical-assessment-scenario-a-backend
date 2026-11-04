# SPEC-001 T7 Audit

Task: T7 — PostgreSQL adapters and unit of work
Base: `45e069f19d62522bd64c89c582d3ff26f7b0fc99`
Head sha: `a974d423539029c8a56d86084fafa32f8cf05ffc`
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings

None.

## Evidence

- The base-to-HEAD diff contains exactly the five T7 paths: `src/scheduler/infrastructure/clock.py`, `src/scheduler/infrastructure/postgres/engine.py`, `src/scheduler/infrastructure/postgres/repositories.py`, `src/scheduler/infrastructure/postgres/unit_of_work.py`, and `tests/test_postgres_adapters.py`. `git diff --check` is clean.
- The two commits exactly match the task block: `SPEC-001 T7a: reserve adapter with savepoint and SQLSTATE boundary (ADR-004)` and `SPEC-001 T7b: read, idempotency adapters and unit of work (ADR-008)`.
- `PostgresAppointmentRepository.reserve` creates one `begin_nested()` savepoint per call around only the appointment insert; it maps psycopg SQLSTATE `23P01` to `ResourceTaken(orig.diag.constraint_name, False)` and `40P01` to `ResourceTaken(None, True)`, re-raises every other `DBAPIError`, and returns `Confirmed` with the returned appointment id.
- `claim` uses PostgreSQL `INSERT ... ON CONFLICT DO NOTHING ... RETURNING`, then selects and returns `StoredResponse` when the key already exists. `record` updates by both dealership id and key. `free_candidates` runs independent free-bay and free-qualified-technician `NOT EXISTS` queries and forms their ordered cross product without shuffling. `qualified_technicians` uses the required double-`NOT EXISTS` form, so an empty required-skill set qualifies all dealership technicians.
- `PostgresUnitOfWork.__aenter__` opens one connection, begins it, applies `SET LOCAL deadlock_timeout = '100ms'` and `SET LOCAL statement_timeout = '2s'`, and constructs all three adapters over that connection. Its attributes are annotated with the application port types; exit commits on success or rolls back on an exception, then closes the connection. `PostgresSchedulingReadRepository` accepts both `engine.connect` and the unit of work's one-connection context.
- The infrastructure imports are limited to application/domain modules, sibling infrastructure modules, and persistence/standard-library dependencies; no interface-layer import is introduced.
- `tests/test_postgres_adapters.py` contains the TC-12 reserve/transaction-continuation and non-constraint propagation coverage, the TC-13 idempotency/candidate coverage, and one real-adapter end-to-end booking run, with no unrelated test case. The supplied testcontainers result is `4 passed in 2.43s`; Docker is unavailable in this audit sandbox, so SQL and the SQLSTATE boundary were verified by source inspection.
