# SPEC-001 T4 Audit

Task: T4 — Domain model, time rules, canonical hash
Base: `a919ea6fa28b7f2333018f02316c40dbccb0c557`
Head: `c8ed8361b7f5263748c63500d7a046fcf359f743`
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings

None.

## Evidence

- `git diff --name-status a919ea6fa28b7f2333018f02316c40dbccb0c557..HEAD` — exactly the six approved T4 paths changed.
- `git log -1 --format='%H%n%B'` — subject is exactly `SPEC-001 T4: domain model, time rules, canonical hash (ADR-008, ADR-009)` and includes `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- `git diff --check a919ea6fa28b7f2333018f02316c40dbccb0c557..HEAD` — no output (clean).
- `UV_CACHE_DIR=/private/tmp/uv-t4-audit uv run pytest tests/test_time_rules.py tests/test_canonical.py tests/test_architecture.py -q` — `17 passed in 0.03s`.
- `UV_CACHE_DIR=/private/tmp/uv-t4-audit uv run python -c ...` (DST and boundary probes) — London 2027-03-28 01:00 and 01:59 raised `GapTime`; 02:00 converted to `2027-03-28T01:00:00+00:00`; London fall-back 01:30 converted to `2027-10-31T00:30:00+00:00`; ZoneInfo input plus 120 elapsed minutes returned `2027-03-28T02:30:00+00:00`; an end exactly at closing returned next-day opening; the Ho Chi Minh UTC/local-date probe returned `2027-03-26T01:00:00+00:00`.
- `UV_CACHE_DIR=/private/tmp/uv-t4-audit uv run pre-commit run --all-files` — all hooks passed, including ruff check/format and mypy.
- `UV_CACHE_DIR=/private/tmp/uv-t4-audit uv run mypy src` — `Success: no issues found in 13 source files`.
- Manual source review against SPEC § Contract Known Facts item 7, AC-04/AC-05, TC-03–TC-07, Interfaces, ADR-008/ADR-009, and design §2–§3 — domain types are frozen dataclasses; `Any` on `Contention.result` is acceptable for this T4-only base because `AttemptResult` belongs to T5; the SPEC-named exception `# noqa: N818` annotations are appropriate; domain imports are standard-library plus intra-domain imports only.
