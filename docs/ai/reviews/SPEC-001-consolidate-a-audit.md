# SPEC-001 consolidate-a audit

Task: consolidate-a
Base: ffbf704
Head sha: c9883e5510cc64918a7525af234fdb71f8b07146
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings

None.

## Evidence

- Reviewed SPEC-001 § Execution → Interfaces, TC-01, TC-02, TC-08, TC-14, task blocks T1/T4/T5/T10, design §§2/4, and ADR-010. The single definitions now live at the SPEC locations: `Hours`, `Dealership`, `Candidate`, `Confirmed`, and `ResourceTaken` in `domain/model.py`; `AttemptResult` in `domain/attempts.py`; and `day_window_utc` in `domain/time_rules.py`.
- `git diff --name-status ffbf704..HEAD` — only `pyproject.toml`, the three allowed domain modules, and the two allowed test modules changed (this audit file is the permitted audit addition). Test hunks change imports only; `pyproject.toml` adds only `mypy_path = "src"` under `[tool.mypy]`.
- Compared the base stand-ins to `domain/model.py`: all five are frozen dataclasses with identical field names, annotations, and declaration order. The removed `windows._day_window_utc` is replaced only by `time_rules.day_window_utc`.
- DST equivalence probe (`Europe/London`, 2026-03-29 and 2026-10-25, 00:30/01:30/02:30): every default-`fold=0` old/new pair was equal. The spring gap 01:30 maps to `01:30Z`; the autumn repeated 01:30 maps to first occurrence `00:30Z`, matching `canonical_utc`'s documented `fold=0` rule.
- Inspected the domain import graph and ran `uv run python -c 'import scheduler.domain.errors, scheduler.domain.time_rules, scheduler.domain.windows'` — `errors -> attempts -> model`, `time_rules -> errors, model`, and `windows -> model, time_rules` import successfully with no cycle; domain imports are standard library or `scheduler.domain` only.
- `rg -n -i 'moved to model\\.py at merge|at merge' src tests` — no matches. `git diff ffbf704..HEAD | rg 'ERR-[0-9]+|LSN-[A-Za-z0-9_-]+'` — no matches. `git diff --check ffbf704..HEAD` — clean.
- `git log --format='%s%n%(trailers:key=Co-Authored-By,valueonly)' ffbf704..HEAD` — subjects exactly `SPEC-001 T4: relocate shared domain types into model.py (design §2, D-041)` and `SPEC-001 T1: mypy resolves src for test modules (design §4)`; each commit has a `Co-Authored-By` trailer.
- `UV_CACHE_DIR=/private/tmp/spec001-consolidate-a-uv-cache uv run pre-commit run --all-files` — all hooks passed.
- `UV_CACHE_DIR=/private/tmp/spec001-consolidate-a-uv-cache uv run mypy src` — `Success: no issues found in 16 source files`.
- `UV_CACHE_DIR=/private/tmp/spec001-consolidate-a-uv-cache uv run mypy tests/test_architecture.py tests/test_attempts.py` — `Success: no issues found in 2 source files`.
- `UV_CACHE_DIR=/private/tmp/spec001-consolidate-a-uv-cache uv run pytest -q --ignore=tests/test_seed.py` — `30 passed in 0.23s`.
- `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock UV_CACHE_DIR=/private/tmp/spec001-consolidate-a-uv-cache uv run pytest -q` — `30 passed, 2 errors in 0.49s`; both errors are `tests/test_seed.py` testcontainer setup failures because this sandbox denies Unix-socket access to `/var/run/docker.sock` (`PermissionError: [Errno 1] Operation not permitted`), so the full container-dependent gate could not be completed here.
