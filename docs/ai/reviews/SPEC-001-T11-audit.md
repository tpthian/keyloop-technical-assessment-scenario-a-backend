# SPEC-001 T11 audit

Task: T11
Base-SHA: `a74854914439cafed2faa2466d9f8478e02442f7`
Head-SHA: `8371f714c059bcf786bae3da1516f8935777de23`
Commits:
- `8371f714c059bcf786bae3da1516f8935777de23 SPEC-001 T11: V-002 concurrency evidence and parallel same-key test (design §3, ADR-013)`

Allowed-Paths: `tests/test_concurrency.py`
Changed-Paths:
- `A tests/test_concurrency.py`

Checks:
- `git rev-parse --verify a74854914439cafed2faa2466d9f8478e02442f7^{commit} && git rev-parse --verify 8371f71^{commit} && git rev-parse HEAD` — exit `0` — base and head resolve; HEAD is `8371f714c059bcf786bae3da1516f8935777de23`.
- `git merge-base --is-ancestor a74854914439cafed2faa2466d9f8478e02442f7 8371f71` — exit `0` — base is an ancestor of head.
- `git status --short` — exit `0` — clean before creation of this permitted audit report; no source, test, or configuration changes outside the report path.
- `git diff --name-status a74854914439cafed2faa2466d9f8478e02442f7..8371f71 && git diff --check a74854914439cafed2faa2466d9f8478e02442f7..8371f71` — exit `0` — only `A tests/test_concurrency.py`; no whitespace errors.
- `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest tests/test_concurrency.py -q -s` — exit `2` — not runnable: sandbox denies uv's default cache path before pytest starts.
- `UV_CACHE_DIR=/private/tmp/spec001-t11-uv-cache TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest tests/test_concurrency.py -q -s` — exit `1` — not runnable: testcontainers cannot access `/var/run/docker.sock` (`PermissionError: Operation not permitted`); all three tests fail only at PostgreSQL-container setup. Supplied leg evidence for head records the required three done-when runs as exit 0, `3 passed` each, with V-002 statuses `{201: 4, 409: 4}`, attempts `4`, deadlocks `0`, candidates_pruned `0`, overlap `0`.
- `UV_CACHE_DIR=/private/tmp/spec001-t11-uv-cache uv run pytest tests/test_architecture.py -q` — exit `0` — `3 passed in 0.05s`.
- `UV_CACHE_DIR=/private/tmp/spec001-t11-uv-cache uv run pre-commit run --all-files` — exit `0` — all hooks passed, including ruff, gitleaks, and mypy.
- `UV_CACHE_DIR=/private/tmp/spec001-t11-uv-cache uv run mypy src` — exit `0` — `Success: no issues found in 33 source files`.
- `UV_CACHE_DIR=/private/tmp/spec001-t11-uv-cache uv run mypy src tests/fakes.py tests/test_concurrency.py` — exit `0` — `Success: no issues found in 35 source files`.

Contract-Checks:
- `Commit protocol` — pass — `8371f71` uses the required `SPEC-001 T11:` subject form, cites design §3 and ADR-013, and includes `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- `Allowed implementation paths` — pass — exact range adds only `tests/test_concurrency.py`; no implementation, configuration, dependency, fixture, lockfile, or status-file change.
- `TC-20 / AC-04, AC-07` — pass — `tests/test_concurrency.py:62-82` sends two concurrent same-key/same-body POSTs and asserts both 201, identical body/appointment id, exactly one appointment, and one idempotency row; the claim/replay transaction semantics are implemented at `src/scheduler/infrastructure/postgres/repositories.py:287-311`.
- `TC-31 / AC-07 / D-044, D-048, D-049 / L-001, L-002` — pass — `tests/test_concurrency.py:85-146` creates a test-owned 4-bay/4-qualified-technician dealership, releases eight clients with `asyncio.Barrier(8)`, asserts the exact 4/4 status split and `capacity_exhausted` losers, distinct winner bays and technicians, zero overlaps, four appointments, eight recorded key rows, eight booking events, and summed attempts of four; it prints the required V-002 evidence. The supplied three captured head runs each report `3 passed`, zero overlaps, zero deadlocks, and the stipulated split.
- `TC-39 / AC-16 / D-050` — pass — `tests/test_concurrency.py:149-225` injects a separate committed `engine.begin()` writer at the post-candidate/pre-reserve attempt-gate seam, without `serialise`; it asserts the free-pair 201 path and the one-pair final `capacity_exhausted` path, their attempt/pruning/deadlock event fields, zero overlaps, and three persisted appointments.
- `Savepoint, SQLSTATE, and locking boundaries` — pass — `src/scheduler/application/book_appointment.py:92-145` serialises only after a new claim and before validation/candidates/gate; `src/scheduler/infrastructure/postgres/unit_of_work.py:42-71` starts one transaction, sets the production 100 ms deadlock timeout and 2 s statement timeout, then uses transaction-scoped `pg_advisory_xact_lock`; `src/scheduler/infrastructure/postgres/repositories.py:261-274` scopes savepoint recovery and SQLSTATE mapping to the appointment INSERT, re-raising all other failures.
- `AC-10 / ADR-013 event evidence` — pass — `tests/test_concurrency.py:134-145` asserts one booking event per V-002 request and its attempt/deadlock/pruning evidence; `src/scheduler/interfaces/http/events.py:34-52,80-83` emits exactly the ordered 17-key allow-list, excluding email, VIN, and `vehicle_key`.
- `ADR-008 route order and layer direction` — pass — `src/scheduler/interfaces/http/appointments.py:54-95` performs UUID/key handling, JSON parse, dealership load, schema validation, then the use case; `tests/test_architecture.py:19-99` and its passing check enforce the stated four-layer import direction.
- `Regression safeguards` — pass — the added tests contain no xfail, exception suppression, broad exception-to-success mapping, unbounded race seam, secret, PII event assertion, or false local execution claim; Docker execution is explicitly marked unavailable and the supplied head-specific evidence is distinguished from local results.

Findings:
- None.

Verdict: pass
