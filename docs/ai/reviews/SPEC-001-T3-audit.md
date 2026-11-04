# SPEC-001 T3 Audit

Task: T3 — Seed migration
Base: `ffbf7049b333b13d940fa696fb924d36982e96f7`
Head sha: `7c5ac1c64384f18b927f922737fafb95aff356d3`
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings

None.

## Evidence

- Static diff review: `git diff --name-only ffbf7049b333b13d940fa696fb924d36982e96f7..HEAD` returned only `migrations/versions/0002_seed.py` and `tests/test_seed.py`; the two pre-existing T2 schema-test function bodies are unchanged. `git diff --check` returned no errors, and no `ERR-nnn` or `LSN-*` identifier appears in the diff.
- Static migration review: `revision = "0002"`, `down_revision = "0001"`; imported `UPGRADE` expands to the required dealerships, hours (dealership 1 weekdays 0..5; dealership 2 weekdays 0..4), skills, service types and qualifications, bays, technicians, technician skills, and `setval(..., 99)` for all five serial seed tables. `DOWNGRADE` deletes the seeded join rows before their parents and resets those sequences with `setval(..., 1, false)`.
- Static DDL/fixture review: all inserted IDs are below 100; the rows satisfy `0001_schema.py` foreign keys and checks. The weekday mapping matches L-004, `DEFAULT_HOURS`, and ADR-009: 0 is Monday, no value lies outside 0..6, and Sunday (6) is absent for both dealerships.
- Static TC-34 review: `tests/test_seed.py` has four seed test functions, one per required seed clause. Each compares the complete relevant row/set, so an incorrect row in its clause fails; the service-type test also verifies the required-skill mappings needed for ADR-006 qualification.
- Static commit review: `git log -1 --format='subject=%s%ntrailers=%(trailers:key=Co-Authored-By,valueonly)' HEAD` returned subject `SPEC-001 T3: seed migration (ADR-009, D-041)` and trailer `Claude Opus 5.5 <noreply@anthropic.com>`.
- Locally run: `uv run mypy src` -> `Success: no issues found in 16 source files`.
- Locally run: `uv run pytest tests/test_architecture.py -q` -> `3 passed in 0.03s`.
- Database-backed seed tests were not run locally because this sandbox has no Docker; verified by static inspection instead.
- Implementer-supplied: `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest tests/test_seed.py tests/test_architecture.py -q` -> `9 passed in 2.43s` (before migration: `4 failed, 2 passed`).
- Implementer-supplied: `uv run pre-commit run --all-files` -> all hooks passed; `uv run mypy src` -> `Success: no issues found in 16 source files`.
- Implementer-supplied live probe (Postgres 16): `alembic upgrade head` produced only the specified opening-hour rows, all five next sequence values were 100, seed relations/rows matched the T3 content, and `alembic downgrade 0001` left all eight seeded tables empty with next dealership ID 1; upgrade again produced two dealerships.
