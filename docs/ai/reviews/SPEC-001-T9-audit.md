# SPEC-001 T9 Audit

Task: T9 — Wide events and health
Base: `877284d86bfcb39517a78555741340829b70471e`
Head sha: `83d5af3c9bdc7cc5f19091035a839b8e1c104d92`
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings

None

## Evidence

- `git diff --name-status 877284d86bfcb39517a78555741340829b70471e..HEAD` — only `src/scheduler/interfaces/http/events.py`, `src/scheduler/interfaces/http/health.py`, `tests/test_events.py`, and `tests/test_health.py` changed; `git diff --check` returned exit 0.
- Static review — the middleware creates the ordered 17-key v1 event before handlers run, projects emission to precisely those keys in order through call-time `sys.stdout`, applies ADR-013 null defaults, derives matched-route names, forces `final=false` for 5xx, and emits a `500`/`error` event for unhandled exceptions (including after response start). No body or path value is copied into an event field except the validated numeric `dealership_id`.
- Static review — `health.build_router(engine)` names `health_live` and `health_ready`; live is constant 200, ready executes `SELECT 1` and maps every exception to the specified 503 body. `src/scheduler/interfaces` has no SQLAlchemy import.
- `uv run mypy /tmp/spec001_t9_health_protocol_probe.py` — `Success: no issues found in 1 source file`; an `AsyncEngine` structurally satisfies `Connectable`. The temporary probe was deleted.
- TC-32 review — six independent, non-vacuous test functions cover one line per response; literal 17-key order and `v == 1`; final values for 201/final 409/422 and contention; health null booking fields; and email/VIN exclusion. TC-33 has separate live-200, ready-200 against the testcontainers engine, and closed-port-503 functions.
- `export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock; uv run pytest tests/test_events.py tests/test_health.py tests/test_architecture.py -q` — sandbox run reached `11 passed, 1 error`; the sole error was the ready-200 test being unable to access Docker (`PermissionError: [Errno 1] Operation not permitted`), the stated sandbox limitation. The implementer’s outside-sandbox result was `12 passed in 2.44s`.
- `uv run pytest tests/test_events.py tests/test_architecture.py -q` — `9 passed in 0.24s`.
- `uv run pre-commit run --all-files` — all hooks passed.
- `uv run mypy src` — `Success: no issues found in 18 source files`.
- Commit review — task commit `d7c5827` has the exact required T9 subject and `Co-Authored-By` trailer; follow-up T9 commit `83d5af3` follows the D-040 protocol form and has the trailer. History is retained as required.
- Diff scan for `ERR-nnn` and `LSN-*` identifiers — no matches.
