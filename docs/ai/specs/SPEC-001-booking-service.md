# SPEC: SPEC-001 — Booking service: clean-architecture implementation of the design

Status: approved
Gate: implementation
Set-By: jp
Set-At: 2026-11-04T16:50:00+07:00
Version: 3 — contract revision (2026-11-04). Reason: ADR-008 request order restored at the HTTP boundary (dealership load before schema validation); v2 rewrote the SPEC to the implementation shape of D-039/D-041 (four layers, Protocol ports, written for engineers); v1 was a layered script.
Operation-Type: new_feature (secondary: data_model_change, devops_change)
Delivery-Risk: high
Branch: feat/spec-001-booking-service
Production Branch: master
Sub-repo: keyloop-technical-assessment-scenario-a-backend (single repository; every path below is relative to its root)

Contract sources: `docs/design.md`, `docs/adr/ADR-001.md` to `ADR-014.md` (ADR-014 from D-058). This SPEC is the ticket breakdown: one task per commit series, every commit traceable to a task and to a design section or ADR. Reader: an engineer reviewing or implementing. Code appears only where correctness is subtle (DDL, the booking transaction, the reserve adapter, the concurrency test); everything else is interface, rule and sequence.

## § Contract

### Outcome

The service described in `docs/design.md` runs from a fresh clone with `make install && make up && make migrate && make run`, books appointments under the guarantee of ADR-004 (three exclusion constraints, one savepoint per attempt, bound of five, three 409 codes), honours the idempotency boundary of ADR-008, the time rules of ADR-009 and the advisory availability of ADR-010, emits one wide JSON event per request (ADR-013), and proves the guarantee with a barrier-based concurrency test (V-002) and `scripts/demo.sh`, whose last line prints the overlap count `0`. The code is arranged in four layers whose dependency direction is enforced by a test, so the design's components map one to one onto modules.

### In Scope / Out of Scope

In scope:
- Schema migration (every table of design.md section 2, `btree_gist`, three exclusion constraints, composite tenancy foreign keys, CHECKs, `GRANT SET ON PARAMETER deadlock_timeout`) and a seed migration.
- `POST /dealerships/{id}/appointments`, `GET /dealerships/{id}/appointments/{appointment_id}`, `GET /dealerships/{id}/availability`, `GET /health/live`, `GET /health/ready`.
- Booking use case: canonical hash, key claim, business validation, candidates in random order, one savepoint per attempt, pruning by constraint name, 409 classification, recorded outcome, `SET LOCAL deadlock_timeout = '100ms'` and `statement_timeout = '2s'`.
- Ports (`typing.Protocol`) owned by the application layer; PostgreSQL adapters in the infrastructure layer; in-memory fakes for use-case unit tests.
- Time rules: local wall time in, gap rejected, first occurrence for a repeated time, start in hours, elapsed duration in UTC, `pickup_from` derived, past and horizon checks.
- Availability: start windows per pair and local day, duration subtracted on UTC instants, 14-day window inside the 90-day horizon, `as_of` watermark.
- Wide event middleware, schema v1, 17 fields, identifiers only.
- Tests by layer: domain (pure), application (fakes), infrastructure (testcontainers), interfaces (full stack), the V-002 concurrency test, the parallel same-key test, and the layer-dependency test.
- `scripts/demo.sh`, `make demo`, compose `api` that migrates on start, CI on testcontainers.
- README sections "API", "Running the demo", "Testing"; dependency changes in `pyproject.toml`.

Out of scope, with reasons:
- README "AI Collaboration Narrative", design.md section 6 and docs/ai code-phase rows: written after the code audit (D-038), not by the implementation.
- Cancellation, rescheduling, admin APIs, notifications, `AppointmentConfirmed` outbox, key cleanup job, `/metrics`, background audit, UI: future work or cut (D-005, D-021, D-037).
- Read-replica routing: documented only (ADR-004); `as_of` is `coalesce(pg_last_xact_replay_timestamp(), now())`, which is `now()` on a primary.
- Resource retirement, per-dealership service offering, closures table: stated limitations.
- Request-level deadline and pool sizing rule: limitation in ADR-004; the pool is sized so the concurrency test runs (10 + 10 overflow).

### Architecture

Four layers under `src/scheduler/`, dependency direction enforced by `tests/test_architecture.py` (D-041):

| Layer | Package | Holds | May import |
|---|---|---|---|
| Domain | `scheduler.domain` | Frozen dataclasses, time rules, window arithmetic, attempt policy, canonical hash, domain errors | Standard library only |
| Application | `scheduler.application` | Ports as `typing.Protocol`; use cases `BookAppointment`, `GetAppointment`, `GetAvailability`; `Outcome` | `scheduler.domain` |
| Infrastructure | `scheduler.infrastructure` | PostgreSQL adapters for the ports, Core table definitions, engine factory, unit of work, system clock | `scheduler.application`, `scheduler.domain`, SQLAlchemy, psycopg |
| Interfaces | `scheduler.interfaces.http` | FastAPI routers, pydantic request and response models, error mapping, wide-event middleware | `scheduler.application`, `scheduler.domain`, FastAPI, pydantic |
| Composition root | `scheduler.main` | `create_app(...)`: builds adapters, injects them into use cases, mounts routers | Everything |

Design-to-code map (the code audit checks every row):

| design.md component (section 2) | Module | Design reference |
|---|---|---|
| API layer: parse JSON, UUID key, load dealership, schema validation before BEGIN; map outcomes to HTTP | `interfaces/http/appointments.py`, `interfaces/http/schemas.py`, `interfaces/http/errors.py`; the router parses the raw body, loads the dealership through the `SchedulingReadRepository` port (404), then validates the schema (422), then calls the use case with the loaded dealership; ADR-008 steps 1–3 happen in `appointments.py` before any transaction | §2, §3, ADR-008 steps 1–3 |
| Booking service: only writer and transaction owner; converts start, computes `end_at`, builds candidates, retries up to 5 | `application/book_appointment.py` (sequence), `domain/time_rules.py`, `domain/attempts.py` | §3, ADR-004, ADR-008, ADR-009 |
| Candidate query: free bays × free qualified technicians, random order | `AppointmentRepository.free_candidates` (adapter: `infrastructure/postgres/repositories.py`), shuffle in `domain/attempts.py` | §2, ADR-004 |
| Idempotency store: claim in the booking transaction, replay or reject | `IdempotencyRepository` (adapter in `repositories.py`), `domain/canonical.py` | ADR-008 |
| Persistence adapter: `reserve(candidate) -> Confirmed | ResourceTaken`; 23P01 and 40P01 around the savepoint INSERT only | `AppointmentRepository.reserve`, adapter `PostgresAppointmentRepository.reserve` | §2, ADR-004 |
| PostgreSQL holds the invariant | `migrations/versions/0001_schema.py` (DDL), `infrastructure/postgres/schema.py` (Core tables for queries) | §2 ERD, ADR-004 |
| Availability, advisory | `application/get_availability.py`, `domain/windows.py` | ADR-010 |
| Observability: one wide event per request | `interfaces/http/events.py` | §5, ADR-013 |
| Health | `interfaces/http/health.py` | §3 |

Secondary impacts: `pyproject.toml` gains `greenlet` (explicit) and `sqlalchemy[asyncio]`, drops `structlog` and `prometheus-client`; `docker-compose.yml` `api` runs migrations before uvicorn; CI drops the postgres service. The system design is unchanged; after the audit, design.md section 2 gains one line naming the layers (D-038).

### Repository Evidence

| Claim | Evidence |
|---|---|
| Scaffold has one `/health` route and no business code | `src/scheduler/main.py:1-10` |
| Settings read `DATABASE_URL` from `.env` | `src/scheduler/settings.py:4-9` |
| Alembic env takes the URL from settings; `target_metadata = None`; no migrations | `migrations/env.py:12-15`; `migrations/versions/` empty |
| Makefile targets install, up, down, run, test, lint, migrate, spike | `Makefile:1-33` |
| Compose `api` has no migration step | `docker-compose.yml:16-24` |
| CI runs a postgres service plus `pre-commit` and `pytest` | `.github/workflows/ci.yml:10-33` |
| Dependencies lack greenlet: importing `sqlalchemy.ext.asyncio` raises `ImportError: ... requires that the Python 'greenlet' library is installed` | Run 2026-11-04, `uv run python -c "from sqlalchemy.ext.asyncio import create_async_engine"` |
| With greenlet: SQLAlchemy 2.1.6, FastAPI 0.162.0, psycopg 3.3.7, pydantic 2.14.2; `AsyncConnection.begin_nested` exists; `psycopg.errors.ExclusionViolation.sqlstate == "23P01"`; `asyncio.Barrier` exists | Same day, `uv run --with greenlet python -c ...` |
| Spike proves savepoint recovery from 23P01 and 40P01 in one transaction | `docs/evidence/spike/race_savepoint.py:70-100`, `docs/evidence/spike/race-savepoint-output-n8.txt` |
| Exclusion constraint DDL of the spike | `docs/evidence/spike/schema.sql:5-20` |
| Pre-commit runs ruff, mypy on `src`, gitleaks; mypy strict; ruff E, F, I, B, UP, N; line length 100 | `.pre-commit-config.yaml:1-30`, `pyproject.toml:38-52` |

### Known Facts and Decisions

Facts:
- Compose and CI database roles are superusers (official image, `POSTGRES_USER`), so `SET LOCAL deadlock_timeout` works with or without the GRANT; the GRANT documents the production requirement.
- `race_savepoint.py` exits 2 when no 40P01 appears; the implementation test never requires 40P01 (`docs/ai/lessons.md` L-001).
- The ADR-010 worked example is dated 2027-03-26, beyond 90 days from today; the clock is a port, so tests fix "now" at the example's issue time, 2027-03-25T16:00:00Z.

Decided at the human gate (D-041, 2026-11-04):
1. Wire formats as below.
2. `start_at` is whole minutes (seconds and microseconds 0), else schema 422. Availability windows carry inclusive `earliest_start` and `latest_start`; a window bounded by closing time ends at `closes_at - 1 min`.
3. `Clock` and `AttemptGate` are ports injected by the composition root. Nothing lives on `app.state` except the engine for readiness.
4. Seed: dealership 1 in `Europe/London` with 2 bays × 2 technicians; race of 8 clients, 4 winners (superseded by D-044: the demo race against the seed expects 2 winners; the test race uses its own fixture of 4 bays × 4 technicians).
5. Dependencies: add `greenlet`, `sqlalchemy[asyncio]`; drop `structlog`, `prometheus-client`; tests on testcontainers only; CI service removed.
6. Branch `feat/spec-001-booking-service`; merged with history kept (D-040).
7. Hash covers `service_type_id`, `start_at` as a UTC instant, `customer`, `vehicle` after validation and VIN normalisation; nulls omitted; keys sorted.

Fixed by this revision (no design change):
8. The idempotency row stores `request_hash`, `response_code`, `response_body`; HTTP status is derived from `response_code` by one table in `interfaces/http/errors.py`. The ERD lists exactly those columns; the v1 draft's `response_status` column is dropped so the application layer never holds an HTTP status.
9. ADR-008 fixes the order parse → load dealership (404) → schema validation (422) → BEGIN. FastAPI validates a typed body parameter before the handler runs, so the booking route takes the raw request instead: the handler parses JSON, loads the dealership through the `SchedulingReadRepository` port (interfaces → application is an allowed edge), validates `BookingRequest` explicitly, and passes the loaded `Dealership` into `BookAppointment.execute`. The use case therefore never looks a dealership up and never raises `NotFound`; "before BEGIN" (design §2) stays inside the layer rule and the ADR-008 precedence is testable (TC-37).

### Files Involved

| File | Change | Evidence Ref |
|---|---|---|
| `pyproject.toml` | Modify dependencies | greenlet ImportError row |
| `uv.lock` | Regenerate with `uv sync` | follows pyproject |
| `migrations/env.py` | Set `target_metadata` | `migrations/env.py:15` |
| `migrations/versions/0001_schema.py`, `0002_seed.py` | Create | `migrations/versions/` empty |
| `src/scheduler/domain/__init__.py`, `model.py`, `errors.py`, `time_rules.py`, `canonical.py`, `attempts.py`, `windows.py` | Create | design §2, §3; ADR-004, 008, 009, 010 |
| `src/scheduler/application/__init__.py`, `ports.py`, `outcomes.py`, `presenters.py`, `book_appointment.py`, `get_appointment.py`, `get_availability.py` | Create | design §2 component table; `presenters.py` is the one place the appointment body is shaped (ADR-008 replay body equals a live body) |
| `src/scheduler/infrastructure/__init__.py`, `clock.py`, `postgres/__init__.py`, `postgres/engine.py`, `postgres/schema.py`, `postgres/unit_of_work.py`, `postgres/repositories.py` | Create | ADR-002, ADR-004 |
| `src/scheduler/interfaces/__init__.py`, `http/__init__.py`, `http/schemas.py`, `http/errors.py`, `http/dependencies.py`, `http/appointments.py`, `http/availability.py`, `http/health.py`, `http/events.py` | Create | design §3 API table, ADR-013 |
| `src/scheduler/main.py` | Rewrite as composition root | `src/scheduler/main.py:1-10` |
| `tests/conftest.py`, `tests/fakes.py` | Create | ADR-002 testcontainers; D-041 fakes |
| `tests/test_architecture.py`, `test_time_rules.py`, `test_canonical.py`, `test_attempts.py`, `test_windows.py`, `test_book_appointment_usecase.py`, `test_postgres_adapters.py`, `test_seed.py`, `test_booking_api.py`, `test_idempotency.py`, `test_availability.py`, `test_events.py`, `test_concurrency.py` | Create | AC/TC table |
| `tests/test_health.py` | Rewrite | `tests/test_health.py:1-10` |
| `docs/ai/specs/SPEC-001-status.md` | Create (T1), append per task | docs/ai README pipeline: implementation status file |
| `scripts/demo.sh` | Create (replaces `scripts/.gitkeep`) | ADR-012, D-035 |
| `docker-compose.yml` | Modify `api` command | `docker-compose.yml:14-22` |
| `Makefile` | Add `demo` target | `Makefile:1` |
| `.github/workflows/ci.yml` | Remove postgres service and `DATABASE_URL` | `ci.yml:10-27` |
| `README.md` | Fill "API", "Running the demo", "Testing"; status line | sections marked "Written in the implementation phase" |

### No-Touch

- `docs/design.md`, `docs/adr/*`, `docs/ai/README.md`, `docs/ai/verification-ledger.md`, `docs/ai/defects-caught.md`, `docs/ai/reviews/*`: edited after the audit (D-038). Needed doc changes are listed in the status file instead.
- `docs/evidence/spike/*`: frozen evidence.
- README sections "AI Collaboration Narrative", "System design", "Design evidence", "Deliverables map", "Quality gates".
- `.pre-commit-config.yaml`, ruff and mypy configuration: gates do not loosen.
- No runtime dependency beyond those named in Task 1.

### Wire formats

Request `POST /dealerships/{dealership_id}/appointments`, header `Idempotency-Key: <uuid>`:

```json
{
  "service_type_id": 1,
  "start_at": "2027-03-26T09:00:00",
  "customer": {"id": "C-42", "email": null, "name": "Sam Lee"},
  "vehicle": {"id": null, "vin": "WVWZZZ1JZXW000001", "make": "VW", "model": "Golf"}
}
```

`start_at` is naive local wall time in the dealership zone, whole minutes; an offset or seconds is a schema 422. Unknown fields are a schema 422. `customer` needs `id` or `email`; `vehicle` needs `id` or `vin`; `vin` is normalised (upper case, whitespace removed) before validation and hashing.

Response 201 (also the body of `GET .../appointments/{id}`):

```json
{
  "appointment_id": 7, "dealership_id": 1, "service_type_id": 1,
  "bay_id": 2, "technician_id": 1, "status": "confirmed",
  "start_at": "2027-03-26T09:00:00Z", "end_at": "2027-03-26T10:00:00Z",
  "pickup_from": "2027-03-26T10:00:00Z", "timezone": "Europe/London",
  "customer": {"id": "C-42", "email": null, "name": "Sam Lee"},
  "vehicle": {"id": null, "vin": "WVWZZZ1JZXW000001", "make": "VW", "model": "Golf"}
}
```

Error body, every non-2xx: `{"code": "<code>", "message": "<text>", "errors": [...]}`; `errors` appears only on schema 422 and holds `{"loc": [...], "msg": "...", "type": "..."}` items (no `input`, no `url`). Code to status table (`interfaces/http/errors.py`):

| Code | Status | Final | Stored |
|---|---|---|---|
| `confirmed` | 201 | yes | yes |
| `validation` (schema, before BEGIN) | 400 malformed JSON or key; 413 body over 16 KiB (AC-17, D-058); 422 schema | yes | no |
| `not_found` | 404 | yes | no |
| `validation` (business, after claim) | 422 | yes | yes |
| `replay_conflict` | 422 | yes | no (the original row stays) |
| `capacity_exhausted` | 409 | yes | yes |
| `vehicle_already_booked` | 409 | yes | yes |
| `contention` | 409, header `Retry-After: 1` | no | no (claim rolled back) |
| `error` | 500 | no | no |

Availability `GET /dealerships/{id}/availability?service_type_id=3&from=2027-03-26&to=2027-03-30`:

```json
{
  "dealership_id": 1, "service_type_id": 3, "from": "2027-03-26", "to": "2027-03-30",
  "as_of": "2027-03-25T16:00:00.123456Z",
  "windows": [
    {"bay_id": 1, "technician_id": 1, "date": "2027-03-26",
     "earliest_start": "2027-03-26T09:00:00Z", "latest_start": "2027-03-26T11:00:00Z"}
  ]
}
```

Health: `GET /health/live` → 200 `{"status": "ok"}`; `GET /health/ready` → 200 `{"status": "ok"}` or 503 `{"status": "unavailable"}`.

Wide event, one JSON line on stdout per request, keys in this order: `v, ts, request_id, route, outcome, code, final, dealership_id, idempotency_key, service_type_id, attempts, deadlocks, candidates_pruned, replay, bay_id, technician_id, latency_ms` (ADR-013; null rules as there).

### Acceptance Criteria

- AC-01 Schema: `alembic upgrade head` on an empty database creates every table of the ERD, extension `btree_gist`, constraints `no_bay_overlap`, `no_technician_overlap`, `no_vehicle_overlap`, `bay_in_dealership`, `technician_in_dealership`, `valid_range`, `positive_duration`, `same_day_hours`, `weekday_range`, and runs `GRANT SET ON PARAMETER deadlock_timeout`; the seed loads two dealerships and three service types including one of 4,320 minutes.
- AC-02 Booking: a valid request returns 201 with the body above, `end_at = start_at + duration` in UTC, `pickup_from` derived; the row holds the snapshot and `vehicle_key`.
- AC-03 409 codes: `capacity_exhausted` when the pruned list is empty (final, stored); `vehicle_already_booked` on `no_vehicle_overlap` (final, stored); `contention` when the bound of 5 is hit with candidates left (transient, claim discarded, `Retry-After: 1`).
- AC-04 Idempotency boundary: every row of the ADR-008 table holds: 400 for malformed JSON or a non-UUID key, 413 for a body over the cap (AC-17, D-058), 404 unknown dealership, schema 422 never stored; business 422, 201 and final 409 stored and replayed; same key different body → 422 `replay_conflict`; concurrent same key → one appointment, identical answers.
- AC-05 Time: start outside hours, in the past, beyond 90 days, or in a DST gap → 422 stored; a repeated local time takes the first occurrence; a 4,320-minute service from Fri 2027-03-26 09:00 London ends 2027-03-29T09:00:00Z; `pickup_from` equals `end_at` when inside hours, else the next opening instant, skipping closed days.
- AC-06 Availability: the ADR-010 worked example returns exactly Friday `[09:00Z, 11:00Z]` and Monday `[13:00Z, 16:59Z]` for the one pair; windows over 14 days or outside the horizon → 422; response carries `as_of`.
- AC-07 Concurrency (V-002): 8 concurrent bookings of one slot at a dealership with 4 bays × 4 qualified technicians (test-owned fixture, D-044), the clients released together by a barrier before they send (D-049), yield exactly 4 × 201 and 4 × 409 `capacity_exhausted`, distinct bays and technicians among winners, 8 committed key rows, overlap count 0, whatever mix of 23P01 and 40P01 occurred.
- AC-08 Tenancy: an appointment referencing a bay or technician of another dealership is refused by the database; a dealership with no bays gets `capacity_exhausted`; with no qualified technician, 422.
- AC-09 Health: `/health/live` 200 always; `/health/ready` 200 with the database and 503 without.
- AC-10 Event: every response emits exactly one JSON line with the 17 keys in order; a booking line carries `attempts`, `deadlocks`, `candidates_pruned`, `replay`, `final`; no line contains an email, VIN or `vehicle_key`.
- AC-11 Demo: `make demo` boots db and api, runs `scripts/demo.sh` sections 1 to 8, and the last printed line is `0`.
- AC-12 Gates: `make lint` and `make test` pass on the branch; CI passes.
- AC-13 README: "API", "Running the demo", "Testing" filled; status line updated; other sections untouched.
- AC-14 Layers: `tests/test_architecture.py` passes: `domain` imports only the standard library and itself; `application` imports only `domain` and itself; `infrastructure` and `interfaces` never import each other; only `main` imports both.
- AC-15 Use cases run without a database: `BookAppointment` is exercised end to end against in-memory fakes (claim, replay, validation, attempts, contention rollback), and the fakes implement the same Protocols as the PostgreSQL adapters (mypy checks structural conformance).
- AC-16 Retry fallback (D-050): a writer that bypasses the dealership lock and takes a resource between the candidate read and the first INSERT costs the booking one attempt per lost resource; the booking lands on a remaining free pair (201) or ends with 409 `capacity_exhausted` when none remains; never a 5xx, never an overlap.
- AC-17 Request bounds (D-058, ADR-014): a request body over `MAX_BODY_BYTES` (16 KiB) is 413 `validation` in the house error body, never stored; a free string over its `max_length` in `schemas.py` is a schema 422 with `errors`, never stored.

### Test Cases

Edge and regression first, happy path last. Layer in the fourth column.

| TC | Case | AC | File (layer) |
|---|---|---|---|
| TC-01 | Attempt policy: `no_bay_overlap` prunes every candidate with that bay; `no_technician_overlap` prunes the technician; 40P01 keeps the pair (counted, nothing pruned; D-048); `no_vehicle_overlap` stops with `vehicle_already_booked` | AC-03 | test_attempts.py (domain) |
| TC-02 | Attempt policy: bound of 5 with candidates left → `contention`; pruned list empty → `capacity_exhausted`; empty input → `capacity_exhausted` with 0 attempts | AC-03 | test_attempts.py (domain) |
| TC-03 | `local_to_utc`: London 2027-03-28 01:30 raises `GapTime`; 2027-10-31 01:30 → 00:30Z (first occurrence); ordinary time converts | AC-05 | test_time_rules.py (domain) |
| TC-04 | `start_in_hours`: at `opens_at` true, at `closes_at` false, missing weekday false | AC-05 | test_time_rules.py |
| TC-05 | `end_at`: Fri 2027-03-26 09:00 London + 4,320 min = 2027-03-29T09:00:00Z, local 10:00 BST | AC-05 | test_time_rules.py |
| TC-06 | `pickup_from`: end inside hours → end; after close → next day's open; Saturday evening with Sunday closed → Monday 08:00 BST = 07:00Z | AC-05 | test_time_rules.py |
| TC-07 | Canonical hash: key order, whitespace, null fields and VIN spacing do not change the hash; UTC instant used | AC-04 | test_canonical.py (domain) |
| TC-08 | Windows arithmetic: merge of overlapping busy ranges; free gaps; duration subtracted on UTC before intersecting local day; closing bound `closes - 1 min` | AC-06 | test_windows.py (domain) |
| TC-09 | Use case with fakes: `reads.dealership` is never called (the dealership arrives as an argument); claim exists with other hash → `ReplayConflict`; claim exists with same hash → replay Outcome, `replay=True`, no attempt | AC-04 | test_book_appointment_usecase.py (application) |
| TC-10 | Use case with fakes: business failures (unknown service type, gap, past, horizon, outside hours, no qualified technician) → `validation` Outcome recorded on the key; no attempt | AC-05, AC-08 | test_book_appointment_usecase.py |
| TC-11 | Use case with fakes: scripted `reserve` results drive 201 recorded, `capacity_exhausted` recorded, `vehicle_already_booked` recorded, `contention` with the unit of work rolled back and nothing recorded; `AttemptGate` awaited exactly once before the first reserve; `serialise` called after the claim and before the gate and any reserve, never on a replay (D-048) | AC-03, AC-04 | test_book_appointment_usecase.py |
| TC-12 | Adapter: `reserve` returns `Confirmed` on a free pair; `ResourceTaken("no_bay_overlap", False)` on a bay clash and the transaction continues (a later INSERT in the same transaction succeeds); `ResourceTaken("no_vehicle_overlap", False)` on a vehicle clash; a non-constraint error re-raises | AC-03 | test_postgres_adapters.py (infrastructure) |
| TC-13 | Adapter: `claim` returns `None` on first insert and the stored row on the second; `record` fills code and body; `free_candidates` excludes busy bays and technicians and only lists qualified ones | AC-04, AC-02 | test_postgres_adapters.py |
| TC-14 | Layer rule: the AST import scan of `src/scheduler` finds no forbidden edge (AC-14 list) | AC-14 | test_architecture.py |
| TC-15 | Malformed JSON → 400 `validation`; missing key → 400; non-UUID key → 400; no key row | AC-04 | test_idempotency.py (interfaces) |
| TC-16 | Unknown dealership → 404 `not_found`, no key row | AC-04 | test_idempotency.py |
| TC-17 | Schema 422 (no identifier; unknown field; offset; seconds) → 422 with `errors`, no key row; corrected body under the same key → 201 | AC-04 | test_idempotency.py |
| TC-18 | Business 422 (outside hours) stored: same key same body replays; same key different body → 422 `replay_conflict` | AC-04, AC-05 | test_idempotency.py |
| TC-19 | 201 replay: same key same body → same status and body, one appointment row; event `replay` true on the second | AC-04 | test_idempotency.py |
| TC-20 | Parallel same key, same body → both 201, same `appointment_id`, one row, one key row | AC-04, AC-07 | test_concurrency.py |
| TC-21 | Unknown `service_type_id` → 422 stored; no qualified technician → 422; past → 422; beyond 90 days → 422; gap → 422 "does not exist" | AC-05, AC-08 | test_booking_api.py |
| TC-22 | Same VIN, overlapping time on a free pair → 409 `vehicle_already_booked`, stored and replayed; `" wvw zzz "` normalises to `WVWZZZ` | AC-03 | test_booking_api.py |
| TC-23 | Every pair busy → 409 `capacity_exhausted`, `attempts` 0; dealership with no bays → `capacity_exhausted` | AC-03, AC-08 | test_booking_api.py |
| TC-24 | Direct INSERT with another dealership's bay raises an integrity error naming `bay_in_dealership`; same for `technician_in_dealership` | AC-08 | test_booking_api.py |
| TC-25 | `GET .../appointments/{id}` 200 with the 201 body; 404 for another dealership's appointment and for an unknown id | AC-02 | test_booking_api.py |
| TC-26 | Back-to-back 09:00–10:00 and 10:00–11:00 on one pair both 201 | AC-02 | test_booking_api.py |
| TC-27 | Happy path 201: body fields, `end_at`, `pickup_from`; stored `vehicle_key = "id:<id>"` when only `id` is given | AC-02 | test_booking_api.py |
| TC-28 | Availability: 15-day window → 422; `to <= from` → 422; `to` beyond horizon → 422; unknown service type → 422; unknown dealership → 404 | AC-06 | test_availability.py |
| TC-29 | Availability worked example (London, 72 h, E1, E2, clock 2027-03-25T16:00Z): exactly the two windows of AC-06; `as_of` aware UTC | AC-06 | test_availability.py |
| TC-30 | Availability with no appointments: every open day `[opens, closes - 1 min]` shifted by the duration at the right end; Sunday absent | AC-06 | test_availability.py |
| TC-31 | V-002 race: 8 clients against a test-owned fixture of 4 bays and 4 qualified technicians (the seed's 2x2 allows only 2 concurrent winners; D-044); the clients wait on an `asyncio.Barrier(8)` and send together, no attempt gate (the bookings queue on the dealership lock; D-049); statuses {201: 4, 409: 4}; winners distinct; overlap 0; 8 key rows all recorded; events' `attempts` sum == 4 (one per winner, zero per loser: the bookings run one at a time and a loser reads an empty candidate list; D-048); elapsed printed | AC-07, AC-10 | test_concurrency.py |
| TC-39 | Retry fallback (D-050), two bookings through `create_app` with an `attempt_gate` that, when awaited, inserts in a separate `engine.begin()` transaction (no `serialise`) that commits on context exit an appointment occupying the case's first bay for the slot, then returns. (a) Dealership 100, 2 bays x 1 qualified technician, bypass row on bay 100: 201 on bay 101; event `attempts == 1 + candidates_pruned`, `candidates_pruned <= 1`, `deadlocks == 0`. (b) Dealership 110, 1 bay x 1 technician, bypass row on bay 110: 409 `capacity_exhausted`, event `attempts == 1`, `candidates_pruned == 1`. Overlap 0 after both; 3 appointment rows | AC-16 | test_concurrency.py |
| TC-32 | Event schema: one line per response, 17 keys in order, `v == 1`; `final` true for 201, final 409 and 422, false for `contention`; health lines carry null booking fields; no `@` and no VIN substring in any line | AC-10 | test_events.py |
| TC-33 | `/health/live` 200; `/health/ready` 200; with an engine on a closed port, 503 | AC-09 | test_health.py |
| TC-34 | Seed: 2 dealerships, 3 service types (one 4,320 min), dealership 1 has 2 bays and 2 technicians, both hold `general`, only technician 1 holds `bodywork`; `btree_gist` installed; the nine named constraints exist | AC-01 | test_seed.py |
| TC-35 | `make demo` on the compose stack: exit 0, last line `0` (manual, recorded in the status file) | AC-11 | scripts/demo.sh |
| TC-36 | `make lint` and `make test` green (manual, recorded) | AC-12 | — |
| TC-37 | ADR-008 precedence: unknown dealership with a schema-invalid body (no identifier, unknown field) → 404 `not_found`, no key row; malformed JSON on an unknown dealership → 400; missing key on an unknown dealership → 400 | AC-04 | test_idempotency.py |
| TC-38 | README inspection: `grep -c '^## API$\|^## Running the demo$\|^## Testing$' README.md` prints `3`; line 3 reads `Status: implemented; see Testing for the evidence.`; `git diff -U0 master -- README.md | grep '^@@'` lists hunks only at line 3 and inside the three sections (recorded in the status file with the hunk list) | AC-13 | README.md |
| TC-40 | Request bounds (D-058): oversized body is 413; an over-long string is 422 with the house error body. A body of `MAX_BODY_BYTES + 1` bytes with a valid key → 413 `{"code": "validation", "message": "request body exceeds 16384 bytes"}`, no key row; `customer.name` of 201 characters → 422 `validation` with one `errors` item, `loc` `["customer", "name"]`, `type` `string_too_long`, no key row | AC-17 | test_booking_api.py (interfaces) |

### Propagation and Rollback

Touches only this repository. Rollback: revert the branch merge; no migration runs against a shared database. After the audit the author updates design.md sections 2 and 6, docs/ai rows and the README narrative (D-038) and retires container `kl-spike-pg`.

## § Execution

Known traps (`docs/ai/lessons.md`): L-001 the barrier test at low N rarely produces 40P01; assert the invariant, accept either SQLSTATE. L-002 evidence runs with the production retry policy (bound 5, 100 ms deadlock timeout). L-003 SQLAlchemy asyncio needs greenlet. L-004 never write a value a CHECK refuses (`weekday` 0..6).

Commit protocol (D-040): one task is one or more commits; each commit reviewable in one sitting (diff in the low hundreds of lines); message form `SPEC-001 T<n>: <what> (design §<n>, ADR-<nnn>)` plus the attribution line; never push until the author says so; history kept. Every task ends with `uv run pre-commit run --all-files` green and `uv run mypy src` green. The implementation status file is `docs/ai/specs/SPEC-001-status.md` (per-task commit hashes, `V-002:` lines, demo output, deviations, additions, doc changes needed in No-Touch files); `Status: awaiting-audit` when done.

### Read before coding

- `docs/design.md` (whole); `docs/adr/ADR-004.md`, `ADR-008.md`, `ADR-009.md`, `ADR-010.md`, `ADR-013.md`
- `src/scheduler/main.py`, `src/scheduler/settings.py`, `migrations/env.py`, `alembic.ini`, `tests/test_health.py`
- `docs/evidence/spike/race_savepoint.py` (the savepoint pattern), `docs/evidence/spike/schema.sql`
- `Makefile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `pyproject.toml`, `README.md`
- Verify before editing: `grep -n "target_metadata" migrations/env.py` → line 15 `target_metadata = None`; `grep -n '"/health"' src/scheduler/main.py` → line 7.

### AC/TC Traceability

| AC | TC(s) | Task(s) | Validation |
|---|---|---|---|
| AC-01 | TC-34 | T2, T3 | `uv run pytest tests/test_seed.py -q` |
| AC-02 | TC-13, 25, 26, 27 | T4, T6, T7, T8 | `uv run pytest tests/test_booking_api.py -q` |
| AC-03 | TC-01, 02, 11, 12, 22, 23 | T5, T6, T7, T8 | `uv run pytest tests/test_attempts.py tests/test_book_appointment_usecase.py tests/test_postgres_adapters.py tests/test_booking_api.py -q` |
| AC-04 | TC-07, 09, 11, 13, 15–20, 37 | T4, T6, T7, T8, T11 | `uv run pytest tests/test_canonical.py tests/test_book_appointment_usecase.py tests/test_idempotency.py tests/test_concurrency.py -q` |
| AC-05 | TC-03–06, 10, 18, 21 | T4, T6, T8 | `uv run pytest tests/test_time_rules.py tests/test_booking_api.py -q` |
| AC-06 | TC-08, 28, 29, 30 | T10 | `uv run pytest tests/test_windows.py tests/test_availability.py -q` |
| AC-07 | TC-20, 31 | T11 | `uv run pytest tests/test_concurrency.py -q -s` |
| AC-08 | TC-10, 21, 23, 24 | T2, T6, T8 | as AC-02 |
| AC-09 | TC-33 | T9 | `uv run pytest tests/test_health.py -q` |
| AC-10 | TC-31, 32 | T9, T11 | `uv run pytest tests/test_events.py tests/test_concurrency.py -q` |
| AC-11 | TC-35 | T12 | `make demo` |
| AC-12 | TC-36 | T13 | `make lint && make test` |
| AC-13 | TC-38 | T13 | the three commands of TC-38, output recorded in the status file |
| AC-14 | TC-14 | T1 | `uv run pytest tests/test_architecture.py -q` |
| AC-15 | TC-09, 10, 11 | T6 | `uv run pytest tests/test_book_appointment_usecase.py -q` |
| AC-16 | TC-39 | T11 | `uv run pytest tests/test_concurrency.py -q -s` |
| AC-17 | TC-40 | T20 | `uv run pytest tests/test_booking_api.py -q` |

### Interfaces

The ports, in `src/scheduler/application/ports.py`. Adapters and fakes implement them structurally; nothing subclasses them.

```python
class Clock(Protocol):
    def now(self) -> datetime: ...  # aware UTC


class AttemptGate(Protocol):
    async def __call__(self) -> None: ...  # awaited once per booking before the first reserve


class SchedulingReadRepository(Protocol):
    """Reference data and read-only appointment queries. Usable outside a transaction."""

    async def dealership(self, dealership_id: int) -> Dealership | None: ...
    async def service_type(self, service_type_id: int) -> ServiceType | None: ...
    async def qualified_technicians(
        self, dealership_id: int, service_type_id: int
    ) -> list[int]: ...
    async def bays(self, dealership_id: int) -> list[int]: ...
    async def appointment(self, dealership_id: int, appointment_id: int) -> Appointment | None: ...
    async def busy_ranges(
        self, dealership_id: int, lo: datetime, hi: datetime
    ) -> list[BusyRange]: ...
    async def watermark(self) -> datetime: ...  # coalesce(pg_last_xact_replay_timestamp(), now())


class AppointmentRepository(Protocol):
    """Write side; bound to the unit of work's transaction."""

    async def free_candidates(
        self, dealership_id: int, qualified: list[int], start: datetime, end: datetime
    ) -> list[Candidate]: ...
    async def reserve(
        self, new: NewAppointment, candidate: Candidate
    ) -> Confirmed | ResourceTaken: ...
    async def by_id(self, appointment_id: int) -> Appointment: ...


class IdempotencyRepository(Protocol):
    """Bound to the unit of work's transaction."""

    async def claim(
        self, dealership_id: int, key: UUID, request_hash: str
    ) -> StoredResponse | None: ...
    async def record(
        self, dealership_id: int, key: UUID, code: str, body: Mapping[str, object]
    ) -> None: ...


class UnitOfWork(Protocol):
    """One transaction: BEGIN on enter; COMMIT on clean exit; ROLLBACK on exception.
    Sets SET LOCAL deadlock_timeout = '100ms' and statement_timeout = '2s' on enter (ADR-004)."""

    appointments: AppointmentRepository
    idempotency: IdempotencyRepository
    reads: SchedulingReadRepository  # same connection, for in-transaction reference reads

    # transaction-scoped advisory lock (pg_advisory_xact_lock): bookings of one dealership run
    # one at a time; between writers that honour it no lock cycles form, so no 40P01 under
    # contention (ADR-004 amendment, D-048); a writer outside it meets the retry fallback (D-050)
    async def serialise(self, dealership_id: int) -> None: ...

    async def __aenter__(self) -> "UnitOfWork": ...
    async def __aexit__(self, et, ev, tb) -> None: ...


UnitOfWorkFactory = Callable[[], UnitOfWork]
```

Domain types, in `src/scheduler/domain/model.py` (all `@dataclass(frozen=True)`):

| Type | Fields | Note |
|---|---|---|
| `Hours` | `weekday: int, opens_at: time, closes_at: time` | weekday 0 = Monday |
| `Dealership` | `id, name, zone: ZoneInfo, hours: Mapping[int, Hours]` | missing weekday = closed |
| `ServiceType` | `id, name, duration_minutes` | |
| `Customer` | `id: str | None, email: str | None, name: str | None` | id or email required (checked at the interface) |
| `Vehicle` | `id: str | None, vin: str | None, make: str | None, model: str | None` | `vin` already normalised |
| `BookingCommand` | `dealership_id, service_type_id, start_local: datetime (naive), customer, vehicle, idempotency_key: UUID` | property `vehicle_key`: vin, else `id:<id>` |
| `Candidate` | `bay_id, technician_id` | |
| `NewAppointment` | `dealership_id, service_type_id, start_at, end_at (aware UTC), customer, vehicle, vehicle_key` | |
| `Appointment` | `id, dealership_id, service_type_id, bay_id, technician_id, status, start_at, end_at, customer, vehicle` | `pickup_from` is derived at response time by `time_rules.pickup_from` |
| `Confirmed` | `appointment_id` | |
| `ResourceTaken` | `constraint: str | None, deadlock: bool` | constraint name from 23P01; `None` with `deadlock=True` for 40P01 |
| `BusyRange` | `bay_id, technician_id, start_at, end_at` | |
| `StoredResponse` | `request_hash, code: str | None, body: Mapping | None` | `code is None` while claimed and not yet recorded |
| `AttemptResult` | `code, attempts, deadlocks, candidates_pruned, candidate: Candidate | None, appointment_id: int | None` | in `domain/attempts.py` |

Domain functions (signatures; rules in the ADR named):

| Module | Function | Rule |
|---|---|---|
| `time_rules.py` | `canonical_utc(naive, zone) -> datetime` | deterministic instant for any wall time, used by the hash |
| | `local_to_utc(naive, zone) -> datetime` | raises `GapTime` when the round trip changes the wall time; `fold=0` so a repeated time takes the first occurrence (ADR-009) |
| | `start_in_hours(naive, dealership) -> bool` | `opens_at <= t < closes_at` on the local weekday |
| | `end_at(start_utc, duration_minutes) -> datetime` | elapsed duration in UTC |
| | `day_window_utc(day: date, hours, zone) -> (opens, closes)` | |
| | `pickup_from(end_utc, dealership) -> datetime` | first opening instant at or after `end_at`; bounded walk of 14 days, raises `NoOpeningInstant` after |
| | constants `HORIZON = 90 days`, `PICKUP_WALK_DAYS = 14` | |
| `canonical.py` | `normalise_vin(raw) -> str | None` | upper case, whitespace removed, empty → `None` |
| | `canonical_hash(command, zone) -> str` | sha256 of `json.dumps(sort_keys, separators=(",", ":"))` over `{service_type_id, start_at: canonical_utc(...).isoformat(), customer, vehicle}` with `None` values omitted (ADR-008) |
| `attempts.py` | `RETRY_BOUND = 5` | |
| | `shuffled(candidates) -> list[Candidate]` | random order, so simultaneous requests spread over pairs (ADR-004) |
| | `run_attempts(candidates, reserve: Callable[[Candidate], Awaitable[Confirmed | ResourceTaken]], bound=RETRY_BOUND) -> AttemptResult` | a lost resource is never tried again: `no_bay_overlap` prunes the bay, `no_technician_overlap` prunes the technician, an unknown constraint prunes the pair, 40P01 keeps the pair (D-048), `no_vehicle_overlap` stops with `vehicle_already_booked`; empty list → `capacity_exhausted`; bound hit with pairs left → `contention` |
| `windows.py` | `merge(ranges)`, `free(busy, lo, hi)`, `start_windows(dealership, days, duration, busy_by_bay, busy_by_tech, bays, techs, earliest_now) -> list[Window]` | subtract the duration on UTC instants, then intersect with each local day window; latest start is `min(free_end - duration, closes - 1 min)` (ADR-010) |
| `errors.py` | `DomainError` base; `GapTime(ValueError)`, `NoOpeningInstant`, `NotFound(what)`, `ValidationFailed(message)`, `ReplayConflict`, `Contention(result: AttemptResult)` | HTTP mapping lives in the interface layer |

Application `Outcome` (`application/outcomes.py`, frozen): `code: str`, `body: Mapping[str, object]`, `final: bool`, `replay: bool = False`, `attempts: int = 0`, `deadlocks: int = 0`, `candidates_pruned: int = 0`, `bay_id: int | None = None`, `technician_id: int | None = None`. Response bodies for appointments are built by `application/presenters.py: appointment_body(appointment, dealership) -> dict` (adds `pickup_from` and `timezone`), the single place the 201 body and the GET body are shaped, so the stored replay body and a live body are identical.

### Booking sequence (`application/book_appointment.py`)

`BookAppointment(uow: UnitOfWorkFactory, clock: Clock, gate: AttemptGate | None = None)`; `async def execute(self, command: BookingCommand, dealership: Dealership) -> Outcome`. The dealership is loaded by the caller before schema validation (ADR-008 step 2, Known Facts 9). Raises `ReplayConflict`; every other path returns an `Outcome`. The transaction is the subtle part; it is given in full:

```python
async def execute(self, cmd: BookingCommand, dealership: Dealership) -> Outcome:
    # dealership already loaded by the interface layer, before BEGIN (design §2, ADR-008 step 2)
    request_hash = canonical_hash(cmd, dealership.zone)
    try:
        async with self.uow() as tx:  # BEGIN + SET LOCAL
            stored = await tx.idempotency.claim(
                cmd.dealership_id, cmd.idempotency_key, request_hash
            )
            if stored is not None:
                if stored.request_hash != request_hash:
                    raise ReplayConflict()
                return replay_outcome(stored)  # final=True, replay=True
            await tx.serialise(cmd.dealership_id)  # this request books: one at a time (D-048)
            failure, service_type, start_utc = await self._validate(tx.reads, dealership, cmd)
            if failure is not None:
                body = validation_body(failure)
                await tx.idempotency.record(
                    cmd.dealership_id, cmd.idempotency_key, "validation", body
                )
                return Outcome("validation", body, final=True)
            end_utc = end_at(start_utc, service_type.duration_minutes)
            qualified = await tx.reads.qualified_technicians(cmd.dealership_id, service_type.id)
            candidates = shuffled(
                await tx.appointments.free_candidates(
                    cmd.dealership_id, qualified, start_utc, end_utc
                )
            )
            new = NewAppointment(
                cmd.dealership_id,
                service_type.id,
                start_utc,
                end_utc,
                cmd.customer,
                cmd.vehicle,
                cmd.vehicle_key,
            )
            if self.gate is not None:
                await self.gate()  # test seam: a writer around the lock (TC-39, D-050)
            result = await run_attempts(candidates, lambda c: tx.appointments.reserve(new, c))
            if result.code == "confirmed":
                appointment = await tx.appointments.by_id(result.appointment_id)
                body = appointment_body(appointment, dealership)
                await tx.idempotency.record(
                    cmd.dealership_id, cmd.idempotency_key, "confirmed", body
                )
                return Outcome(
                    "confirmed",
                    body,
                    final=True,
                    attempts=result.attempts,
                    deadlocks=result.deadlocks,
                    candidates_pruned=result.candidates_pruned,
                    bay_id=appointment.bay_id,
                    technician_id=appointment.technician_id,
                )
            if result.code in ("capacity_exhausted", "vehicle_already_booked"):
                body = conflict_body(result.code)
                await tx.idempotency.record(
                    cmd.dealership_id, cmd.idempotency_key, result.code, body
                )
                return Outcome(
                    result.code,
                    body,
                    final=True,
                    attempts=result.attempts,
                    deadlocks=result.deadlocks,
                    candidates_pruned=result.candidates_pruned,
                )
            raise Contention(result)  # leaves the block: ROLLBACK, claim discarded
    except Contention as c:
        return Outcome(
            "contention",
            contention_body(),
            final=False,
            attempts=c.result.attempts,
            deadlocks=c.result.deadlocks,
            candidates_pruned=c.result.candidates_pruned,
        )
```

`_validate` order (ADR-008 step 6, each a stored 422): unknown service type → `local_to_utc` (`GapTime` → "does not exist") → past (`start_utc < clock.now()`) → beyond `HORIZON` → `start_in_hours` → no qualified technician. Rules the implementation must keep: `ReplayConflict` is raised inside the block but the context manager's rollback writes nothing, because the original row belongs to another transaction; `DBAPIError` is never caught here, the adapter is the only place; the `record` of a stored outcome happens before the block exits.

`GetAppointment(reads).execute(dealership_id, appointment_id) -> Mapping` raises `NotFound` for an unknown dealership or an appointment outside it, and returns `appointment_body`. `GetAvailability(reads, clock).execute(dealership_id, service_type_id, from_date, to_date) -> Mapping`: validation (`to <= from`, span > 14 days, `from < today` in the dealership zone, `to > today + HORIZON`, unknown service type) raises `ValidationFailed`; then `watermark`, `bays`, `qualified_technicians`, `busy_ranges(lo, hi + duration)` and `start_windows`; windows sorted by date, bay, technician, earliest start.

### Reserve adapter (`infrastructure/postgres/repositories.py`)

The only place that reads SQLSTATE. Given in full because the savepoint and the error boundary carry the guarantee:

```python
async def reserve(self, new: NewAppointment, candidate: Candidate) -> Confirmed | ResourceTaken:
    stmt = insert(appointment).values(**row_of(new, candidate)).returning(appointment.c.id)
    try:
        async with (
            self.conn.begin_nested()
        ):  # SAVEPOINT; rolled back on exception, released on success
            appointment_id = (await self.conn.execute(stmt)).scalar_one()
    except DBAPIError as e:
        orig = e.orig
        if isinstance(orig, psycopg.Error):
            if orig.sqlstate == "23P01":
                return ResourceTaken(orig.diag.constraint_name, deadlock=False)
            if orig.sqlstate == "40P01":
                return ResourceTaken(None, deadlock=True)
        raise  # anything else is a 5xx, never "next pair"
    return Confirmed(int(appointment_id))
```

Other adapter rules: `claim` is `INSERT ... ON CONFLICT DO NOTHING RETURNING key`; when nothing returns, select the row and return `StoredResponse`. `record` is an `UPDATE` by `(dealership_id, key)`. `free_candidates` runs the two `NOT EXISTS` queries of the v1 draft (free bays of the dealership; free technicians among `qualified`) and returns the cross product; the shuffle is domain policy. `qualified_technicians` is the double `NOT EXISTS` over `service_type_required_skill` and `technician_skill`, so zero required skills qualifies every technician (ADR-006). `PostgresUnitOfWork(engine)`: `__aenter__` opens a connection, begins, executes the two `SET LOCAL`, builds the three adapters on that connection; `__aexit__` commits or rolls back and closes. `PostgresSchedulingReadRepository(connect: Callable[[], AsyncContextManager[AsyncConnection]])` takes `engine.connect` for the pre-transaction path and a one-connection context for the in-transaction path, so one class serves both. `engine.py: make_engine(url)` with `pool_size=10, max_overflow=10`. `clock.py: SystemClock.now()` returns `datetime.now(UTC)`.

### HTTP layer (`interfaces/http/`)

- `schemas.py`: pydantic `BookingRequest` (`extra="forbid"`; `start_at` naive and whole minutes; `Customer` id or email; `Vehicle` id or vin, vin through `domain.canonical.normalise_vin`), `AppointmentOut`, `AvailabilityOut` (`from`/`to` aliases), `Window`, `ErrorOut`; `to_command(req, dealership_id, key) -> BookingCommand` is the one mapping function (accepted duplication, D-041).
- `errors.py`: `STATUS_OF_CODE` table (Wire formats); handlers for `DomainError` subclasses, `pydantic.ValidationError` (422, `errors` from `.errors()` with `input` and `url` stripped), `json.JSONDecodeError` (400) and FastAPI's `RequestValidationError` (query and path errors, 422); a missing or non-UUID `Idempotency-Key` → 400 `validation`.
- `dependencies.py`: `idempotency_key(request) -> UUID` (header dependency, 400 `validation` when missing or not a UUID); `UseCases` frozen dataclass (`reads`, `book_appointment`, `get_appointment`, `get_availability: GetAvailability | None = None` until T10b). The container is never stored on `app.state` (Known Facts 3): each router module exposes `build_router(uc: UseCases) -> APIRouter` and the handlers close over `uc`; `create_app` builds the container once and calls the factories.
- `appointments.py`: `POST` declares no typed body parameter (so FastAPI performs no body validation of its own; `openapi_extra` carries `BookingRequest.model_json_schema()` for `/docs`). Handler order, ADR-008 steps 1–4: `raw = await request.json()` (`JSONDecodeError` → 400 `validation`, `json_invalid`; `BodyTooLarge` from `limits.py` → 413 `validation` when the body exceeds 16 KiB, D-058); `dealership = await uc.reads.dealership(dealership_id)` (`None` → 404 `not_found`); `req = BookingRequest.model_validate(raw)` (`pydantic.ValidationError` → 422 `validation` through the handler in `errors.py`); `cmd = to_command(req, dealership_id, key)`. It then sets `ev.route = "book_appointment"`, calls `BookAppointment.execute(cmd, dealership)`, copies `Outcome` fields into the event, answers `STATUS_OF_CODE[outcome.code]` with `Retry-After: 1` on `contention`; `GET` calls `GetAppointment`.
- `availability.py`: `GET` with `from`/`to` query aliases, calls `GetAvailability`.

The booking handler, given in full because the ADR-008 order is the subtle part (`interfaces/http/appointments.py`):

```python
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import ValidationError

from scheduler.application.book_appointment import BookAppointment
from scheduler.domain.errors import NotFound
from scheduler.interfaces.http.dependencies import UseCases, idempotency_key
from scheduler.interfaces.http.errors import STATUS_OF_CODE
from scheduler.interfaces.http.schemas import BookingRequest, to_command

BOOKING_BODY: dict[str, Any] = {
    "requestBody": {"content": {"application/json": {"schema": BookingRequest.model_json_schema()}}}
}


def build_router(uc: UseCases) -> APIRouter:
    router = APIRouter(prefix="/dealerships/{dealership_id}/appointments")

    @router.post("", status_code=201, name="book_appointment", openapi_extra=BOOKING_BODY)
    async def book_appointment(
        dealership_id: int,
        request: Request,
        response: Response,
        key: UUID = Depends(idempotency_key),  # ADR-008 step 1: header before anything else
    ) -> dict[str, Any]:
        return await _book(uc, dealership_id, request, response, key)

    @router.get("/{appointment_id}", name="get_appointment")
    async def get_appointment(dealership_id: int, appointment_id: int) -> dict[str, Any]:
        return dict(await uc.get_appointment.execute(dealership_id, appointment_id))

    return router


async def _book(
    uc: UseCases, dealership_id: int, request: Request, response: Response, key: UUID
) -> dict[str, Any]:
    raw = await request.json()  # step 1: json.JSONDecodeError -> 400 (errors.py)
    dealership = await uc.reads.dealership(dealership_id)
    if dealership is None:  # step 2: before schema validation
        raise NotFound("dealership")  # -> 404 not_found (errors.py)
    try:
        req = BookingRequest.model_validate(raw)  # step 3: pydantic.ValidationError -> 422
    except ValidationError as exc:
        raise exc  # handled in errors.py; explicit for readers
    cmd = to_command(req, dealership_id, key)  # step 4: command carries no HTTP types
    ev = request.state.ev
    ev["route"] = "book_appointment"
    ev["idempotency_key"] = str(key)
    outcome = await uc.book_appointment.execute(cmd, dealership)  # steps 5-7 inside the use case
    for field in (
        "code",
        "final",
        "replay",
        "attempts",
        "deadlocks",
        "candidates_pruned",
        "bay_id",
        "technician_id",
    ):
        ev[field] = getattr(outcome, field)
    response.status_code = STATUS_OF_CODE[outcome.code]
    if outcome.code == "contention":
        response.headers["Retry-After"] = "1"
    return dict(outcome.body)
```

`_book` is a module-level function so the ADR-008 order is testable without building a router. The `try/except` around `model_validate` re-raises on purpose: it marks the step boundary for a reader and the `errors.py` handler for `pydantic.ValidationError` produces the 422 body. No typed body parameter exists on this route, so FastAPI never validates the body before step 2.

- `health.py`: `live` constant; `ready` runs `SELECT 1` on the engine, any exception → 503.
- `events.py`: middleware creates `request.state.ev` with the 17 keys in order, times the call, defaults `route` from the matched route name, emits one line through `sys.stdout` at call time, maps an unhandled exception to 500 `error` with `final=False` and still emits.
- `main.py`: `create_app(engine=None, clock=None, attempt_gate=None)`; builds `SystemClock`, `PostgresSchedulingReadRepository(engine.connect)`, `PostgresUnitOfWork` factory, the use cases (`BookAppointment` and `GetAppointment` from T8b; `GetAvailability` added in T10b); builds one `UseCases` container and passes it to `appointments.build_router(uc)`, `availability.build_router(uc)` (T10b) and `health.build_router(engine)`; nothing but the engine goes on `app.state` (`app.state.engine`, readiness only); mounts middleware, handlers; lifespan disposes an engine it created.

### Tasks

Each task: allowed paths, done-when, the tests it adds (TC numbers), and the commit message. Return level if blocked: `return_to_execution` unless stated.

**T1: Dependencies, package skeleton, layer-rule test** (design §4, D-041)
Paths: `pyproject.toml`, `uv.lock`, `src/scheduler/{domain,application,infrastructure,infrastructure/postgres,interfaces,interfaces/http}/__init__.py`, `tests/test_architecture.py`, `docs/ai/specs/SPEC-001-status.md` (created here with the header `# SPEC-001 implementation status`, `Status: in-progress`, and one `## T1` section; every later task appends its own `## T<n>` section, so the status file is an allowed path for every task).
Steps: step 1 is the branch: `git switch master && git switch -c feat/spec-001-booking-service` (branch already present locally → `git switch feat/spec-001-booking-service`); `git branch --show-current` prints `feat/spec-001-booking-service` and `git merge-base --is-ancestor master HEAD` exits 0 before any edit. Then dependencies become `fastapi`, `uvicorn[standard]`, `psycopg[binary,pool]`, `sqlalchemy[asyncio]>=2`, `greenlet`, `alembic`, `pydantic-settings`; `uv sync`; `uv run python -c "from sqlalchemy.ext.asyncio import create_async_engine"` prints nothing. `test_architecture.py` walks `src/scheduler/**/*.py` with `ast`, collects absolute imports, and asserts the AC-14 edges with the standard-library set from `sys.stdlib_module_names`.
Done when: TC-14 passes (on an empty skeleton it passes trivially and will guard every later task); lint green.
Commit: `SPEC-001 T1: dependencies, layer skeleton, architecture test (design §4, D-041)`.

**T2: Schema migration and Core tables** (design §2, ADR-004)
Paths: `migrations/env.py:14-15`, `migrations/versions/0001_schema.py`, `src/scheduler/infrastructure/postgres/schema.py`, `tests/conftest.py`, `tests/test_seed.py` (constraint check only).
DDL, the guarantee, given in full:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE dealership (
    id        serial PRIMARY KEY,
    name      text NOT NULL,
    timezone  text NOT NULL
);

CREATE TABLE opening_hours (
    dealership_id int  NOT NULL REFERENCES dealership (id),
    weekday       int  NOT NULL,                        -- 0 = Monday
    opens_at      time NOT NULL,
    closes_at     time NOT NULL,
    PRIMARY KEY (dealership_id, weekday),
    CONSTRAINT same_day_hours CHECK (opens_at < closes_at),
    CONSTRAINT weekday_range  CHECK (weekday BETWEEN 0 AND 6)
);

CREATE TABLE service_bay (
    id            serial PRIMARY KEY,
    dealership_id int  NOT NULL REFERENCES dealership (id),
    name          text NOT NULL,
    CONSTRAINT service_bay_id_dealership UNIQUE (id, dealership_id)
);

CREATE TABLE technician (
    id            serial PRIMARY KEY,
    dealership_id int  NOT NULL REFERENCES dealership (id),
    name          text NOT NULL,
    CONSTRAINT technician_id_dealership UNIQUE (id, dealership_id)
);

CREATE TABLE skill (
    id   serial PRIMARY KEY,
    name text NOT NULL UNIQUE
);

CREATE TABLE technician_skill (
    technician_id int NOT NULL REFERENCES technician (id),
    skill_id      int NOT NULL REFERENCES skill (id),
    PRIMARY KEY (technician_id, skill_id)
);

CREATE TABLE service_type (
    id               serial PRIMARY KEY,
    name             text NOT NULL,
    duration_minutes int  NOT NULL,
    CONSTRAINT positive_duration CHECK (duration_minutes > 0)
);

CREATE TABLE service_type_required_skill (
    service_type_id int NOT NULL REFERENCES service_type (id),
    skill_id        int NOT NULL REFERENCES skill (id),
    PRIMARY KEY (service_type_id, skill_id)
);

CREATE TABLE appointment (
    id              serial PRIMARY KEY,
    dealership_id   int  NOT NULL REFERENCES dealership (id),
    bay_id          int  NOT NULL,
    technician_id   int  NOT NULL,
    service_type_id int  NOT NULL REFERENCES service_type (id),
    start_at        timestamptz NOT NULL,
    end_at          timestamptz NOT NULL,
    status          text NOT NULL DEFAULT 'confirmed',
    customer_id     text,
    customer_email  text,
    customer_name   text,
    vehicle_id      text,
    vin             text,
    vehicle_key     text NOT NULL,
    make            text,
    model           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    -- Tenancy: a bay or technician of another dealership cannot be referenced (ADR-004).
    CONSTRAINT bay_in_dealership
        FOREIGN KEY (bay_id, dealership_id) REFERENCES service_bay (id, dealership_id),
    CONSTRAINT technician_in_dealership
        FOREIGN KEY (technician_id, dealership_id) REFERENCES technician (id, dealership_id),
    -- An empty or inverted range overlaps nothing and would stack without limit.
    CONSTRAINT valid_range CHECK (end_at > start_at),
    CONSTRAINT no_bay_overlap
        EXCLUDE USING gist (bay_id WITH =, tstzrange(start_at, end_at) WITH &&),
    CONSTRAINT no_technician_overlap
        EXCLUDE USING gist (technician_id WITH =, tstzrange(start_at, end_at) WITH &&),
    CONSTRAINT no_vehicle_overlap
        EXCLUDE USING gist (
            dealership_id WITH =, vehicle_key WITH =, tstzrange(start_at, end_at) WITH &&
        )
);

CREATE TABLE idempotency_key (
    dealership_id   int   NOT NULL REFERENCES dealership (id),
    key             uuid  NOT NULL,
    request_hash    text  NOT NULL,
    response_code   text,                               -- NULL while claimed and not yet recorded
    response_body   jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dealership_id, key)
);

-- deadlock_timeout is superuser-level; the booking transaction sets it locally (ADR-004).
GRANT SET ON PARAMETER deadlock_timeout TO CURRENT_USER;
```

`schema.py` mirrors the DDL as SQLAlchemy Core `Table` objects for queries (the migration owns the DDL; `env.py` points `target_metadata` at this metadata). `conftest.py`: session-scoped testcontainers PostgreSQL 16 running `alembic upgrade head`; function-scoped `engine` that truncates `appointment`, `idempotency_key` and deletes fixture rows with ids ≥ 100; `make_dealership(engine, id, *, timezone, hours, bays, technicians)` helper writing rows ≥ 100; `booking_body(...)`; `overlap_count(engine)` running the overlap SQL of design §5; `barrier_gate(n)` returning an awaitable over `asyncio.Barrier(n)` with a 10 s timeout (removed at the final gate: unused since D-049, TC-31 holds its barrier in the test).
Done when: the nine named constraints and `btree_gist` are found in `pg_constraint` and `pg_extension` (TC-34 part); lint green.
Commits: `SPEC-001 T2a: schema migration and Core tables (design §2, ADR-004)`; `SPEC-001 T2b: test harness on testcontainers (ADR-002)`.

**T3: Seed migration** (ADR-009, D-041 item 4)
Paths: `migrations/versions/0002_seed.py`, `tests/test_seed.py`.
Content: dealership 1 "Riverside Motors" `Europe/London` Mon–Sat 08:00–18:00; dealership 2 "Harbour Motors" `Asia/Ho_Chi_Minh` Mon–Fri 08:00–17:00; skills `general` (1), `bodywork` (2); service types `Oil change` 60 (needs general), `Major service` 180 (general), `Bodywork` 4,320 (bodywork); bays 1, 2 at dealership 1 and 3 at dealership 2; technicians Ada (1: general, bodywork), Grace (2: general) at dealership 1, Minh (3: general) at dealership 2; sequences moved to 99.
Done when: TC-34 passes. Commit: `SPEC-001 T3: seed migration (ADR-009, D-041)`.

**T4: Domain model, time rules, canonical hash** (ADR-008, ADR-009)
Paths: `src/scheduler/domain/{model,errors,time_rules,canonical}.py`, `tests/test_time_rules.py`, `tests/test_canonical.py`.
Done when: TC-03–07 pass; `domain` imports nothing outside the standard library (TC-14). Commit: `SPEC-001 T4: domain model, time rules, canonical hash (ADR-008, ADR-009)`.

**T5: Attempt policy** (design §3, ADR-004)
Paths: `src/scheduler/domain/attempts.py`, `tests/test_attempts.py`.
Tests use a scripted `reserve` coroutine returning a fixed sequence and recording the candidates it saw. Done when: TC-01, TC-02 pass. Commit: `SPEC-001 T5: attempt policy, next pair never same pair (design §3, ADR-004)`. Amended by D-048: "never same pair" applies to a named 23P01 loss; a 40P01 names no resource, keeps the pair in the candidate list (attempt and deadlock counted, nothing pruned), and the bound still ends the run.

**T6: Ports, outcomes, booking use case, fakes** (design §2, §3, ADR-008)
Paths: `src/scheduler/application/{ports,outcomes,presenters,book_appointment,get_appointment}.py`, `tests/fakes.py`, `tests/test_book_appointment_usecase.py`.
`tests/fakes.py`: `FakeReads` (dicts of dealerships, service types, qualification, appointments), `FakeAppointments` (scripted `reserve` results, records inserted rows), `FakeIdempotency` (dict keyed by `(dealership_id, key)`), `FakeUnitOfWork` (snapshot on enter, restore on exception so a rollback is observable, `committed` flag), `FixedClock`, `CountingGate`. mypy checks the fakes against the Protocols in the tests' type run (`uv run mypy tests/fakes.py`).
Done when: TC-09–11 pass without a database. Commits: `SPEC-001 T6a: application ports and outcomes (design §2)`; `SPEC-001 T6b: BookAppointment use case with fakes (design §3, ADR-008)`.

**T7: PostgreSQL adapters and unit of work** (ADR-004, ADR-008)
Paths: `src/scheduler/infrastructure/{clock}.py`, `src/scheduler/infrastructure/postgres/{engine,unit_of_work,repositories}.py`, `tests/test_postgres_adapters.py`.
Done when: TC-12, TC-13 pass on testcontainers; the end-to-end use case against the real adapters books one appointment. Commits: `SPEC-001 T7a: reserve adapter with savepoint and SQLSTATE boundary (ADR-004)`; `SPEC-001 T7b: read, idempotency adapters and unit of work (ADR-008)`.

**T8: HTTP layer for appointments and the composition root** (design §3, ADR-008)
Paths: `src/scheduler/interfaces/http/{schemas,errors,dependencies,appointments,events(stub),health(stub)}.py`, `src/scheduler/main.py`, `tests/test_booking_api.py`, `tests/test_idempotency.py`.
The events middleware is a pass-through stub here (sets `request.state.ev = {}`) and health is a stub router; both are replaced in T9. TC-19's event assertion is a separate test function marked `xfail(strict=True)` until T9; the status and body assertions of TC-19 pass in T8.
Done when: TC-15–19 (TC-19 event part xfail), TC-21–27, TC-37 pass; `create_app` builds `UseCases(reads, book_appointment, get_appointment)` and `app.state` carries only `engine`. Commits: `SPEC-001 T8a: HTTP schemas, error mapping, dependencies (design §3)`; `SPEC-001 T8b: appointments router and composition root (design §2, ADR-008)`.

**T9: Wide events and health** (design §5, ADR-013)
Paths: `src/scheduler/interfaces/http/{events,health}.py`, `tests/test_events.py`, `tests/test_health.py`, `tests/test_idempotency.py` (xfail removed).
Done when: TC-32, TC-33 pass; TC-19 passes without xfail. Commit: `SPEC-001 T9: wide event middleware and health split (design §5, ADR-013)`.

**T10: Availability** (ADR-010)
Paths: `src/scheduler/domain/windows.py`, `src/scheduler/application/get_availability.py`, `src/scheduler/interfaces/http/availability.py`, `src/scheduler/infrastructure/postgres/repositories.py` (adds the read methods `bays`, `busy_ranges`, `watermark`; the Protocol in `ports.py` already declares them from T6a), `src/scheduler/main.py` (T10b adds `GetAvailability` to the container and mounts the availability router), `tests/test_windows.py`, `tests/test_availability.py`.
Done when: TC-08, TC-28–30 pass. Commits: `SPEC-001 T10a: window arithmetic (ADR-010)`; `SPEC-001 T10b: GetAvailability use case and route (ADR-010)`.

**T11: Concurrency evidence** (design §3, §5, V-002)
Paths: `tests/test_concurrency.py`. Return level if blocked: `return_to_contract` (a failed invariant is a design defect).
The test, given in full because its assertions are the evidence:

```python
async def test_v002_race_eight_clients_four_pairs(engine, capsys) -> None:
    """Production retry policy (bound 5, deadlock_timeout 100 ms); either SQLSTATE accepted (L-001).

    The clients are released together by a barrier before they send (D-049); inside the service
    the bookings of the dealership queue on the advisory lock (ADR-004 amendment, D-048), so no
    attempt gate is injected and no 40P01 is expected.
    """
    await make_dealership(
        engine, 100, bays=[100, 101, 102, 103], technicians={100: [1], 101: [1], 102: [1], 103: [1]}
    )
    n = 8
    app = create_app(engine=engine, clock=FixedClock(FIXED_NOW))
    start = asyncio.Barrier(n)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:

        async def one(i: int) -> httpx.Response:
            async with asyncio.timeout(10):
                await start.wait()
            return await client.post(
                URL,
                json=booking_body(vin=f"RACEVIN{i:02d}"),
                headers={"Idempotency-Key": str(uuid4())},
            )

        started = time.perf_counter()
        responses = await asyncio.gather(*(one(i) for i in range(n)))
        elapsed_ms = (time.perf_counter() - started) * 1000

    statuses = Counter(r.status_code for r in responses)
    assert statuses == {201: 4, 409: 4}, [r.json() for r in responses]
    winners = [r.json() for r in responses if r.status_code == 201]
    assert (
        len({w["bay_id"] for w in winners}) == 4 and len({w["technician_id"] for w in winners}) == 4
    )
    assert all(r.json()["code"] == "capacity_exhausted" for r in responses if r.status_code == 409)
    assert await overlap_count(engine) == 0
    async with engine.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM appointment"))).scalar_one() == 4
        keys = (
            await conn.execute(text("SELECT count(*), count(response_code) FROM idempotency_key"))
        ).one()
    assert tuple(keys) == (n, n)

    evs = [
        json.loads(ln) for ln in capsys.readouterr().out.splitlines() if '"book_appointment"' in ln
    ]
    assert len(evs) == n and sum(e["attempts"] for e in evs) == 4  # serialised: no retries
    assert all(e["attempts"] == 0 for e in evs if e["code"] == "capacity_exhausted")
    deadlocks = sum(e["deadlocks"] for e in evs)
    print(
        f"\nV-002: {n} clients, 4 pairs, attempts={sum(e['attempts'] for e in evs)}, deadlocks={deadlocks},"
        f" max latency_ms={max(e['latency_ms'] for e in evs)}, wall={elapsed_ms:.0f} ms, overlaps=0"
    )
```

Plus TC-20 (two concurrent POSTs with one key: both 201, same body, one row, one key row).

Plus TC-39 (D-050), `test_retry_fallback_when_a_writer_bypasses_the_lock`: the attempt gate is the seam for the bypassing writer; it runs after the candidate read and before the first INSERT, exactly the window the dealership lock closes for requests that honour it. The bypass inserts through `engine.begin()` with `row_of`-shaped values (ids ≥ 100, the same slot as `booking_body()`), so the row commits outside the booking transaction. Case (a) shows the loop landing on the free pair (the shuffle decides whether the blocked bay is tried first, hence `attempts == 1 + candidates_pruned`); case (b) shows the clean 409 when the only pair is lost. Both prove the retry loop is live as the fallback behind the lock (ADR-004 amendment).
Done when: three consecutive runs pass (`for i in 1 2 3; do uv run pytest tests/test_concurrency.py -q -s || break; done`); the `V-002:` lines go into the status file. Commit: `SPEC-001 T11: V-002 concurrency evidence and parallel same-key test (design §3, ADR-013)`.

**T12: Demo, compose, Makefile** (ADR-012, D-035)
Paths: `scripts/demo.sh`, `docker-compose.yml` `api.command`, `Makefile` `demo` target.
`api` runs `alembic upgrade head && uvicorn scheduler.main:create_app --factory --host 0.0.0.0 --port 8000`. `make demo` is `docker compose up -d --build --wait db api` then `scripts/demo.sh`. The script (`set -euo pipefail`, `jq` required) runs eight sections against dealership 1: health; book Oil change next Monday 09:00; replay same key; same key different body → `replay_conflict`; same car new key overlapping → `vehicle_already_booked`; availability; the race (8 background curls on the Monday after against the seed's 2 bays x 2 technicians, so 2 winners and 6 `capacity_exhausted` are the expected split; each response in its own file, per-client line, then the last 8 `book_appointment` events from `docker compose logs`); the overlap SQL through `psql`, printed last. A clean rerun is `make down && make demo` (README).
Done when: TC-35 recorded in the status file. Commit: `SPEC-001 T12: demo script, compose api migrates on start, make demo (ADR-012, D-035)`.

**T13: CI, README, gates** (design §6 pointer only)
Paths: `.github/workflows/ci.yml` (remove the postgres service and `DATABASE_URL`), `README.md` sections "API", "Running the demo", "Testing" and the status line (line 3 becomes `Status: implemented; see Testing for the evidence.`).
"API": the five endpoints, the `Idempotency-Key` rule, the request and 201 example, the error body and the code table, Swagger at `/docs`. "Running the demo": `make demo`, the eight sections, last line `0`, clean rerun. "Testing": `make test` (Docker required), one line per test file and what it proves, the race test alone with output, the L-001 rule, "Known limitations": no request-level deadline; `statement_timeout` is per statement; a vehicle by VIN once and by id once yields two keys; hours and seed change by migration; the compose role is a superuser so the GRANT is documentary; no key cleanup job (SQL given).
Done when: `make lint && make test` green; the local CI equivalent recorded in the status file (`uv run pre-commit run --all-files`, `uv run mypy src`, `uv run pytest -q`, and `.github/workflows/ci.yml` inspected to run exactly those); GitHub CI runs after the push is authorised (D-045); TC-38's three commands recorded in the status file; status file at `Status: awaiting-audit`. Commit: `SPEC-001 T13: CI on testcontainers, README API, demo and testing sections (design §3, §5)`.

**T20: Security posture and request bounds** (design §7, ADR-014, D-058)
Paths: `src/scheduler/interfaces/http/limits.py` (new: `BodySizeLimitMiddleware`, `MAX_BODY_BYTES`, `BodyTooLarge`), `errors.py` (413 handler), `schemas.py` (`max_length` on every free string), `main.py` (mount inside the wide-event middleware), `appointments.py` (413 in the OpenAPI responses), `tests/test_booking_api.py` (TC-40 only), `docs/adr/ADR-014.md`, `docs/adr/README.md`, `docs/design.md`, `README.md`.
The cap wraps `receive`: a declared `Content-Length` over the cap, or more bytes received than the cap, raises `BodyTooLarge` when the handler reads the body (ADR-008 step 1), so the 413 carries the route's wide event and never reaches the key store. HTTP layer only; no domain or application change.
Done when: TC-40 passes; `uv run pre-commit run --files <changed>`, `uv run mypy src`, `uv run pytest -q` green. Commits: `SPEC-001 T20: <what> (design §7, ADR-014)`.

### Scope Amendments

| Date | Approved by | Change | Reason |
|---|---|---|---|
| 2026-11-04 | JP (D-044) | TC-31/T11: race test uses its own fixture of 4 bays x 4 technicians; demo race expects 2 winners against the seed | Codex plan review: seed 2x2 cannot yield 4 concurrent winners |
| 2026-11-04 | JP (D-045) | T13 done-when: local CI equivalent recorded; GitHub CI after the authorised push | No-push rule during the overnight run |
| 2026-11-04 | orchestrator (Execution) | TC-38 heading check uses `grep -Ec '^## (API|Running the demo|Testing)$' README.md` (prints 3 on GNU and BSD grep); T13 paths gain `Makefile` (test target exports the testcontainers socket override) and the CI mypy step is `uv run mypy src tests/fakes.py` (AC-15 requires the fakes to type-check); T12 compose change includes `PYTHONUNBUFFERED=1` on `api` so event lines reach `docker compose logs` | T12/T13 verification findings |
| 2026-11-05 | JP (D-048) | UnitOfWork.serialise(dealership_id) after the claim; 40P01 keeps the pair; TC-01 deadlock clause and the Booking sequence updated | Race finding: deadlock detection latency and a false capacity_exhausted |
| 2026-11-05 | JP (D-049) | TC-31, AC-07, T11 block: the race synchronises the 8 clients before they send (`asyncio.Barrier` in the test, no attempt gate); AC-07 and the T11 example aligned with the D-044 fixture (4 bays x 4 technicians); TC-11 unchanged | D-048 audit cycle 2: an attempt gate inside the transaction deadlocks against the dealership lock taken before it |
| 2026-11-05 | JP (D-050) | AC-16, TC-39 added to T11: retry-fallback test where a writer bypasses the dealership lock from the attempt gate; the `AttemptGate` seam stays for this purpose. TC-31 `attempts` sum becomes `== 4` with zero attempts per loser (D-048 audit cycle 3 F-001, Execution) | Under D-048 the retry loop fires only for writers around the lock; the fallback needs evidence, and the old `>= 8` was unimplementable |
| 2026-11-05 | orchestrator (Execution, T14) | TC-39 row names the bypass bay and dealership of each case (bay 100 at dealership 100, bay 110 at dealership 110, as `tests/test_concurrency.py` uses); AC-16 listed after AC-15, numbering unchanged | Final coverage pass: the row said bay 100 for case (b) |
| 2026-11-05 | orchestrator (Execution, T15) | Docs only: every ADR, design.md and README walked claim by claim against the code and tests; Codex F-1..F-12 on ADR-004 fixed in the body (latency budget an SLO allocation, not enforced; `SELECT ... FOR UPDATE` rejected, not implemented; retry-fallback claims scoped to what TC-39 proves; pool limit a hypothesis); no decision, code or test changed | JP: one coherent body before the videos |
| 2026-11-05 | JP (D-058) | AC-17, TC-40 and task T20 added: request body cap (413) and `max_length` on every free string (schema 422); security posture recorded as ADR-014 and design §7 | Security was the unstated gap: the trust boundary was implied by "Authentication: upstream gateway" only |
| 2026-11-05 | orchestrator (Execution, T20) | AC-04 and the HTTP layer handler order name the 413 of AC-17 | Codex T20 cycle 1: the ADR-008 row and the handler sequence omitted the 413 |
| 2026-11-05 | orchestrator (Execution, T20) | Contract sources extend to ADR-014; T20 paths gain `appointments.py` (413 listed in the booking route's OpenAPI responses) | Codex T20 cycle 2: sources ended at ADR-013; `/openapi.json` omitted the 413 |
| 2026-11-05 | orchestrator (Execution, T20) | Wire-format code table names the 413; TC-40's "no key row" checks the row count | Codex T20 cycle 3 (fixed after the cap, not re-verified) |
