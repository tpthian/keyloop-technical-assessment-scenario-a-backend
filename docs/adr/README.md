# Architecture Decision Records

Each record is short and cites, as D-nnn, the entry of the working decision log it comes from; the log itself stays outside the repository and each record restates its decision in full. Design document: [../design.md](../design.md).

Every D-nnn the repository cites is resolved in the decision register: [../decisions.md](../decisions.md).

| ADR | Title | Summary |
|---|---|---|
| [001](ADR-001.md) | Scenario and layer | Scenario A, backend only; client stubbed. |
| [002](ADR-002.md) | Technology stack | Python 3.12, FastAPI, PostgreSQL 16; portable. |
| [003](ADR-003.md) | Scheduler owns the resource calendars | The service that owns the invariant owns its data; zone and hours are a seeded local copy. |
| [004](ADR-004.md) | Booking guarantee | PostgreSQL exclusion constraints (bay, technician, NOT NULL `vehicle_key`); commit order arbitrates; per-dealership advisory lock after the key claim, so the normal path is at most one attempt (amendment, D-048); bounded next-candidate retry as the fallback for a writer outside the lock (D-050); on the attempt INSERT a 23P01 prunes the named resource and a 40P01 counts the attempt and keeps the pair; `deadlock_timeout` 100 ms; randomised order, savepoint per attempt; composite foreign keys for tenancy; non-overlap and tenancy hold for any writer; port isolates coupling. |
| [005](ADR-005.md) | Continuous time ranges | Start and end timestamps, not a slot grid; elapsed absolute duration added in UTC; half-open, no turnaround buffer; availability as per-pair start windows. |
| [006](ADR-006.md) | Qualification model | Single skill today, multi-skill-ready joins. |
| [007](ADR-007.md) | No synchronous CRM | Scheduler is an intake point; identifier is vehicle id or VIN, customer id or email; `vehicle_key` derived from it; CRM reconciles from an event. |
| [008](ADR-008.md) | Idempotency | Client-generated UUID key; 400, 413 (ADR-014), 404 and schema 422 before the claim, never stored; hash of the canonical request; READ COMMITTED; replay or 422 `replay_conflict`; final outcomes only (201, `capacity_exhausted`, `vehicle_already_booked`, business 422) versus transient `contention`. |
| [009](ADR-009.md) | Time zones and opening hours | UTC storage; local wall-time input in the dealership zone, gap rejected, `end_at` computed in UTC; same-day seeded hours, missing row means closed; only the start must fall in hours, `end_at` is unconstrained and `pickup_from` derived; past starts rejected. |
| [010](ADR-010.md) | Availability is advisory | Per-pair start windows (duration subtracted on UTC instants, then intersected with local opening hours), at most 14 days per request, stamped with `as_of` as a data watermark; booking is authoritative. |
| [011](ADR-011.md) | Quality gates | Pre-commit plus CI, enforced by the repository. |
| [012](ADR-012.md) | Scope and demonstration | No custom UI; Swagger UI, demo script, curl. |
| [013](ADR-013.md) | Observability | One wide JSON event per request on stdout, schema v1; SLI over booking events; no metrics endpoint, no background audit; the overlap query runs in the concurrency test and `demo.sh`. |
| [014](ADR-014.md) | Security posture and trust boundary | Three trust zones: the gateway (assumed) authenticates, rate-limits and caps volume; the service binds every SQL value, validates every body, caps the body at 16 KiB (413) and every free string, logs identifiers only and bounds the work per request; a future CRM stays outbound and off the booking path. Tenant binding of caller to dealership is the one stated gap, deferred. Not a penetration test. |
