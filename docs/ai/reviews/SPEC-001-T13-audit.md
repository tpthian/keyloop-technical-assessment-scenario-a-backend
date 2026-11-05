# SPEC-001 T13 audit

Task: T13 — CI, README, gates
Base: `a51ee968628fe85b67a74bae3fc38f80335fdb56`
Head sha: `682a527524b4622b8aa4e8867d379ac6dd47c4ad`
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings (Cycle 2)

None.

## Pending

- T10b: `tests/test_availability.py` is intentionally absent. Its README row agrees with TC-28–30. The live demo therefore stops at section 6 with the expected current-tree 404; this is not a T13 finding.
- T11: `tests/test_concurrency.py` is intentionally absent. Its README row agrees with TC-20 and TC-31. `OUTPUT-PENDING-T11` remains for the orchestrator to replace with the T11 `V-002:` line at merge; this is not a T13 finding.

## Escalations (not T13 defects)

- Cycle-1 TC-38 portability: the approved literal `grep -c '^## API$\|^## Running the demo$\|^## Testing$' README.md` is GNU-BRE dependent. It returns `3` with GNU grep 3.11 (the Linux CI family) and `1` with the audit host's BSD grep 2.6.0; the portable ERE equivalent returns `3` on both. The README content meets AC-13, and changing the command requires an approved SPEC amendment, not a T13-path change.
- Cycle-1 status record: `docs/ai/specs/SPEC-001-status.md` is orchestrator-owned under the leg contract. The leg supplied the gate and TC-38 evidence below for the orchestrator to record at merge; its later `Status: awaiting-audit` update is not a T13 deliverable defect.

## Evidence

- Scope: `git diff a51ee968628fe85b67a74bae3fc38f80335fdb56..HEAD -- .github README.md Makefile` changes CI, README, and the Makefile. `9e95aa0` changes only those three files; `8e1a964` changes CI and README only. `git diff --quiet f9c64ec..HEAD -- .github README.md Makefile` reports no later change to T13 paths.
- The Makefile socket override is the expressly orchestrator-directed addition outside T13's listed paths. It is correct: `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE ?= /var/run/docker.sock` is overridable and `make test` exports it only to pytest. The supplied `make test` result is green. The `demo` target in the base-to-head diff is T12 work.
- CI: `rg -n 'services:|postgres:|DATABASE_URL|^      - run: uv (sync|run pre-commit run --all-files|run mypy src tests/fakes.py|run pytest -q)$' .github/workflows/ci.yml` finds only the four required run commands at lines 17–20; there is no PostgreSQL service or `DATABASE_URL`. The `tests/fakes.py` addition is an intentional, valid extension of T13's shorter `uv run mypy src`: AC-15 and the T6 fakes requirement expressly require mypy structural conformance against the Protocols.
- Gates from `runbook/raw/legs/T13-gates-output.txt`: `uv run pre-commit run --all-files` exit 0; `uv run mypy src tests/fakes.py` → `Success: no issues found in 32 source files`; `uv run pytest -q` → `95 passed in 9.69s`; `make lint` exit 0; `make test` → `95 passed in 5.92s`.
- TC-38: the literal host command `grep -c '^## API$\|^## Running the demo$\|^## Testing$' README.md` → `1` (BSD grep portability item above); `grep -Ec '^## (API|Running the demo|Testing)$' README.md` → `3`; `sed -n '3p' README.md` → `Status: implemented; see Testing for the evidence.`; `git diff -U0 master -- README.md | grep '^@@'` → `@@ -3 +3 @@`, `@@ -47 +47,67 @@`, `@@ -51 +117,19 @@`, `@@ -55 +139,47 @@`. The first is line 3; the remaining hunks are inside API, Running the demo, and Testing.
- No-touch: SHA-256 checks of the README sections `AI Collaboration Narrative`, `System design`, `Design evidence`, `Deliverables map`, and `Quality gates` match `master` byte-for-byte.
- README/API: five endpoints, the UUID dealership-scoped idempotency boundary, request and 201 wire examples, error body/code table, and `/docs` agree with the SPEC Wire formats, design §3, and ADR-008. `python3` reports `2027-03-26 09:00 Europe/London` as `GMT +0000`, so the example's `09:00:00Z` is correct.
- README/demo and testing: the script contains sections 1–8 and ends with `echo "$overlaps"` plus `[[ "$overlaps" == "0" ]]`; the README accurately states clean rerun and the eight behaviours. It has one TC-aligned row for every present `test_*.py`, plus the two specified pending rows, the standalone race command and L-001, and all six required limitations. `runbook/raw/legs/T12-demo-output.txt` records sections 1–5 passing, the deferred-T10b 404 at section 6, and a diagnostic continuation with the 2/6 race split and final `0`.
- Commits: `9e95aa0` and `8e1a964` use the `SPEC-001 T13:` form and both include `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. The latter's AC-15 follow-up remains traceable to design §5. `git show 9e95aa0 8e1a964 | rg 'ERR-[0-9]{3}|LSN-[A-Za-z0-9-]+'` has no matches.
