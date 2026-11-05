# SPEC-001 implementation status

Status: audited
Branch: feat/spec-001-booking-service
Base: f0f4117 (T0b, spec approved)

Each task appends one section: commits, test command and result line, audit file and verdict, deviations.

## T1
Commits: a919ea6 (deps, skeleton, test), ca49db0, 1d24569 and one later fix (architecture-scan gaps found by Codex cycles 1–3: nested main.py, package-root aliases, relative imports).
Tests: `uv run pytest tests/test_architecture.py -q` → 3 passed.
Audit: docs/ai/reviews/SPEC-001-T1-audit.md — pass (cycle 4; cycles 1–3 each found a distinct scan gap, all fixed in new commits).
Deviation: audit exceeded the 3-cycle bound by one, orchestrator exception (each cycle raised a new gap, none repeated).

## T2
Commits: 0292cdf (T2a schema migration + Core tables), fd19e99 (T2b test harness), 37c7f41 (downgrade drops btree_gist), 20778e0 (audit); merged add2f0b.
Tests: `uv run pytest tests/test_seed.py tests/test_architecture.py -q` → 4 passed (TC-34 constraint clauses).
Audit: docs/ai/reviews/SPEC-001-T2-audit.md — pass (cycle 2).
Notes: the GRANT is documentary under the superuser test role; testcontainers on colima needs `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock` (Makefile and README carry it, T13).

## T4
Commits: c8ed836 (domain model, time rules, canonical hash), 44c04fd (audit); merged eff7981.
Tests: `uv run pytest tests/test_time_rules.py tests/test_canonical.py -q` → 15 passed (TC-03..TC-07).
Audit: docs/ai/reviews/SPEC-001-T4-audit.md — pass (cycle 1).
Rules fixed where the SPEC was silent: a job ending exactly at closing takes pickup at the next opening; the pickup walk checks 14 local dates from the end's local date. `Contention.result` typed `Any` until T5 merged (consolidation commit).

## T5
Commits: bec479c, 42e347f (attempt policy), ffebff3 (audit); merged e783aed.
Tests: `uv run pytest tests/test_attempts.py -q` → 7 passed (TC-01, TC-02).
Audit: docs/ai/reviews/SPEC-001-T5-audit.md — pass (cycle 1; two deliberate mutations caught by the tests).
Definition fixed: `candidates_pruned` counts every candidate a loss removes, including the pair just tried. `Candidate`, `Confirmed`, `ResourceTaken` defined in attempts.py pending relocation to model.py (consolidation commit).

## T10a
Commits: 3052c50 (window arithmetic), a2887ef (tests cut to TC-08 clauses), 269d94a (audit); merged 8651cbf.
Tests: `uv run pytest tests/test_windows.py -q` → 4 passed (TC-08).
Audit: docs/ai/reviews/SPEC-001-T10a-audit.md — pass (cycle 3; cycles 1–2 were sandbox and amend-policy issues, no code findings).
Rules fixed: the "now" cutoff rounds up to the next whole minute and a start equal to now is allowed. Local `Hours`/`Dealership` stand-ins pending replacement by T4 imports (consolidation commit).

Wave A merged 2026-11-04 22:05: `uv run pytest -q` → 32 passed; pre-commit and `mypy src` green.

## T3
Commits: leg/t3 (seed migration 0002 + TC-34 seed clauses), 5941b6c (audit); merged as the commit above this line's merge.
Tests: `uv run pytest tests/test_seed.py tests/test_architecture.py -q` → 9 passed.
Audit: docs/ai/reviews/SPEC-001-T3-audit.md — pass (cycle 1).
Rules fixed: dealership 1 open Mon–Sat, dealership 2 Mon–Fri, Sunday absent; seed ids < 100 and the five seeded tables' id counters set to 99 (appointment counter untouched, it has no seed rows).

## T6
Commits: leg/t6 (T6a ports and outcomes; T6b BookAppointment use case with fakes), b6b4bf7 (audit); merged as the merge commit following this section's status commit.
Tests: `uv run pytest tests/test_book_appointment_usecase.py tests/test_architecture.py -q` → 17 passed (TC-09, TC-10, TC-11), no database. `uv run mypy src tests/fakes.py` green.
Audit: docs/ai/reviews/SPEC-001-T6-audit.md — pass (cycle 1).
Rules fixed: a replayed 201 carries the stored bay and technician in the Outcome (ADR-013: null only when not a 201); a claimed key row with no recorded outcome raises and becomes a 5xx (cannot occur for a committed row). Note for T7: the unit of work declares `appointments`, `idempotency`, `reads` with the port types, not the adapter classes.

## T7
Commits: 50ba998 (T7a reserve adapter), a974d42 (T7b read, idempotency adapters and unit of work), audit commit; merged after this section's status commit. Written inline by the orchestrator (leg cap), same contract and audit.
Tests: `uv run pytest tests/test_postgres_adapters.py -q` → 4 passed (TC-12 x2, TC-13, end-to-end BookAppointment against PostgreSQL).
Audit: docs/ai/reviews/SPEC-001-T7-audit.md — pass (cycle 1).
Notes: the read repository also carries `bays`, `busy_ranges`, `watermark` (the Protocol requires all methods for structural typing), so T10b adds no repository code.

## T9
Commits: d7c5827 (wide event middleware and health split), 83d5af3 (an exception after the response started now records 500 `error`, not final), 106d78b (audit); merged after this section's status commit.
Tests: `uv run pytest tests/test_events.py tests/test_health.py -q` → 9 passed (TC-32, TC-33).
Audit: docs/ai/reviews/SPEC-001-T9-audit.md — pass (cycle 3; cycle 1 found the started-response status gap; cycle 2 asked for a squash, declined under the commit protocol).
Rules fixed: `health.build_router(engine)` accepts any object with an async `connect()` so the interfaces layer imports no SQLAlchemy; the middleware emits only the 17 schema keys, so no handler can leak an email or VIN into the event; `SELECT 1` readiness, any exception → 503.

## T8
Commits: leg/t8 (T8a HTTP schemas, error mapping, dependencies; T8b appointments router and composition root), 1e2cca6 (T7 fix: `qualified_technicians` inner NOT EXISTS now correlated), b7af954 (audit); merged after this section's status commit.
Tests: `uv run pytest tests/test_booking_api.py tests/test_idempotency.py -q` → 36 passed (TC-15..19, 21..27, 37); TC-19's event assertion runs for real (T9 merged first, no xfail). Full suite 95 passed.
Audit: docs/ai/reviews/SPEC-001-T8-audit.md — pass (cycle 1).
Defect caught by TC-21: an uncorrelated NOT EXISTS in the T7 qualification query made every technician qualified whenever any technician held the skill; fixed in 1e2cca6 (orchestrator-approved fix inside the Contract).
Rules fixed: `route` and `idempotency_key` are written to the event before ADR-008 steps 2–3 so 400/404/422 events carry the key (ADR-013); `service_type_id` is written after schema validation; error handlers set `code` on every error response.

## T10b
Commits: leg/t10b (GetAvailability use case and route; a second commit typed the handler return after audit cycle 1), 4931990 (audit); merged after this section's status commit.
Tests: `uv run pytest tests/test_availability.py -q` → 10 passed (TC-28, TC-29 exact London windows, TC-30). Full suite 104 passed.
Audit: docs/ai/reviews/SPEC-001-T10b-audit.md — pass (cycle 2).
Rules fixed where the SPEC was silent: days are `[from, to)` and the horizon is checked on the exclusive `to`; the busy-range read spans first opening to last closing plus duration; no bay, no qualified technician or no open day → 200 with empty windows. TC-30 read as `[opens, closes - 1 min]` on every open day regardless of duration (consistent with AC-06).
Deviation: `AvailabilityOut`/`WindowOut` live in `availability.py` (T8a owns `schemas.py`); relocation to `schemas.py` is a follow-up commit before the final audit.

## T12
Commits: dc353b1 (demo script, compose api migrates on start, make demo), plus verification commits on leg/t12-t13-verify (race clients start behind a barrier; unbuffered api stdout; temp path), audit; merged 3df7f82.
TC-35: `make down && make demo` on the merged branch (T10b included) → exit 0; sections 1–8 as specified; race 2 x 201 + 6 x `capacity_exhausted`; last line `0`. Output: runbook `raw/legs/T12-demo-output-merged.txt` (private evidence copy; the README describes the run).
Audit: docs/ai/reviews/SPEC-001-T12-audit.md — pass (cycle 1).
Retired: the spike container `kl-spike-pg`.

## T13
Commits: 9e95aa0 (CI on testcontainers, README API/demo/testing sections), 8e1a964 (CI mypy step covers tests/fakes.py), audit; merged 3df7f82.
TC-36 / local CI equivalent (D-045): `uv run pre-commit run --all-files` green; `uv run mypy src tests/fakes.py` green; `uv run pytest -q` → 104 passed on the merged branch; `.github/workflows/ci.yml` runs exactly those, no database service, no DATABASE_URL.
TC-38: `grep -Ec '^## (API|Running the demo|Testing)$' README.md` → 3; line 3 reads `Status: implemented; see Testing for the evidence.`; `git diff -U0 master -- README.md | grep '^@@'` → hunks at line 3 and inside the three sections only.
Audit: docs/ai/reviews/SPEC-001-T13-audit.md — pass (cycle 2).
Open: README placeholder `OUTPUT-PENDING-T11` is filled at the T11 merge (D-048 pending).

## D-048 (ADR-004 amendment: per-dealership serialisation; D-049, D-050 follow-ups)
Commits on leg/d048: 440c37a (T7 advisory lock adapter), 3d3e403 (T6 serialise after the key claim), 687fb04 (T5 40P01 keeps the pair), 5433422 + 752bcb4 (ADR-004 amendment, SPEC rows), 7ed95e0 (T5 block wording, audit cycle 1), 9a6a682 (D-049: TC-31 synchronises the clients, not the attempts), 918ecb8 (D-050: retry loop as the fallback behind the lock, AC-16/TC-39, TC-31 attempts total), 977b5fd (audit); merged 67f1f6f. Doc coherence on the feature branch: 94daeed (design, ADR-008, README wording), ffc7d14 (design wording for D-050).
Gates on the merged branch: `uv run pytest -q` → 106 passed; `uv run mypy src tests/fakes.py` green; `uv run pre-commit run --all-files` green.
TC-01, TC-02 (40P01 keeps the pair, bound), TC-11 (`serialise` after the claim, before the gate and any reserve, never on a replay), adapter test (lock held until commit) pass. L-005 recorded in docs/ai/lessons.md.
Audit: docs/ai/reviews/SPEC-001-D048-audit.md — pass (cycle 4). Cycle 1: SPEC T5 wording. Cycle 2: TC-31's in-transaction barrier deadlocks against the lock → D-049. Cycle 3: TC-31 `attempts >= 8` unimplementable under serialisation → D-050.
Deviation (accepted): commit 7ed95e0's subject cites "D-048 audit cycle 1" and no design section or ADR; history kept as is because the committed cycle-2 audit cites that sha.
Open: T11 (TC-20, TC-31, TC-39) on this head; README placeholder `OUTPUT-PENDING-T11` and the test-table row for `tests/test_concurrency.py` filled at the T11 merge.

## T11
Commits on leg/t11-v2 (BASE a748549): 8371f71 (tests/test_concurrency.py: TC-20, TC-31, TC-39), 4723799 (audit); merged 5486672.
Done-when loop: 3 of 3 runs green; 10 further runs all green (split 4/4, deadlocks 0, max latency_ms 108–118).
V-002: 8 clients, 4 pairs, statuses={201: 4, 409: 4}, attempts=4, deadlocks=0, candidates_pruned=0, max latency_ms=126, wall=129 ms, overlaps=0
V-002: 8 clients, 4 pairs, statuses={201: 4, 409: 4}, attempts=4, deadlocks=0, candidates_pruned=0, max latency_ms=114, wall=119 ms, overlaps=0
Before D-048 (first attempt, runbook evidence): split held 9 of 20 runs, up to 13 deadlocks, peaks 1.2–1.4 s. After: every run, 0 deadlocks, 110–126 ms.
TC-39 (D-050): case (a) dealership 100, 2 bays x 1 technician, bypass row on bay 100 → 201 on bay 101; case (b) dealership 110, 1 x 1 → 409 capacity_exhausted, attempts 1, pruned 1. Bypass rows use skill-less technicians so only the bay is blocked.
Gates on the merged branch: `uv run pytest -q` → 109 passed; `uv run mypy src tests/fakes.py` green (also green with tests/test_concurrency.py); `uv run pre-commit run --all-files` green.
Audit: docs/ai/reviews/SPEC-001-T11-audit.md — pass (cycle 1).
Open: `barrier_gate` in tests/conftest.py is unused since D-049 (T2's file); remove or document at the final gate. README `OUTPUT-PENDING-T11`, test-table row and Known limitations filled in the next T13 commit.

## T13 (final: README fill, conftest, coherence)
Commits on leg/t13-final (BASE bba578f): 6a3a0e4 (README: V-002 line, test-table row for TC-20/TC-31/TC-39, Known limitations bullet for the dealership lock, stale race wording), f208fdf (T2: unused `barrier_gate` removed from tests/conftest.py), coherence commit (ADR-004 ordering, capacity and measured-figure notes; design.md rejected-alternatives qualifier; SPEC D-041 item 4 superseded note, booking-sequence gate comment, AC-10 traceability, T2 block note, D-049/D-050 rows dated and ordered).
Closes the Open lines of T13, D-048 and T11: `OUTPUT-PENDING-T11` filled; `barrier_gate` removed.
Coherence cross-check: docs/ai/reviews/SPEC-001-coherence-crosscheck.md — pass (cycle 2; cycle 1 F-1..F-5 fixed in ca609d9: ADR-004 pool limitation and pruning parenthesis, lock ordering and pool limit stated without an unproven guarantee, TC-39 row names the `engine.begin()` transaction). Evidence correction: the after-lock run count is 19 (3 + 10 + 6), not 20.

## Final gate
Scope: SPEC-001 whole, `git diff bdb70d0..377e994` (feature-branch base to the coherence cross-check head).
Gates on 377e994: `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest -q` → 109 passed; `uv run mypy src tests/fakes.py` → no issues in 34 source files; `uv run pre-commit run --all-files` → all hooks passed; `scripts/demo.sh` on a compose stack of this tree (unique project, db port unpublished, `API_URL` on a free port) → sections 1–8, race 2 x 201 + 6 x 409 `capacity_exhausted` with losers at `attempts` 0, last line `0`.
Audit: docs/ai/reviews/SPEC-001-code-audit.md — pass (cycle 1), one low finding F-001 recorded below.
Deviation (accepted, F-001): commit 9e3ae18 `SPEC-001 consolidate-a: Codex audit (pass)` uses neither the `SPEC-001 T<n>:` form nor a design or ADR citation; history kept as is.
Closing-leg commits on leg/t13-final (BASE bba578f): 6a3a0e4, f208fdf, d984a7c, ca609d9, 377e994, and this status commit.
Open for the author: test-seam comments at `src/scheduler/application/book_appointment.py:64,104` and `src/scheduler/main.py:49` still name the barrier race (the seam serves TC-39 since D-049, D-050); the race banner in `scripts/demo.sh` says "allow 2 concurrent winners". Both outside the closing leg's paths.

## T14 (final coverage against the brief, polish)
Commits on leg/t14-polish (BASE c05b99a): 914fc78 (seam comments name the TC-39 bypass writer, comments only), 0367886 (demo section 7 banner "allow 2 winners"; README Quick start prerequisites; booking curl prints its status and states the 409 `vehicle_already_booked` of a second send or a prior `make demo`), 8a297e0 (SPEC TC-39 row names bay 100 at dealership 100 and bay 110 at dealership 110; AC-16 after AC-15; Scope Amendments row), 73e5722 (docs/ai/README artefact table links the SPEC, status file, SPEC review and audits), and this status commit with the audit.
Gates: `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest -q` → 109 passed; `uv run pytest tests/test_concurrency.py -q -s` → 3 passed, `V-002: 8 clients, 4 pairs, statuses={201: 4, 409: 4}, attempts=4, deadlocks=0, candidates_pruned=0, max latency_ms=107, wall=111 ms, overlaps=0`; `uv run mypy src tests/fakes.py` → no issues in 34 source files; `make lint` → all hooks passed.
Demo: `make down && make demo` run twice (before and after the banner fix): sections 1–8, race 2 x 201 + 6 x 409 `capacity_exhausted`, losers at `attempts` 0, last line `0`.
README run as a reviewer: `make install`, `make up`, `make migrate`, `make run`, the booking curl (201 on a fresh database; 409 `vehicle_already_booked` when sent again or after `make demo`, now stated), `GET` by id 200, availability 200, `/health/live` 200, `/health/ready` 200, `/docs` 200, `/openapi.json` 5 paths, error bodies 400, 404, 422 with `errors`.
Coverage against the brief: 41 rows; 34 MET, 3 PARTIAL, 1 MISSING, 3 out of scope by design. The PARTIAL and MISSING rows reduce to two author-owned items (D-038): the README AI Collaboration Narrative and the video link.
Audit: docs/ai/reviews/SPEC-001-T14-audit.md — pass (cycle 1); every MET row cross-checked, no missed requirement.
Open for the author: README AI Collaboration Narrative and the Deliverables map rows for it and the video; design.md section 2 layer line (D-038); push and GitHub CI (D-045).

## T15

ADR coherence walk, docs only, from e659eaf. Commits: 033f657 (C1, Codex F-1..F-12 on ADR-004), 077a6d1 (C2), e2d099b (C3), c13951f (C4, with the SPEC T15 amendment row), 4ecb8f0 (cycle 1), b69d8ad (cycle 2), 6b72d6d (fix after cycle 3).
Ledger: walk OK 158, STALE 12, UNPROVEN 17, CONTRADICTS 7, DANGLING 1 (every ADR, design.md, README.md, adr/README); cross-check adds STALE 4, UNPROVEN 3, CONTRADICTS 1, DANGLING 2. Fixes: 51.
Cross-check: docs/ai/reviews/SPEC-001-adr-coherence-crosscheck.md, Codex, 3 cycles, final verdict revise (F-14, fixed in 6b72d6d, not re-verified): BLOCKED on the cycle cap.
Needs the author: 3 (code comment `ports.py:91` and test docstring `test_architecture.py:1` out of the docs-only scope; the design §2 layer line added in cycle 1 was an author-owned open item, keep or revert).
Gates: `uv run pytest -q` 109 passed; `uv run mypy src tests/fakes.py` clean; `uv run pre-commit run --all-files` clean.
