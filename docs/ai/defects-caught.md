# Defects caught

## Before code

Each row is a defect found in the design phase, before any application code existed, with what it changed.

| Defect | Caught by | Evidence path | Consequence |
|---|---|---|---|
| Vacuous pre-commit pass: `pre-commit run --all-files` on the fresh clone reported success while checking nothing, because untracked files are skipped | AI skeleton agent, on reading its own output | `docs/ai/verification-ledger.md` (V-000b) | Gates re-run after `git add -N`; a green check is read for what it checked |
| Barrier stall in the first spike scaffolding: a 5 s stall, caused by a barrier in the AI's own test code timing out while B was blocked inside INSERT and never reached it | AI, on reading the first trace | `docs/evidence/spike/race.py` (barrier removed), `docs/evidence/spike/race-output.txt` (corrected run) | The stall was scaffolding, not the mechanism; the trace cited in design.md is the corrected run |
| Savepoint gap: a failed INSERT aborts the PostgreSQL transaction, and the key claim shares that transaction, so retry-next-candidate would lose the claim | AI drafting agent, writing the design from the decision log | design.md section 3; `docs/evidence/spike/race_savepoint.py` | One `SAVEPOINT` per attempt; recovery proven live (V-001) |
| 40P01 deadlock hidden by the staggered spike: truly simultaneous INSERTs on the same pair deadlock instead of one getting 23P01 | AI adversarial review agent, reproduced live: 9 deadlocks in 11 transactions, average 11.7 s | `docs/ai/reviews/review-001.md` (finding 1); `docs/evidence/spike/race-savepoint-output-n8.txt` | 40P01 treated as a lost candidate; randomised candidate order; barrier-based concurrency test. Superseded in the implementation phase by D-048 (ADR-004 amendment): a 40P01 counts the attempt and keeps the pair, behind a per-dealership advisory lock |
| Idempotency boundary: an invalid body cannot be hashed, and the hash needs the dealership zone, which was read after the key claim | AI second-model review | `docs/ai/reviews/review-002.md` (M1); ADR-008 "Idempotency boundary" | Schema validation and dealership lookup move before the claim; their responses are never stored |
| Vehicle identity: a vehicle sent by `id` without a VIN escaped `no_vehicle_overlap`, and ADR-008 omitted `vehicle_already_booked` | AI second-model review | `docs/ai/reviews/review-002.md` (M2) | NOT NULL `vehicle_key`; constraint with no WHERE clause; final 409 `vehicle_already_booked` recorded and replayed |
| SLO not computable: the event's `outcome` could not tell a final 409 from a transient one, and booking-only fields were undefined on other routes | AI second-model review | `docs/ai/reviews/review-002.md` (M3); ADR-013 | Event gains `route`, `code`, `final`; SLI scoped to booking; every status classified |
| Latency versus deadlock timeout: five attempts at the default 1 s `deadlock_timeout` contradicted the 1,000 ms bound and the "immediate answer" wording | AI second-model review | `docs/ai/reviews/review-002.md` (M4); ADR-004 "Latency budget" | `SET LOCAL deadlock_timeout = '100ms'`, `statement_timeout` 2 s; latency budget table; a recovered race is good only inside the bound |

## In the implementation phase, caught by the author

Each row is a defect that passed the AI gates and was found by the author reading the output.

| Defect | Caught by | Evidence path | Consequence |
|---|---|---|---|
| Sizing written as given: design.md and ADR-004 stated 1,000 sites as if the brief had supplied it; the brief gives no count | Author, asking whether a service business has 1,000 sites; it had passed the adversarial review of the design | design.md section 4 and ADR-004 "Scale" (both now say "assumption") | Every number in the repository names its origin: the brief, a measurement, or an assumption |
| Amendment by annotation: the ADR-004 amendment for the per-dealership lock was appended while the latency table and four body passages still described deadlock-and-retry as the normal path; it passed eight audit cycles across four gates (the amendment audit, the coherence cross-check, the final gate and the T14 audit) | Author, reading one table: "has this been validated?" | `docs/ai/reviews/SPEC-001-adr-coherence-crosscheck.md`; ADR-004 | ADR-004 body rewritten; then a claim-by-claim walk of every ADR against the code: 51 corrections, cross-examined by the second model (L-005) |
| Latency budget failed by a correct design: the race test held the exact 4/4 split in 9 of 20 runs with deadlocks between writers and peaks of 1.2 to 1.4 s; the implementer proposed relaxing the test | Author, ruling on the implementer's escalation | `docs/ai/reviews/SPEC-001-D048-audit.md`; ADR-004 amendment; `docs/ai/specs/SPEC-001-status.md` | Test kept exact; per-dealership advisory lock after the key claim, retry kept as the fallback; 19 of 19 runs, zero deadlocks |
