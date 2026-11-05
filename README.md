# Unified Service Scheduler (Scenario A, backend)

Status: implemented; see Testing for the evidence.

## Quick start

Requires Docker (with Compose), [uv](https://docs.astral.sh/uv/) and `make`; uv installs Python 3.12 and the dependencies. The demo also needs `curl`, `jq` and `python3` on the host.

```bash
make install   # uv sync + install pre-commit hooks
make up        # start PostgreSQL 16 (docker compose, db only)
make migrate   # alembic upgrade head
make run       # uvicorn with --reload on :8000
make test      # pytest
make lint      # pre-commit run --all-files
make spike     # rerun the design-phase spikes against the compose database
make down      # stop the database
```

Copy `.env.example` to `.env` to override defaults.

## Deliverables map

Where each item the brief asks for lives in this repository.

| Brief | Required content | File |
|---|---|---|
| Part 1: System Design Document | Architecture diagram, component roles, data flow, technologies with justification, observability strategy, GenAI in the design phase | [docs/design.md](docs/design.md), sections 1 to 6 in that order, with a TL;DR on top, and section 7 on security. Decisions and rejected alternatives: [docs/adr/](docs/adr/README.md) (ADR-001 to ADR-014); decision register: [docs/decisions.md](docs/decisions.md) |
| Part 1, supporting: design evidence | Code that produced every spike trace cited in the design | [docs/evidence/spike/](docs/evidence/spike/): `schema.sql`, `race.py`, `race_savepoint.py` and their traces; rerun with `make spike` |
| Part 1, supporting: GenAI in the design phase | Pipeline, gates, reviews, verification ledger, defects caught | [docs/ai/README.md](docs/ai/README.md), [docs/ai/verification-ledger.md](docs/ai/verification-ledger.md), [docs/ai/defects-caught.md](docs/ai/defects-caught.md), [docs/ai/reviews/](docs/ai/reviews/review-001.md) |
| Part 2: Backend, API and data layer | Appointment booking API, availability check with no double booking under concurrency, multi-tenant data model | `src/scheduler/`, `migrations/`; API table in design.md section 3; Swagger UI at `/docs` when running |
| Part 2: README, build, run, test | How to build, run and test | This file: Quick start, Running the demo, Testing |
| Part 2: AI Collaboration Narrative | How AI was used in implementation, how its output was verified, what it got wrong | This file, section "AI Collaboration Narrative", in the author's voice; the evidence is in [docs/ai/](docs/ai/README.md) and [docs/ai/defects-caught.md](docs/ai/defects-caught.md) |
| Part 2: Tests validating core logic | Tests for the booking guarantee, retry, idempotency, time rules | `tests/`, run with `make test` |
| Part 3: Video | 5 to 10 minute walkthrough | Link in the submission email and at the top of this file once recorded |

## System design

Read [docs/design.md](docs/design.md) first. The TL;DR gives the whole design in a page; sections 1 to 6 follow the brief's list; section 7 states the security posture and its trust boundary. Each decision has an ADR in [docs/adr/](docs/adr/README.md) with the alternatives rejected.

## Design evidence

- `make spike` starts the compose database, creates a separate `spike` database on it and runs both spikes there; the spikes drop and recreate their own tables, so they never touch the application database.
- `race.py` reproduces the first race trace; `race_savepoint.py 8` reproduces savepoint recovery from 23P01 and 40P01.
- A `race_savepoint.py` run that sees no 40P01 exits 2 (inconclusive) and is repeated; 40P01 needs truly simultaneous inserts and does not occur on every run.

## API

Swagger UI at `http://localhost:8000/docs` when the service runs (`make run` or `make demo`). Design reference: [design.md section 3](docs/design.md), [ADR-008](docs/adr/ADR-008.md) for the idempotency boundary.

| Method and path | Purpose |
|---|---|
| `POST /dealerships/{dealership_id}/appointments` | Book an appointment; header `Idempotency-Key` required |
| `GET /dealerships/{dealership_id}/appointments/{appointment_id}` | Read one appointment of that dealership |
| `GET /dealerships/{dealership_id}/availability?service_type_id=&from=&to=` | Advisory start windows per bay and technician over `[from, to)`, at most 14 days, inside the 90-day horizon, with an `as_of` watermark |
| `GET /health/live` | 200 `{"status": "ok"}` while the process runs |
| `GET /health/ready` | 200 `{"status": "ok"}` with the database, 503 `{"status": "unavailable"}` without |

`Idempotency-Key` rule:

- The header is a UUID; missing or not a UUID is 400 `validation`. Keys are scoped to the dealership.
- Malformed JSON (400), a body over 16 KiB (413, ADR-014), unknown dealership (404) and schema errors (422 with `errors`) are answered before the transaction and never stored, so a corrected body may reuse the key.
- 201, business 422 and the final 409s (`capacity_exhausted`, `vehicle_already_booked`) are stored with the key and replayed with the same status and body for the same key and body, until cleanup and at least 24 h.
- The same key with a different body is 422 `replay_conflict`; the original outcome stays.
- `contention` (409, `Retry-After: 1`) and 500 discard the claim, so a retry with the same key runs again.

Request, `start_at` in the dealership's local wall time, whole minutes, no offset; unknown fields are a 422; `customer` needs `id` or `email`, `vehicle` needs `id` or `vin`; the VIN is normalised to upper case without whitespace:

```json
{
  "service_type_id": 1,
  "start_at": "2027-03-26T09:00:00",
  "customer": {"id": "C-42", "email": null, "name": "Sam Lee"},
  "vehicle": {"id": null, "vin": "WVWZZZ1JZXW000001", "make": "VW", "model": "Golf"}
}
```

The example dates are illustrative; a booking must start in the future and within 90 days. The same request with `start_at` set to next Monday 09:00, against the seeded dealership 1:

```bash
START="$(python3 -c 'import datetime as d; t = d.date.today(); print(t + d.timedelta(days=7 - t.weekday()))')T09:00:00"
curl -s -w '\nHTTP %{http_code}\n' -X POST http://localhost:8000/dealerships/1/appointments \
  -H "Idempotency-Key: $(python3 -c 'import uuid; print(uuid.uuid4())')" \
  -H 'Content-Type: application/json' \
  -d '{"service_type_id": 1, "start_at": "'"$START"'",
       "customer": {"id": "C-42", "email": null, "name": "Sam Lee"},
       "vehicle": {"id": null, "vin": "WVWZZZ1JZXW000001", "make": "VW", "model": "Golf"}}'
```

On a fresh database (`make up && make migrate && make run`) this prints the body below and `HTTP 201`. Sent again with a new key, or after `make demo` (whose section 2 books the same car at the same time), it prints 409 `vehicle_already_booked`; change the VIN or the hour to book again.

Response 201, also the body of `GET .../appointments/{appointment_id}`; instants in UTC; `pickup_from` is `end_at` when that falls inside opening hours, else the next opening instant:

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

Every non-2xx response has the body `{"code": "<code>", "message": "<text>", "errors": [...]}`; `errors` appears only on a schema 422 and holds `{"loc": [...], "msg": "...", "type": "..."}` items.

| Code | Status | Final | Stored with the key |
|---|---|---|---|
| `confirmed` | 201 | yes | yes |
| `validation` (schema, before the transaction) | 400 malformed JSON or key; 413 body over 16 KiB (ADR-014); 422 schema | yes | no |
| `not_found` | 404 | yes | no |
| `validation` (business: hours, past, horizon, DST gap, service type, qualification) | 422 | yes | yes |
| `replay_conflict` | 422 | yes | no (the original row stays) |
| `capacity_exhausted` | 409 | yes | yes |
| `vehicle_already_booked` | 409 | yes | yes |
| `contention` | 409, header `Retry-After: 1` | no | no (claim rolled back) |
| `error` | 500 | no | no |

## Running the demo

Requires Docker, `curl`, `jq` and `python3` on the host.

```bash
make demo              # docker compose up db and api (api migrates on start), then scripts/demo.sh
make down && make demo # clean rerun on a fresh database
```

`scripts/demo.sh` runs eight sections against seeded dealership 1 (Riverside Motors, `Europe/London`, Mon-Sat 08:00-18:00, 2 bays x 2 technicians), with dates computed from today:

1. Health: `/health/live` and `/health/ready`.
2. Book an Oil change next Monday at 09:00 local: 201.
3. Replay with the same key and body: 201, same `appointment_id`, no second booking.
4. Same key, different body: 422 `replay_conflict`.
5. Same car (VIN sent in lower case with a space), new key, overlapping 09:30: 409 `vehicle_already_booked`.
6. Availability for the Oil change on that Monday: windows per pair and `as_of`.
7. The race: 8 concurrent clients book one slot on the Monday after. Two bays and two technicians allow two winners, so the expected split is 2 x 201 and 6 x 409 `capacity_exhausted`; one line per client, then the last 8 `book_appointment` events from `docker compose logs api`, one summary line each (outcome, code, attempts, deadlocks, pruned candidates, latency) and one event printed in full (ADR-013).
8. The overlap query of design section 5, printed last.

The last printed line is the overlap count and must be `0`. Each response is written to its own file under a temporary directory whose path is printed first. The script stops with a message when a response differs from the expected one, and refuses to run against a database that already holds appointments; `make down && make demo` starts clean.

## Testing

```bash
make test   # uv run pytest -q; Docker required
```

The tests start their own PostgreSQL 16 container with testcontainers (ADR-002) and migrate it with `alembic upgrade head`, as `make migrate` does; no compose database is needed. With colima or Docker Desktop, testcontainers needs the in-VM socket path for its reaper container: `make test` sets `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock`; when running `uv run pytest` directly, export it first. CI runs `uv run pre-commit run --all-files`, `uv run mypy src tests/fakes.py` (the fakes checked against the Protocols) and `uv run pytest -q` on the runner's Docker, with no database service.

| Test file | Layer | Proves |
|---|---|---|
| `tests/test_architecture.py` | all | The layer rule: `domain` imports only the standard library, `application` only `domain`, `infrastructure` and `interfaces` never import each other, only `main` imports both |
| `tests/test_time_rules.py` | domain | Local to UTC with the DST gap rejected and the first occurrence of a repeated time; start inside hours; `end_at` of a 4,320-minute service across the DST change; `pickup_from` over closed days |
| `tests/test_canonical.py` | domain | The request hash ignores key order, whitespace, null fields and VIN spacing, and uses the UTC instant |
| `tests/test_attempts.py` | domain | Pruning by constraint name, 40P01 prunes nothing and the same pair is retried within the bound of 5, the bound gives `contention`, an empty list gives `capacity_exhausted` |
| `tests/test_windows.py` | domain | Busy ranges merged, free gaps, duration subtracted on UTC instants, closing bound `closes - 1 min` |
| `tests/test_book_appointment_usecase.py` | application | The booking use case on in-memory fakes: replay, `replay_conflict`, business 422 recorded, scripted reserve outcomes, `contention` rolled back with nothing recorded, the dealership lock taken after the claim and never on a replay |
| `tests/test_postgres_adapters.py` | infrastructure | `reserve` maps 23P01 to `ResourceTaken` and the transaction continues after the savepoint, and re-raises any other error; `claim`, `record`, `free_candidates`; `serialise` holds the dealership's advisory lock until COMMIT |
| `tests/test_seed.py` | infrastructure | The seed and the nine named constraints, `btree_gist` installed |
| `tests/test_booking_api.py` | interfaces | 201 body, business 422s, `vehicle_already_booked`, `capacity_exhausted`, tenancy foreign keys, `GET` by id, back-to-back slots, request bounds (413 over the body cap, 422 on an over-long string; TC-40) |
| `tests/test_idempotency.py` | interfaces | The ADR-008 boundary rows before and at the claim: 400 malformed JSON or key, 404, schema 422 with no key row and a corrected body under the same key, business 422 replayed or `replay_conflict`, 201 replayed with one appointment, and the order 400, 404, then schema 422. The concurrent same-key row is TC-20, the final-409 replay is TC-22, the attempt and `contention` rows are TC-01, TC-11, TC-12 and TC-39; crash points and 5xx are not tested |
| `tests/test_availability.py` | interfaces | Window limits, the ADR-010 worked example, an empty schedule |
| `tests/test_events.py` | interfaces | One wide event per response, 17 keys in order, `final` classification, no email or VIN in any line |
| `tests/test_health.py` | interfaces | `/health/live` 200; `/health/ready` 200, and 503 with an unreachable database |
| `tests/test_concurrency.py` | full stack | V-002: 8 clients released together by a barrier against 4 bays x 4 technicians yield 4 x 201 and 4 x `capacity_exhausted`, distinct winners, 0 overlaps (TC-31); a parallel same-key pair yields one appointment (TC-20); a booking that loses a bay to a writer bypassing the dealership lock prunes it by the constraint name and lands on the remaining free bay, or gets `capacity_exhausted` when none is left (retry fallback, TC-39) |

The race test alone, with its summary line:

```bash
TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest tests/test_concurrency.py -q -s
```

```text
V-002: 8 clients, 4 pairs, statuses={201: 4, 409: 4}, attempts=4, deadlocks=0, candidates_pruned=0, max latency_ms=126, wall=129 ms, overlaps=0
```

The race asserts the invariant, never a particular SQLSTATE: the test accepts any mix of 23P01 and 40P01 and checks the winner count and the overlap count (L-001). Since bookings of one dealership are serialised behind an advisory lock (ADR-004 amendment), no 40P01 is expected: each booking reads the pairs already committed, so a loser finds none free and gets `capacity_exhausted` with zero attempts; the next-candidate retry runs only for a writer that bypasses the lock (TC-39, L-005).

Known limitations:

- Bookings of one dealership are serialised by a transaction-scoped advisory lock taken after the idempotency-key claim (ADR-004 amendment). Before the lock, the exact race split on 4 bays x 4 technicians held in 9 of 20 runs, and races on the seed shape of 2 x 2 saw up to 13 deadlocks with peaks of 1.2 to 1.4 s; with it, the split held in all 19 recorded runs (3 + 10 + 6), with 0 deadlocks and peaks of 108 to 126 ms in the 13 runs whose figures were kept. Bookings are taken in the order they reach the lock, not click order, and no user-visible ordering guarantee is made; bookings of different dealerships stay parallel; the next-candidate retry remains the fallback for writers outside the lock (TC-39). Hypothesis, not load-tested: under mass concurrency the throughput limit is the connection pool (10 plus 10 overflow per instance), not the lock.
- No request-level deadline: the latency budget of ADR-004 is an SLO allocation, not enforced; a booking waiting on the dealership lock is bounded only by the 2 s `statement_timeout` of the lock statement, which ends it as a 500.
- `statement_timeout` (2 s) bounds one statement, not the request.
- A vehicle booked once by VIN and once by vehicle `id` gets two `vehicle_key` values, so `no_vehicle_overlap` does not catch that overlap (ADR-007).
- Opening hours and the seed change by migration only; there is no admin API (ADR-009, ADR-012).
- The compose and CI database role is a superuser, so `SET LOCAL deadlock_timeout` works without the migration's `GRANT SET ON PARAMETER deadlock_timeout`; the GRANT documents what a production application role needs.
- No key cleanup job. Stored keys replay until removed; the operator runs:

  ```sql
  DELETE FROM idempotency_key WHERE created_at < now() - interval '24 hours';
  ```

## AI Collaboration Narrative

This section is written in the author's voice; the rest of the repository is written as an instruction book. Design-phase procedure and evidence: [docs/ai/README.md](docs/ai/README.md).

**How I directed the work**

- I owned the problem. I read the brief, chose the backend scenario, and cut it to the one hard thing: no double booking of a bay, a technician or a vehicle under concurrency. I wrote the service model on paper first: dealership, bays, technicians, appointments as time ranges.
- The AI's job was to challenge that sketch, not to replace it. Every challenge had to carry a measurement or a source. I decided every item that touched the contract or the code; every outcome is a numbered decision that names its origin: the brief, me, or AI-proposed and accepted by me. more than fifty decisions over three days, each registered in the repository.
- My first answer to double booking was a queue or an application-level check. The AI countered with PostgreSQL exclusion constraints and I made it prove the claim before I adopted it: a spike against a real database. The first spike hid the problem by staggering clients 50 ms apart. The adversarial review of that spike reproduced deadlocks in 9 of 11 transactions. The second spike, eight simultaneous writers with a savepoint per attempt, recovered from both failure modes with zero overlaps. That is the design we built.
- Architecture, layer rules and code principles were fixed before the first line of code, and a test enforces the layer rule on every commit.

**The loop, once the design stood**

- A SPEC in two parts: a Contract I gate, an Execution section the agents may revise. 16 acceptance criteria, 39 test cases when the loop closed.
- An adversarial review of the SPEC by a second AI, three cycles, before I approved it.
- Fifteen implementation tasks, each in an isolated branch, each followed by a read-only audit from the second AI. Tests are exactly the SPEC test cases; the auditor never writes tests. Cap of three audit cycles, then it stops and comes to me.
- Nine of the fifteen passed first time, three took two cycles, two took three, one took four by my exception. 43 audit and review runs in total when the loop closed, every final verdict a pass. 109 tests.
- Anything that touched the contract or the business logic came to me. I read, ruled, revised, and redesigned where the evidence demanded it.
- After the code: two coherence walks of the design document and every ADR against the code, with the second AI cross-examining the walker, then a handful of small documentation commits under the gates alone. The documents describe the code that runs. On the last day two more tasks went through the same loop, each with its own audit: the security posture (ADR-014, one more acceptance criterion and one more test, so 17, 40 and 110 today) and a register of every decision the repository cites.

**Where my judgement changed the outcome**

- The race test proved correctness but failed the latency budget: the split held in 9 of 20 runs, deadlocks between writers, peaks of 1.2 to 1.4 seconds. The implementer offered to relax the test. I kept the test exact and ruled for a per-dealership advisory lock after the idempotency claim, with the retry kept as the fallback for writers outside the lock. Since then: 19 of 19 runs, zero deadlocks, about 110 to 150 ms.
- An ADR had its change appended as an amendment while the body still described the old model. It passed eight AI audit cycles across four gates. I caught it from one table and asked "has this been validated?". That became a claim-by-claim walk of every ADR against the code: 51 corrections.
- The AI once wrote a 1,000-site scale figure as if the brief had given it. I made it say so. Numbers in this repository say where they come from.
- The AI proposed a 90-day booking horizon the brief never asked for. I kept it, and made the ADR say what it is: an operational assumption standing in for published roster depth, with the rule that will replace it.
- On the last day I raised security as the gap nobody had asked about. I had it written down as a trust boundary, with its one open hole, tenant binding, named rather than left implied.

**Rules that bounded the agents**

- No agent pushes. Every commit names its task, design section and ADR. Merges are never squashed, so the audit trail is the history.
- Every decision, defect and lesson is logged with who found it. The repository cites lessons by id; the raw record stays with me.
- Evidence over narration. The verification ledger, the defects-caught register and the audit reports are in [docs/ai/](docs/ai/README.md), so the process is visible as a system rather than told as a story.

**What I learned**

- The AI's value was speed and breadth in measurement, implementation and audit, and a good counter-proposal when mine was weaker. Mine was knowing what the hard thing was, holding a test exact when it was inconvenient, reading the evidence, and spotting the one document that no audit re-read.

## Quality gates

pre-commit (ruff format and lint, mypy on the application package, gitleaks, whitespace and end-of-file fixers) runs locally; GitHub Actions runs the same configuration plus pytest on every push (ADR-011).
