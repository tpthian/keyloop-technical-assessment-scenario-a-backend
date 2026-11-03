# Review 002: independent second-model review

- Reviewer: Codex (a second model, high reasoning effort), findings only, no edits.
- Input: the brief, docs/design.md, the ADRs, the README, review-001 and both spikes. The reviewer was told what review-001 had found, so it hunted new ground.
- Result: 0 critical, 11 major, 8 minor, 3 suspected, 7 verified OK.
- Triage: the primary AI proposed a disposition per finding and concrete values for each fix; the author accepted the triage. Every number introduced by the fixes is the AI's proposal, accepted by the author, not a value given by the brief.

Dispositions: **adopted** (a design gap, fixed), **wording** (the design was right, the text was wrong or loose), **dismissed** (with the reason), **limitation** (stated, not fixed).

## Major

| # | Finding | Disposition | Where it landed |
|---|---|---|---|
| M1 | Idempotency boundary: an invalid body cannot be hashed or stored, and the hash needs the dealership zone, read only after the claim | Adopted | Order: parse, load dealership, validate schema, canonicalise and hash, claim, business validation. Pre-claim responses are never stored. design.md section 3 sequence diagram; ADR-008 order table and "Idempotency boundary" |
| M2 | Vehicle identity: a vehicle sent by `id` without a VIN escaped `no_vehicle_overlap`; ADR-008's final list omitted `vehicle_already_booked` | Adopted | NOT NULL `vehicle_key`; constraint with no WHERE clause; final 409 `vehicle_already_booked` recorded and replayed: design.md sections 2 and 3; ADR-004, ADR-007, ADR-008 |
| M3 | The event schema cannot compute the SLO: `outcome` cannot separate a final 409 from a transient one; booking-only fields undefined on other routes | Adopted | `route`, `code`, `final`; nullable booking-only fields; SLI scoped to booking with every status classified: ADR-013 |
| M4 | Latency: five attempts at the default 1 s `deadlock_timeout` contradict "immediate answer" and the 1,000 ms bound | Adopted | `SET LOCAL deadlock_timeout = '100ms'`, `statement_timeout` 2 s; latency budget table; a recovered race is good only inside the bound: design.md section 3; ADR-004 "Latency budget", ADR-008. Follow-up limitation: no request-level deadline or pool-size rule |
| M5 | Tenancy wording: reference tables carry no `dealership_id`; dealership service offerings unmodelled | Wording | `dealership_id` partitions every tenant table; `skill`, `service_type`, `service_type_required_skill` are global reference data; `technician_skill` follows its technician; service offering stated as a limitation: design.md sections 1 and 4; ADR-004 |
| M6 | Scale arithmetic labels bookings as writes; the peak is unsupported | Wording | Bookings/s, row writes/s, peak factor 30 with its assumption, rows per year: ADR-004 "Scale" |
| M7 | Replica `as_of` cannot make staleness visible if it is the response time | Adopted | `as_of` is a data watermark: `pg_last_xact_replay_timestamp()` on a replica, `now()` on the primary: design.md section 3; ADR-010 |
| M8 | The spike does not exercise the production retry policy (bound, pruning, ordering, outcome classes) | Dismissed | The spike proves a narrow claim by design: savepoint recovery from 23P01 and 40P01. The production-shaped test is V-002 ([../verification-ledger.md](../verification-ledger.md)) |
| M9 | Availability has an unbounded response surface | Adopted | At most 14 days per request, inside the 90-day horizon, else 422; result bounded by days x pairs: design.md section 3; ADR-010 |
| M10 | The README AI Collaboration Narrative is still empty | Dismissed | The narrative is an implementation-phase deliverable; the README section exists as a heading and the deliverables map says so |
| M11 | The overlap audit multiplies with instances and omits the vehicle | Adopted, then superseded | The background audit was later cut. The overlap query covers bay, technician and `vehicle_key` and runs only in the concurrency test and as the last line of `demo.sh`, so it never multiplies with instances: ADR-013 |

## Minor

| # | Finding | Disposition | Where it landed |
|---|---|---|---|
| 1 | Unknown dealership and unknown service type have no declared response | Adopted, through M1 | 404 for an unknown dealership before the claim, not stored; 422 for an unknown service type after the claim, stored: ADR-008 |
| 2 | An opaque client key can carry personal data into the logs | Adopted | The key must be a UUID, 400 otherwise: ADR-008, ADR-013 |
| 3 | "Elapsed wall-clock time" contradicts the UTC arithmetic | Wording | "Elapsed absolute duration"; "wall time" reserved for local input and the hours check: ADR-005, ADR-009 |
| 4 | Retiring a bay or technician is undefined | Limitation | Stated: bays and technicians are seeded and never deleted: design.md section 1 |
| 5 | ADR-004 had two stale internal references | Adopted | Section reference and both SQLSTATEs in the savepoint clause corrected: ADR-004 |
| 6 | The TL;DR omits outcomes and overstates determinism | Wording | All three 409 codes with final or transient class; `contention` named as timing-dependent: design.md TL;DR |
| 7 | 24-hour retention has no enforcing component | Wording | Retention is documented SQL run by the operator; replay window "until cleanup, at least 24 h": design.md sections 3 and 4; ADR-008 |
| 8 | "OpenTelemetry with zero code change" is not credible for child spans | Wording | Traces listed as needing instrumentation code: design.md section 5 |

## Suspected

| # | Finding | Disposition | Where it landed |
|---|---|---|---|
| 1 | Availability may diverge from booking across DST for multi-day services | Wording | Duration subtracted on UTC instants, then intersected with local hours; worked example with a DST change and a lagging replica: ADR-010 "Worked example" |
| 2 | Mapping every 40P01 to a lost resource may hide an unrelated lock cycle | Adopted | 40P01 caught only around the savepoint-wrapped INSERT; elsewhere a 5xx; counted in `deadlocks`: design.md section 3; ADR-004 |
| 3 | The reduced spike schema does not confirm the full production DDL | Dismissed | Same reason as M8: the spike proves the narrow claim; the migration-backed test (V-002) covers the full invariant set |

## Verified OK by the reviewer

The six Part 1 headings; crash behaviour at every point of the transaction boundary; savepoint recovery from both 23P01 and 40P01 (live trace); the DST and range-boundary policy; bay and technician tenancy foreign keys; zero-skill and cancellation semantics stated; read-after-write routing.

## Questions the design must answer, and where it answers them

| Question | Answer |
|---|---|
| Where exactly is the idempotency boundary, statement by statement, for every failure? | ADR-008, "Idempotency boundary" table |
| Why do five attempts meet the latency goal under the measured deadlock behaviour? | ADR-004, "Latency budget"; measured figure pending V-002 |
| Does one availability algorithm match booking semantics across DST, a closed day, back-to-back ranges and a lagging replica? | ADR-010, "Worked example" |
