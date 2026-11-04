# SPEC-001 T10a audit

Task: T10a — window arithmetic (ADR-010)
Base: a919ea6fa28b7f2333018f02316c40dbccb0c557
Head sha: a2887ef51dda14dd532b50ce091b4712afec1de6
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings

None.

## Evidence

- `git diff --name-only a919ea6fa28b7f2333018f02316c40dbccb0c557..HEAD` — only `src/scheduler/domain/windows.py` and `tests/test_windows.py` changed.
- Reviewed `windows.py` against SPEC Contract Known Facts item 2, AC-06, TC-08, the domain interfaces, ADR-009, and ADR-010. `Hours` and `Dealership` match the specified fields; the local temporary definitions and `_day_window_utc` carry the accepted T4 merge comments. `merge`, `free`, and `start_windows` have the specified callable shapes and use UTC `datetime` interval tuples plus `timedelta`, which supports the planned `busy_ranges(lo, hi + duration)` call without adaptation.
- Independently recomputed the ADR-010 worked example through `start_windows` — output: `2027-03-26 2027-03-26T09:00:00+00:00 2027-03-26T11:00:00+00:00`; `2027-03-29 2027-03-29T13:00:00+00:00 2027-03-29T16:59:00+00:00`.
- Inspected `tests/test_windows.py` — exactly four test functions, one for each TC-08 clause (overlapping/touching merge, free gaps, UTC duration subtraction before local-day intersection, and the closing-minus-one-minute bound), with no additional test functions.
- Mutation probe: temporarily changed `closes - ONE_MINUTE` to `closes`; `uv run --no-sync pytest tests/test_windows.py::test_closing_bound_closes_minus_one_minute -q` — `1 failed` (produced `latest_start` 18:00Z rather than 17:59Z). Restored.
- Mutation probe: temporarily replaced UTC `gap_end - duration` with wall-time subtraction and conversion; `uv run --no-sync pytest tests/test_windows.py::test_duration_subtracted_on_utc_before_intersecting_local_day -q` — `1 failed` (produced Friday 12:00Z rather than 11:00Z). Restored.
- `git diff --exit-code HEAD -- src/scheduler/domain/windows.py` and `git status --short -- src/scheduler/domain/windows.py` — exit 0 / clean after probes.
- `uv run --no-sync pytest tests/test_windows.py tests/test_architecture.py -q` — `6 passed in 0.02s`.
- `uv run --no-sync mypy src` — `Success: no issues found in 10 source files`.
- `uv run --no-sync ruff check .` — `All checks passed!`; `uv run --no-sync ruff format --check .` — `41 files already formatted`.
- Read pre-commit gate evidence at `/private/tmp/claude-501/-Users-jp-Documents-Personal-JobSearching-NextRound-KeyLoop/9bba0762-9ade-465b-b52d-f6294bb17bbe/scratchpad/precommit-T10a.txt` — all nine hooks Passed, including gitleaks and mypy; `exit=0 at HEAD a2887ef`. `git rev-parse HEAD` returned `a2887ef51dda14dd532b50ce091b4712afec1de6`.
- Commit audit: `3052c50` message is exactly `SPEC-001 T10a: window arithmetic (ADR-010)` followed by a blank line and `Co-Authored-By`; the only later commit, `a2887ef`, starts `SPEC-001 T10a:` and also has a `Co-Authored-By` trailer.
