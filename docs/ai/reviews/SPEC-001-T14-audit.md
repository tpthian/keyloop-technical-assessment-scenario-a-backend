# SPEC-001 T14 audit

Task: T14
Base-SHA: `c05b99a1d94836623224a0a1b01a504295f5349b`
Head-SHA: `73e572277809b98ec7d26745b94a72e631fb1c97`
Commits:
- `914fc781d5d2c7683b8f253e9ed36d31ad4dac3d SPEC-001 T14: retire stale barrier-race seam comments (design §3, D-049, D-050)`
- `03678862706be42aa27b79bc53e859960630d093 SPEC-001 T14: demo banner and README curl fixes (design §5)`
- `8a297e0c8efbec1e2764f364120ce4e9bcc5354f SPEC-001 T14: SPEC TC-39 row bay id and AC order (D-050)`
- `73e572277809b98ec7d26745b94a72e631fb1c97 SPEC-001 T14: docs/ai artefact table links the implementation-phase files (design §6)`

Allowed-Paths: `src/scheduler/application/book_appointment.py`, `src/scheduler/main.py` (comments only); `scripts/demo.sh` (banner only); `README.md`; `docs/ai/specs/SPEC-001-booking-service.md`; `docs/ai/README.md`; and this report path only.
Changed-Paths:
- `M README.md`
- `M docs/ai/README.md`
- `M docs/ai/specs/SPEC-001-booking-service.md`
- `M scripts/demo.sh`
- `M src/scheduler/application/book_appointment.py`
- `M src/scheduler/main.py`

Checks:
- `git rev-parse --verify c05b99a1d94836623224a0a1b01a504295f5349b^{commit}` — exit `0` — base commit exists.
- `git rev-parse --verify 73e572277809b98ec7d26745b94a72e631fb1c97^{commit}` — exit `0` — head commit exists.
- `git merge-base --is-ancestor c05b99a1d94836623224a0a1b01a504295f5349b 73e572277809b98ec7d26745b94a72e631fb1c97` — exit `0` — base is an ancestor of head.
- `git status --short` — exit `0` — clean before this report was created; no source, test, or configuration changes outside the report path afterwards.
- `git diff --name-status c05b99a1d94836623224a0a1b01a504295f5349b..73e572277809b98ec7d26745b94a72e631fb1c97` — exit `0` — exactly the six Changed-Paths above.
- `git diff --check c05b99a1d94836623224a0a1b01a504295f5349b..73e572277809b98ec7d26745b94a72e631fb1c97` — exit `0` — no whitespace errors.
- `uv run pytest tests/test_architecture.py -q` — exit `0` — `3 passed in 0.15s`.
- `uv run pre-commit run --all-files` — exit `0` — all hooks passed.
- `uv run mypy src` — exit `0` — `Success: no issues found in 33 source files`.
- `docker info >/dev/null 2>&1` — exit `1` — Docker unavailable in this sandbox.
- `uv run pytest -q` — exit `N/A` — not run because Docker is unavailable; relied on leg evidence: `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest -q` — exit `0` — `109 passed`.
- `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest tests/test_concurrency.py -q -s` — exit `0` (leg evidence) — `3 passed`; V-002 reported 4 × 201, 4 × 409, 0 deadlocks, 0 overlaps.

Contract-Checks:
- T14 commit protocol — pass — all four subjects use `SPEC-001 T14:`, each cites a design section or decision, and each commit has a `Co-Authored-By:` trailer.
- Allowed scope and unchanged tests — pass — range contains only the six allowed task paths; `git diff ... -- tests` is empty.
- B1 comment-only source changes — pass — `book_appointment.py:64,105` and `main.py:49` identify the TC-39 writer-bypass seam; comment-stripped, blank-normalised base/head comparisons exit 0 for both files.
- B2 demo banner — pass — `scripts/demo.sh:165-166` says `allow 2 winners`; leg rerun records the same banner and the expected 2 × 201 / 6 × 409 split.
- B2 README curl and run guidance — pass — `README.md:7,82-90` states prerequisites, prints HTTP status, and accurately describes 201 on a fresh database and 409 after a new-key repeat or `make demo`; captured run C confirms both cases.
- B3 TC-39 — pass — SPEC `docs/ai/specs/SPEC-001-booking-service.md:253` matches `tests/test_concurrency.py:191-220`: case (a) dealership 100/bay 100 then 201 on bay 101; case (b) dealership 110/bay 110 then 409, one attempt, one pruned candidate.
- B3 AC order and amendment — pass — AC-15 precedes AC-16 at `docs/ai/specs/SPEC-001-booking-service.md:213-214`, numbering is unchanged, and the T14 Scope Amendments row is at `:859`.
- B4 implementation-artifact links — pass — `docs/ai/README.md:73-75` links to existing SPEC, status, SPEC-review, and whole-SPEC-audit files; all changed Markdown link targets resolve.
- False-evidence and writing-rule review — pass — new T14 text contains no stale `concurrent winners`, unsupported result, first-person claim, or non-L-id lesson citation; PDF/table claims agree with the rendered four-page source and supplied run evidence.

Coverage-Checks:
- `1` — confirmed — `docs/design.md:20` identifies the Scenario A scheduler; the source tree, leg full-suite evidence, and demo support the table claim.
- `2` — confirmed — `src/scheduler/interfaces/http/appointments.py:45-60`, `schemas.py:71`, and `tests/test_booking_api.py:249` support the requested booking inputs and route.
- `3` — confirmed — `repositories.py:148-165,232-273`, `time_rules.py:61-66`, `0001_schema.py:107-114`, and `unit_of_work.py:62-71` implement qualified, full-duration atomic booking.
- `3a` — confirmed — `src/scheduler/interfaces/http/availability.py:24-29` exposes availability; TC-28..30 and captured demo/curl section 6 support the advisory claim.
- `4` — confirmed — `migrations/versions/0001_schema.py:82-115` persists appointment, customer/vehicle snapshot, bay, technician, tenancy, and non-overlap fields.
- `5` — confirmed — `docs/ai/README.md:1-78`, `docs/ai/specs/`, and `docs/ai/reviews/` exist and document the stated AI process and audit artefacts.
- `6` — confirmed — correctly PARTIAL: process evidence exists, while `README.md:192-194` remains the identified narrative stub; Needs JP records the author-owned gap.
- `7` — confirmed — `docs/design.md:34-42` documents the assumptions and their decisions.
- `8` — confirmed — `docs/design.md:18-32,55-93,165-183` contains the architecture, ERD, and scale diagrams.
- `9` — confirmed — `docs/design.md:44-53` gives each component's role.
- `10` — confirmed — `docs/design.md:100-150` contains the data-flow sequence and API outcomes.
- `11` — confirmed — `docs/design.md:152-163` lists technologies with justifications.
- `12` — confirmed — `docs/design.md:189-210` states the observability strategy.
- `13` — confirmed — `docs/design.md:212-224` is the dedicated GenAI design-phase section.
- `14` — confirmed — backend implementation is selected and bounded by ADR-001 and ADR-012; no custom frontend is claimed.
- `15` — confirmed — rows 2-4 evidence the selected backend's Scenario A core requirements.
- `16` — confirmed — `src/scheduler/main.py:64-70` creates the FastAPI app; captured `/openapi.json` lists five paths.
- `17` — confirmed — `docker-compose.yml:1-30` provides PostgreSQL and the API migrates with Alembic; `migrations/versions/0001_schema.py` and `0002_seed.py` exist.
- `18` — confirmed — `scripts/demo.sh`, `README.md:80-90`, and Swagger/OpenAPI provide the permitted client stubs; captures confirm their stated outcomes.
- `19` — confirmed — `docs/design.md:185-187` addresses stateless instances, availability replicas, tenancy shardability, and stated future work.
- `20` — confirmed — `unit_of_work.py:46-47` sets the two timeouts; ADR-004 and supplied V-002 evidence support the bounded performance claim.
- `21` — confirmed — `README.md:59-65` documents idempotency and retries; `health.py:42-49` implements readiness failure.
- `22` — confirmed — `tests/test_architecture.py` passed; `.github/workflows/ci.yml:17-20` runs the declared gates and `pre-commit`/mypy passed locally.
- `23` — confirmed — `src/scheduler/interfaces/http/events.py:80-83` emits the ordered wide event; TC-32 and demo event output support the table claim.
- `24` — confirmed — `docs/design.md` and `docs/adr/` provide the architectural plan and its decision records.
- `25` — confirmed — correctly treats the local working repository and 109-pass/demo evidence as working code; the unpushed submission URL is separately listed under Needs JP.
- `26` — confirmed — `README.md:5-20,119-147` supplies build/run/test instructions; T14 curl and demo captures validate the corrected reviewer paths.
- `27` — confirmed — correctly MISSING: the required README narrative is absent beyond `README.md:192-194`; the D-038 author-owned record is present under Needs JP.
- `28` — confirmed — the `tests/` suite and README test table exist; leg evidence reports 109 passing tests and three passing concurrency tests.
- `29` — confirmed — correctly OOS for this repository audit: the PDF video deliverable is separately author-owned and listed under Needs JP.
- `30` — confirmed — `docs/design.md` TL;DR, sections 1-6, and ADRs substantiate the system-design criterion.
- `31` — confirmed — gate results, V-002/TC-39, and 0-overlap evidence substantiate technical execution.
- `32` — confirmed — correctly PARTIAL for the same identified README narrative gap as row 27; implementation evidence is otherwise present.
- `33` — confirmed — correctly PARTIAL because the video and README narrative are not yet complete; both are listed under Needs JP.
- `34` — confirmed — `0001_schema.py:107-114`, ADR-004, TC-31, TC-39, and demo overlap output establish non-overlap coverage.
- `35` — confirmed — `README.md:59-65`, ADR-008, and TC-15..20/37 substantiate idempotent booking.
- `36` — confirmed — `README.md:105-117` and `interfaces/http/errors.py` define the uniform error shape and mapping.
- `37` — confirmed — `src/scheduler/domain/time_rules.py:40-78`, ADR-009, and TC-03..06/21 cover time zones and opening hours.
- `38` — confirmed — correctly OOS: `docs/design.md:40` explicitly places authentication at the upstream gateway.
- `39` — confirmed — correctly OOS: `docs/design.md:187`, the SPEC Out of Scope contract, and ADR-012 record the deferred features.
- `40` — confirmed — `src/scheduler/interfaces/http/health.py:38-49`, TC-33, and curl run A cover both health endpoints.
- Missed requirements: None.

Findings:
- None.

Verdict: pass
