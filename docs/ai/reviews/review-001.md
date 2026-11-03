# Review 001: adversarial logic review

- Reviewer: a separate AI agent (Claude, Opus), findings only, no edits.
- Input: docs/design.md and the ADRs as drafted, read inside-out from ADR-004 and outside-in from the brief.
- Scenario classes hunted: time, DST and midnight; idempotency under concurrency; stale candidate lists; tenancy filters; availability as pairs versus counts; checks that live only in the application; replica routing; crash after commit.
- Result: 14 findings (1 critical, reproduced live; 6 major; 7 minor) and 3 suspected. Disposition by the author: all 14 adopted.

| # | Severity | Finding | Disposition | Where it landed |
|---|---|---|---|---|
| 1 | Critical | Simultaneous INSERTs on the same pair deadlock (40P01) instead of one getting 23P01; reproduced with 8 clients (9 deadlocks in 11 transactions, average 11.7 s). The spike's 50 ms stagger hid it | Adopted | 40P01 is a lost candidate, randomised candidate order, barrier-based test: design.md section 3; ADR-004 deadlock clause |
| 2 | Major | The retry loop retries pairs that share a lost resource, so five attempts burn on one lost bay | Adopted | Pruning by constraint name; 409 code decided on the pruned list: design.md section 3; ADR-004 pruning clause |
| 3 | Major | Availability output undefined; "reuses the candidate query" cannot hold over a window | Adopted, later refined by the multi-day decision | Per-pair start windows per local day: design.md section 3; ADR-010 |
| 4 | Major | `GET /appointments/{id}` not scoped by dealership; ids enumerable; unroutable after sharding | Adopted | `/dealerships/{id}/appointments/{appointment_id}`; authentication assumption: design.md sections 1 and 3 |
| 5 | Major | "Holds for any writer" overstated; empty ranges stack without limit | Adopted | `CHECK (end_at > start_at)`, `CHECK (duration_minutes > 0)`; claim narrowed to non-overlap and tenancy: design.md sections 1 and 2; ADR-004 |
| 6 | Major | Time input format and DST arithmetic unspecified | Adopted | Local wall time in the dealership zone, gap rejected, first occurrence for repeated times, `end_at` computed in UTC: design.md section 3; ADR-009 |
| 7 | Major | The same vehicle could be booked twice at once | Adopted, then superseded by review-002 M2 | Vehicle exclusion constraint, now over a NOT NULL `vehicle_key`: design.md section 2; ADR-004 |
| 8 | Minor | Isolation level unstated; the `ON CONFLICT` path needs READ COMMITTED | Adopted | design.md section 3; ADR-004, ADR-008 |
| 9 | Minor | Request-hash canonicalisation unspecified | Adopted | Canonical form rule: ADR-008 "Idempotency boundary" |
| 10 | Minor | "Read-your-own-writes" routing is unknowable across stateless instances | Adopted | Appointment reads always on the primary; replicas serve availability only: design.md section 4; ADR-004, ADR-010 |
| 11 | Minor | Past start times accepted | Adopted | 422 for a past start; 90-day horizon: ADR-009 |
| 12 | Minor | Opening-hours model limits unstated | Adopted | Same-day hours with CHECK; missing row means closed: ADR-009 |
| 13 | Minor | "Identifier" undefined; name or make alone passed | Adopted | Vehicle `id` or `vin`; customer `id` or `email`: design.md section 1; ADR-007 |
| 14 | Minor | The AI Collaboration Narrative must be a README section, not only `docs/ai/` | Adopted | README section "AI Collaboration Narrative", written in the implementation phase; links here |

Suspected items:

| Item | Disposition | Where it landed |
|---|---|---|
| Service type with zero required skills: qualifies all technicians or none, depending on query shape | Addressed in §1 | Any technician qualifies: design.md section 1 |
| No technician holds the required skill: recorded as a final 409 | Addressed in §1 | 422 configuration error, not 409: design.md section 1 |
| Missing assumptions: half-open ranges, no turnaround buffer, authentication out of scope | Addressed in §1 | design.md section 1 assumptions table; ADR-005 |

Traced OK by the reviewer: the three booking requirements; the six Part 1 sections; tenancy foreign keys with their UNIQUE targets; savepoints released; crash-after-commit replay; same key on two instances under READ COMMITTED; contention rollback; key scoping; `end == close` under half-open ranges; no scope creep against ADR-012.
