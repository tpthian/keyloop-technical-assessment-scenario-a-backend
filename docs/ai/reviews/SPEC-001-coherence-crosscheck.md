# SPEC-001 coherence cross-check

Head-SHA: `ca609d908dc929f5205b2c8b23944b821faea5b7`
Reader: Codex, read-only
Inputs: README.md; docs/design.md; docs/adr/ADR-004.md; docs/adr/ADR-008.md; docs/adr/ADR-012.md; docs/adr/ADR-013.md; docs/ai/specs/SPEC-001-booking-service.md; docs/ai/specs/SPEC-001-status.md; docs/ai/lessons.md; tests/test_concurrency.py; tests/conftest.py; src/scheduler/application/book_appointment.py; src/scheduler/infrastructure/postgres/unit_of_work.py; src/scheduler/infrastructure/postgres/repositories.py; src/scheduler/infrastructure/postgres/engine.py; src/scheduler/domain/attempts.py; src/scheduler/main.py

## Claims checked

- C-1: `README.md:124,132` — the demo race uses seeded dealership 1 with 2 bays × 2 technicians and therefore expects 2 × 201 plus 6 × 409 — true — seed shape and fresh-demo evidence agree.
- C-2: `README.md:160` — TC-31 uses a barrier and a 4-bay × 4-technician test fixture, yielding 4 × 201 and 4 × 409 — true — `tests/test_concurrency.py:95-125` creates that fixture and asserts the split.
- C-3: `README.md:169` — the displayed V-002 line has 4 winners, 4 losers, 4 attempts, 0 deadlocks/pruning/overlaps, max latency 126 ms and 129 ms wall time — true — verbatim recorded evidence supplied.
- C-4: `README.md:172` — normal locked bookings yield zero-attempt `capacity_exhausted` losers; retry is for writers bypassing the lock — true — `book_appointment.py:78-105`, `test_concurrency.py:135-137`, and TC-39 support this.
- C-5: `README.md:176` — the pre-lock 4×4 split held in 9/20 runs; the 2×2 control saw up to 13 deadlocks and 1.2–1.4 s peaks — true — supplied T11 evidence.
- C-6: `README.md:176` — after the lock, all 19 recorded runs were green with 0 deadlocks; retained figures were 108–126 ms — true — supplied T11-v2 evidence.
- C-7: `README.md:176` — lock order is not click order and no user-visible ordering guarantee exists — true — no code path exposes an ordering guarantee.
- C-8: `README.md:176` — different dealerships stay parallel — true — `UnitOfWork.serialise` keys the advisory lock by `dealership_id`.
- C-9: `README.md:176` — the pool is the expected mass-concurrency limit rather than the lock — unsupported — engine capacity is demonstrably 10 pooled plus 10 overflow connections, but the document correctly labels the throughput conclusion as a non-load-tested sizing expectation.
- C-10: `README.md:177` — no request-level deadline exists; the latency budget bounds deadlock waits only — true — `statement_timeout` is per statement and no request deadline is configured.
- C-11: `docs/design.md:7,13` — constraints are the invariant, the advisory lock is the normal deterministic path, and bounded retry is the bypass-writer fallback — true — matches D-048/D-050 and `attempts.py`.
- C-12: `docs/design.md:49-52` — candidates are shuffled; reserve maps only INSERT-local 23P01/40P01; booking retries at most five times — true — `attempts.py:32,62-104` and `repositories.py:261-274`.
- C-13: `docs/design.md:115-131` — claim precedes transaction-scoped advisory locking; 40P01 retains the pair; contention rolls back the claim — true — `book_appointment.py:71-78`, `unit_of_work.py:62-71`, and `attempts.py:96-103`.
- C-14: `docs/design.md:136` — savepoint recovery trace contains 24 × 23P01, 4 × 40P01, and zero overlaps — true — `docs/evidence/spike/race-savepoint-output-n8.txt:69-71`.
- C-15: `docs/design.md:137-139` — normal lock-honouring requests do not form attempt-path cycles; an unexpected 40P01 is counted without pruning; five 100 ms waits are about 500 ms — true — code and D-048 agree.
- C-16: `docs/design.md:137` — TC-39 proves a bypass writer can cost one attempt per lost resource and still land on a free pair or cleanly exhaust capacity — true — `tests/test_concurrency.py:183-225`.
- C-17: `docs/design.md:162` — the advisory lock is a PostgreSQL lock valid across instances, not the rejected application-level-lock alternative — true — PostgreSQL transaction-scoped advisory lock is issued by `unit_of_work.py:69-71`.
- C-18: `docs/adr/ADR-004.md:13,21` — named 23P01 conflicts prune named resources, 40P01 counts but prunes nothing, and the bound remains five — true — `attempts.py:67-104`.
- C-19: `docs/adr/ADR-004.md:15,17-18` — the booking transaction sets 100 ms `deadlock_timeout`, 2 s `statement_timeout`, and has no request-level deadline — true — `unit_of_work.py:23-47`.
- C-20: `docs/adr/ADR-004.md:44-52` — five deadlock waits are budgeted at about 500 ms; V-002 retained figures are 108–126 ms across 13 measured runs — true — arithmetic and supplied evidence agree.
- C-21: `docs/adr/ADR-004.md:98-101` — pre-D-048 race findings include 12–13 deadlocks, 1.2–1.4 s peaks, and 5/20 false-capacity results on 2×2 — true — supplied evidence agrees.
- C-22: `docs/adr/ADR-004.md:103` — lock acquisition happens only after a new claim, before validation/attempts; replay paths do not wait; 40P01 retains its pair — true — `book_appointment.py:71-79`.
- C-23: `docs/adr/ADR-004.md:107-114` — lock-honouring booking requests serialize, while bypass writers remain constraint-protected and activate retry fallback — true — the latter is directly exercised by TC-39.
- C-24: `docs/adr/ADR-004.md:116` — PostgreSQL queue arrival is not click order and no user-visible fairness guarantee is made — true — no application-level ordering contract exists.
- C-25: `docs/adr/ADR-004.md:116` — V-002 completes eight queued bookings in about 130 ms wall time — true — the retained 129 ms V-002 line supports the qualified “about” claim.
- C-26: `docs/adr/ADR-004.md:116` — each instance has at most 10 pooled plus 10 overflow connections — true — `engine.py:8-10`.
- C-27: `docs/adr/ADR-004.md:116` — pool saturation is the expected cross-dealership throughput limit — unsupported — explicitly disclosed as a sizing expectation rather than measured result.
- C-28: `docs/adr/ADR-008.md:19-22,29` — advisory locking occurs only after a new claim and 40P01 preserves candidates — true — code sequence matches.
- C-29: `docs/adr/ADR-008.md:37,53-60` — 40P01 is unexpected on the normal path, and failures outside the attempt INSERT are 5xx — true — `repositories.py:266-273` catches SQLSTATE only around `reserve`.
- C-30: `docs/adr/ADR-012.md:9` — the demo includes a two-concurrent-bookings race — true — `scripts/demo.sh` performs the seeded 8-client race, whose expected result is two winners.
- C-31: `docs/adr/ADR-013.md:31-37,41-52` — events carry attempts/deadlocks/pruning/latency and classify outcomes against a 1,000 ms SLI — true — event tests and ADR definitions agree.
- C-32: `docs/ai/specs/SPEC-001-booking-service.md:98,205,252` — D-044 supersedes the old seed race: TC-31 is test-owned 4×4, while seed/demo is 2×2 — true — SPEC, README, and test fixture agree.
- C-33: `docs/ai/specs/SPEC-001-booking-service.md:213,253` — AC-16/TC-39 uses a separately committed `engine.begin()` bypass transaction, not an autocommit connection — true — `tests/test_concurrency.py:165-168`.
- C-34: `docs/ai/specs/SPEC-001-booking-service.md:287-299` — AC/TC traceability includes AC-10 → TC-31/32 and AC-16 → TC-39 — true — the cycle-1 corrections are present.
- C-35: `repository text` — documentation cites lesson identifiers only as `L-nnn`, never `ERR-`/`LSN-` — true — repository-wide `rg` excluding `.git` and `.venv` returned no matches.

## AC -> TC -> test

- AC-01 — TC-34 — `tests/test_seed.py::{test_btree_gist_installed,test_nine_named_constraints_exist,test_seed_two_dealerships,test_seed_three_service_types_one_of_4320_minutes,test_seed_dealership_1_has_two_bays_and_two_technicians,test_seed_both_hold_general_only_technician_1_holds_bodywork}` — pass — functions assert the TC-34 extension, constraints, and seed clauses.
- AC-02 — TC-13,25,26,27 — `tests/test_postgres_adapters.py::test_claim_record_and_free_candidates`; `tests/test_booking_api.py::{test_get_appointment_returns_the_201_body,test_back_to_back_on_one_pair_both_201,test_happy_path_201_body_end_at_and_pickup_from,test_vehicle_key_is_id_prefixed_when_only_id_given}` — pass — assertions match the rows.
- AC-03 — TC-01,02,11,12,22,23 — `tests/test_attempts.py::test_tc01_*`, `tests/test_attempts.py::test_tc02_*`, `tests/test_book_appointment_usecase.py::{test_confirmed_is_recorded,test_capacity_exhausted_is_recorded,test_vehicle_already_booked_is_recorded,test_contention_rolls_back_and_records_nothing}`, `tests/test_postgres_adapters.py::test_reserve_confirms_free_pair_and_loses_to_named_constraints`, `tests/test_booking_api.py::{test_same_vin_overlapping_is_409_stored_and_replayed,test_every_pair_busy_is_capacity_exhausted_with_zero_attempts}` — pass — all listed outcomes are asserted.
- AC-04 — TC-07,09,11,13,15–20,37 — `tests/test_canonical.py::test_tc07_*`; `tests/test_book_appointment_usecase.py::{test_claim_with_other_hash_raises_replay_conflict,test_claim_with_same_hash_replays_without_attempt,test_contention_rolls_back_and_records_nothing}`; `tests/test_postgres_adapters.py::test_claim_record_and_free_candidates`; `tests/test_idempotency.py::test_*`; `tests/test_concurrency.py::test_parallel_same_key_same_body_books_once` — pass — assertions match the idempotency rows.
- AC-05 — TC-03–06,10,18,21 — `tests/test_time_rules.py::test_tc03_*` through `test_tc06_*`; `tests/test_book_appointment_usecase.py::test_{unknown_service_type,gap_time,past_start,start_beyond_horizon,start_outside_hours}_is_validation_recorded`; `tests/test_idempotency.py::test_business_422_replays_for_same_body`; `tests/test_booking_api.py::test_*_is_stored_422` — pass — time and persistence assertions match.
- AC-06 — TC-08,28,29,30 — `tests/test_windows.py::{test_merge_of_overlapping_busy_ranges,test_free_gaps,test_duration_subtracted_on_utc_before_intersecting_local_day,test_closing_bound_closes_minus_one_minute}`; `tests/test_availability.py::test_*` — pass — expected windows and validation are asserted.
- AC-07 — TC-20,31 — `tests/test_concurrency.py::{test_parallel_same_key_same_body_books_once,test_v002_race_eight_clients_four_pairs}` — pass — TC-31 has the 4×4 fixture, client barrier, exact status split, distinct winners, committed keys, and zero overlaps.
- AC-08 — TC-10,21,23,24 — `tests/test_book_appointment_usecase.py::test_no_qualified_technician_is_validation_recorded`; `tests/test_booking_api.py::{test_no_qualified_technician_is_stored_422,test_dealership_without_bays_is_capacity_exhausted,test_other_dealerships_bay_violates_bay_in_dealership,test_other_dealerships_technician_violates_technician_in_dealership}` — pass — assertions match.
- AC-09 — TC-33 — `tests/test_health.py::{test_live_is_200_without_a_database,test_ready_is_200_with_the_database,test_ready_is_503_with_an_engine_on_a_closed_port}` — pass — assertions match.
- AC-10 — TC-31,32 — `tests/test_concurrency.py::test_v002_race_eight_clients_four_pairs`; `tests/test_events.py::test_*` — pass — TC-31 asserts race event attempts; TC-32 asserts event schema/privacy requirements.
- AC-11 — TC-35 — `scripts/demo.sh::top-level` — pass — intentionally manual script target; supplied fresh evidence reports exit 0 and final line `0`.
- AC-12 — TC-36 — recorded command `make lint && make test` — pass — intentionally manual gate; supplied merged-T11 evidence reports `uv run pytest -q` → 109 passed.
- AC-13 — TC-38 — `README.md::inspection commands` — pass — intentionally manual repository inspection, recorded in the status file.
- AC-14 — TC-14 — `tests/test_architecture.py::{test_layer_dependency_rule,test_only_main_imports_both_outer_layers,test_rules_catch_violations}` — pass — assertions match.
- AC-15 — TC-09,10,11 — `tests/test_book_appointment_usecase.py::{test_dealership_arrives_as_argument_and_is_never_looked_up,test_claim_with_other_hash_raises_replay_conflict,test_claim_with_same_hash_replays_without_attempt,test_*_is_validation_recorded,test_confirmed_is_recorded,test_capacity_exhausted_is_recorded,test_vehicle_already_booked_is_recorded,test_contention_rolls_back_and_records_nothing,test_attempt_gate_awaited_once_before_first_reserve,test_serialise_after_claim_before_any_reserve_and_never_on_replay}` — pass — fake-based use-case assertions match.
- AC-16 — TC-39 — `tests/test_concurrency.py::test_retry_fallback_when_a_writer_bypasses_the_lock` — pass — both free-pair and exhausted-pair bypass cases, counters, zero deadlocks, zero overlap, and three rows are asserted.

## Findings

- F-1 [low]: `src/scheduler/application/book_appointment.py:64` — “`test seam for the barrier race (TC-31)`” — TC-31 now uses a client-side `asyncio.Barrier` and injects no attempt gate; the seam is used by TC-39 — replace with “`test seam for a writer that bypasses the dealership lock (TC-39); None in production`”. src, out of this leg's paths.
- F-2 [low]: `src/scheduler/application/book_appointment.py:104` — “`test seam: first INSERTs leave together`” — D-049 removed the in-transaction attempt barrier because it deadlocks behind the advisory lock; the gate now commits a bypass writer before the booking’s first reserve — replace with “`test seam: writer bypasses the dealership lock (TC-39, D-050)`”. src, out of this leg's paths.
- F-3 [low]: `src/scheduler/main.py:49` — “`test seam for the barrier race`” — this injection is for TC-39’s bypass writer, not TC-31’s client barrier — replace with “`test seam for the bypass-writer fallback test (TC-39); None in production`”. src, out of this leg's paths.

Verdict: pass

Cycles: 2. Cycle 1 verdict revise (F-1..F-5 on ADR-004, README and the TC-39 row; F-6..F-8 stale src comments), fixed in the commit "coherence fixes cycle 1"; cycle 2 above.
