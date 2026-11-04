# SPEC-001 T2 audit

Task: T2 — Schema migration and Core tables
Base: a919ea6fa28b7f2333018f02316c40dbccb0c557
Head sha: 37c7f410be707b97e345cc6c6bd640f42ab41df2
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings

None.

## Evidence

- `git diff --name-status a919ea6fa28b7f2333018f02316c40dbccb0c557..HEAD` — only the five T2 paths changed: `migrations/env.py`, `migrations/versions/0001_schema.py`, `src/scheduler/infrastructure/postgres/schema.py`, `tests/conftest.py`, and `tests/test_seed.py`. `pyproject.toml`, `uv.lock`, and `docs/ai/specs/SPEC-001-status.md` are unchanged.
- `git log ... a919ea6...HEAD` — required subjects are exact and each required commit has a `Co-Authored-By` trailer. Fix commit `37c7f41` is a new commit and drops `btree_gist` last.
- Extracted the T2 SQL block and compared it with `UPGRADE`, whitespace-normalised — `spec statements=12 upgrade entries=12`; `whitespace-normalized exact all=True differences=[]`.
- Static downgrade check — `downgrade_reverses_ddl=True`; `extension_is_last=True`.
- Static Core metadata inspection — ten ERD tables present; appointment metadata has `bay_in_dealership`, `technician_in_dealership`, `valid_range`, `no_bay_overlap`, `no_technician_overlap`, and `no_vehicle_overlap`. `migrations/env.py` imports this metadata and assigns `target_metadata = metadata`.
- Reviewed `tests/conftest.py` and `tests/test_seed.py` — harness uses a session PostgreSQL 16 testcontainer migrated by Alembic, a function-scoped async psycopg engine with specified cleanup, the four T11-compatible helpers, the ADR-013 overlap query, and a ten-second `asyncio.Barrier`; TC-34's two T2 clauses are each exercised by one test.
- `UV_CACHE_DIR=/tmp/spec001-t2-audit-uv-cache uv run mypy src` — `Success: no issues found in 10 source files`.
- `UV_CACHE_DIR=/tmp/spec001-t2-audit-uv-cache uv run pytest tests/test_architecture.py -q` — `2 passed in 0.01s`.
- `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest tests/test_seed.py tests/test_architecture.py -q` — architecture tests passed; the two database-backed seed tests were unverified because the sandbox denies Docker socket access (`PermissionError: [Errno 1] Operation not permitted`). Consequently the requested live throwaway probe, Alembic `compare_metadata`, and migration round trip were also not runnable here. Cross-checked against the supplied implementer evidence: seed/architecture suite `4 passed`; probe covered all three named exclusion constraints, half-open back-to-back ranges, tenancy foreign keys, and `valid_range`; compare metadata was empty; and the upgrade/downgrade/upgrade round trip left no tables and no `btree_gist` after downgrade.
- `UV_CACHE_DIR=/tmp/spec001-t2-audit-uv-cache PRE_COMMIT_HOME=/tmp/spec001-t2-audit-precommit uv run pre-commit run --all-files` — unverified: pre-commit could not initialize because this sandbox cannot resolve `github.com` (`fatal: ... Could not resolve host`).
