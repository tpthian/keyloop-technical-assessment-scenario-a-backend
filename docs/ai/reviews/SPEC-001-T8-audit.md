# SPEC-001 T8 audit

Task: T8 — HTTP layer for appointments and the composition root
Base: `4b11c9398695209f8d4075991f39bb62634412be` (audit range begins after merged T9 commit `d3e32d4`)
Head sha: `fdd03589be4eaeffcefb6dabf224eacc5c2e1c1f`
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## ADR-008 order

| ADR-008 / SPEC handler requirement | Implementation evidence | Result |
|---|---|---|
| Dependency resolves the UUID key before the route body runs; a missing or invalid key is 400 and stored nowhere. | `dependencies.py:23-36` parses the header and raises `BadRequest`; the route injects it at `appointments.py:58`, before `_book`. The POST has no typed body parameter. | Pass |
| Step 1 parses JSON before reading the dealership; malformed JSON is 400 and stored nowhere. | `appointments.py:79` awaits `request.json()` before line 80; `errors.py:77-80` maps `JSONDecodeError` to 400 `validation`. | Pass |
| Step 2 loads the dealership before schema validation; an absent dealership is 404 and stored nowhere. | `appointments.py:80-82` loads and rejects before `BookingRequest.model_validate` at line 84. | Pass |
| Step 3 explicitly validates the raw body, after the dealership load; schema failures are 422 with reduced error items and stored nowhere. | `appointments.py:84-86`; `errors.py:83-86`; `schemas.py:144-146`. | Pass |
| Step 4 maps the validated body once, then canonicalises/hashes with the loaded dealership zone before `BEGIN`. | `appointments.py:88-89` calls only `to_command` then `BookAppointment.execute(cmd, dealership)`; the reviewed use case performs canonicalisation before its UoW. | Pass |
| Steps 5–7 claim inside one transaction, perform business validation, and attempt bookings in the use case. | `appointments.py:89` delegates after all pre-claim work; this is the specified application boundary. | Pass |
| No outcome is stored for steps 1–3. | All three exceptions leave `_book` before `BookAppointment.execute`; the supplied outside-sandbox TC-15–17 and TC-37 run passed. | Pass |
| SPEC illustrative handler imports `json`; implementation does not. | `json.JSONDecodeError` is handled centrally in `errors.py`, so `appointments.py` has no direct `json` reference. | Intentional, equivalent. |
| SPEC illustrative handler imports `BookAppointment`; implementation does not. | The router operates through the typed `UseCases` container instead of naming the concrete class. | Intentional, equivalent. |
| Implementation additionally imports `AppointmentOut` and `ErrorOut`, sets `BOOKING_BODY.required`, and adds `BOOKING_RESPONSES` plus GET response documentation (`appointments.py:20-31`, `47-53`, `62-66`). | These are OpenAPI-only declarations; runtime parsing remains raw-request parsing and response bodies are unchanged. | Additive, conforms to the wire contract. |
| SPEC's repeated outcome-field literal becomes `OUTCOME_FIELDS` (`appointments.py:32-41`, `90`). | The tuple contains exactly the eight fields in the illustrative handler and copies each exactly once. | Intentional refactor, equivalent. |
| SPEC's `key: UUID = Depends(...)` becomes `key: Annotated[UUID, Depends(...)]` (`appointments.py:58`). | Both forms are FastAPI dependencies; neither is a body parameter. | Intentional, equivalent. |
| The SPEC block sets `ev["route"]` and `ev["idempotency_key"]` after `to_command`; implementation sets them at `appointments.py:76-78`, before JSON parsing. | A valid key must be present on booking events even for malformed JSON, 404, or schema-422 responses; ADR-013 says it is null only when missing or invalid. | Necessary divergence; ADR-013-conformant. |
| The SPEC block has no explicit `service_type_id` event assignment; implementation adds it at `appointments.py:87`. | It is set only after successful schema validation, as ADR-013 requires. | Necessary additive behavior; ADR-013-conformant. |

## Findings

- Severity: escalate
  File: [src/scheduler/infrastructure/postgres/repositories.py](/Users/jp/Documents/Personal/JobSearching/NextRound/KeyLoop/keyloop-technical-assessment-scenario-a-backend/.claude/worktrees/agent-aca0595f1d1683153/src/scheduler/infrastructure/postgres/repositories.py:165)
  What: Commit `1e2cca6` modifies a T7-owned file outside T8's approved path list. The change is minimal and correct: explicit correlation removes `technician` from the inner `EXISTS` `FROM`, retaining `technician_skill.technician_id = technician.id` as the outer correlation; it fixes the stated qualification false-positive.
  Required fix: None from T8. Orchestrator to decide whether to accept this scoped T7 correction in the T8 range or move/audit it under T7.

## Evidence

- Reviewed `git diff d3e32d4..HEAD` against SPEC Contract Architecture/design-to-code map, Known Facts 3 and 9, Files Involved/No-Touch, Wire formats, AC-02/03/04/05/08, TC-15–19/21–27/37, the HTTP-layer execution bullets and handler block, T8, design §3, ADR-008, ADR-013, and the merged T9 `events.py`/`health.py` mounting. `git diff --check d3e32d4..HEAD` produced no output.
- Path audit: the two T8 commits change only their expected HTTP/main/test paths. `1e2cca6` is the sole additional commit and changes only the T7 repository file recorded above.
- T7 SQL compile probe (`UV_CACHE_DIR=/private/tmp/spec001-t8-uv-cache uv run python ...`) produced `FROM technician_skill` in the inner `EXISTS`, retained `technician_skill.technician_id = technician.id`, and printed `PASS: inner EXISTS correlates technician; its FROM contains technician_skill only`.
- `uv run pytest tests/test_architecture.py -q` — `3 passed in 0.08s`.
- `uv run mypy src tests/fakes.py` — `Success: no issues found in 32 source files`.
- `uv run pre-commit run --all-files` — every hook passed: trailing whitespace, EOF, YAML, large files, merge conflicts, ruff check/format, secrets, and mypy.
- Database-backed T8 tests cannot run in this sandbox because Docker is unavailable. Supplied outside-sandbox execution reports all listed `test_booking_api.py` and `test_idempotency.py` cases plus architecture checks passed; full suite: `95 passed in 5.28s`. TC-19's replay-event assertion is active (not xfailed), and TC-24 directly inserts and asserts the named tenancy constraints.
- `tests/test_architecture.py` enforces that interfaces do not import infrastructure and only `main.py` imports both outer layers; its three tests passed. `main.py:34-65` constructs one use-case container with `SystemClock` default, `PostgresSchedulingReadRepository(db.connect)`, a `PostgresUnitOfWork` factory, mounts appointment and T9 health routers plus `WideEventMiddleware`, registers handlers, stores only `engine`, obtains a missing engine from settings, removes the scaffold `/health`, and disposes only an owned engine.
- `errors.py`'s status table matches the wire table; its handlers emit `{code, message}` and add `errors` only for Pydantic/FastAPI validation items reduced to `loc`/`msg`/`type`. The additional `StarletteHTTPException` handler is conformant: it extends the specified every-non-2xx error-body rule to framework 404/other 4xx and writes `ev["code"]` through the shared helper.
- `schemas.py` forbids extras at request and nested levels, enforces naive whole-minute input and customer/vehicle identifiers, normalises VIN before the vehicle identifier check, and has the requested one command mapper and response models. `dependencies.py` has the UUID dependency and frozen three-use-case container; availability is correctly deferred because `GetAvailability` is not present.
- Commit audit: `44c8c6b` subject is exactly `SPEC-001 T8a: HTTP schemas, error mapping, dependencies (design §3)` and `fdd0358` exactly `SPEC-001 T8b: appointments router and composition root (design §2, ADR-008)`; both include `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
