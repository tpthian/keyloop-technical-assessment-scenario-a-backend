# SPEC-001 T10b Audit — Cycle 2

Task: T10b — GetAvailability use case and route (ADR-010)
Base: `a51ee968628fe85b67a74bae3fc38f80335fdb56`
Head: `abb2521862a63f61dbf045d9bb9f973aa5593add`
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings (Cycle 2)

None.

## Escalated (outside task scope)

- `src/scheduler/interfaces/http/availability.py:24` — The SPEC HTTP-layer paragraph assigns
  `AvailabilityOut` and `Window` to `schemas.py`, while the approved T10 path list excludes
  `schemas.py` and the Base-to-Head diff correctly leaves it untouched. The locally defined
  `AvailabilityOut` and `WindowOut` accurately document the implemented wire contract, so this
  is not a T10b blocking defect. The implementer's ESCALATE item requires an authorized
  follow-up `schemas.py` change or a SPEC ownership clarification; it must not broaden T10b.

## Evidence

- `git diff --name-status a51ee968628fe85b67a74bae3fc38f80335fdb56..HEAD` → exactly the five approved T10b paths changed: `get_availability.py`, `availability.py`, `dependencies.py`, `main.py`, and `test_availability.py`; `pyproject.toml`, `uv.lock`, the status file, and `schemas.py` are untouched.
- `git diff --check a51ee968628fe85b67a74bae3fc38f80335fdb56..HEAD` → no whitespace errors.
- `UV_CACHE_DIR=/private/tmp/keyloop-t10b-cycle2-uv-cache uv run mypy src tests/fakes.py` → `Success: no issues found in 34 source files`.
- `UV_CACHE_DIR=/private/tmp/keyloop-t10b-cycle2-uv-cache uv run pytest tests/test_architecture.py -q` → `3 passed in 0.05s`.
- `git show -s --format='%H%n%s%n%b' 60c31155a26600b62c9ec742a76987cd1725dbed` → delivery commit subject is exactly `SPEC-001 T10b: GetAvailability use case and route (ADR-010)` and includes a `Co-Authored-By` trailer. The Cycle-2 correction commit `abb2521` also includes that trailer.
- Contract/code inspection → validation order, dealership-zone day calculation, `[from, to)` days, watermark-before-busy read, busy-range coverage, UTC `Z` serialization, inclusive `closes - 1 min` bounds, route/error/event behavior, one shared clock, and sorted windows conform to SPEC § Execution Interfaces, AC-06, ADR-010, ADR-013, and design §3.
- Test inspection → TC-28 has one HTTP function for each listed validation/404 clause; TC-29 asserts exactly Friday `[09:00Z, 11:00Z]`, Monday `[13:00Z, 16:59Z]`, and an aware UTC `as_of`; TC-30 covers every open day and Sunday absence using `create_app(engine=..., clock=FixedClock(2027-03-25T16:00Z))`.
- Implementer-provided post-fix gates (Docker is unavailable in this audit sandbox): targeted pytest → `12 passed`; full suite → `104 passed`; mypy → `Success: no issues found in 34 source files`; pre-commit → every hook Passed.
