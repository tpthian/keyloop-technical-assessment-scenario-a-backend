# SPEC-001 T15: ADR coherence cross-check (Codex)

Adversarial read of `docs/adr/*.md`, `docs/design.md`, `README.md` and `docs/ai/specs/SPEC-001-booking-service.md` against `src/**` and `tests/**`, by Codex (`codex exec -s read-only`), after the T15 walk (C1 033f657, C2 077a6d1, C3 e2d099b, C4 c13951f). Codex had no Docker; the gate results (pytest 109 passed, mypy, pre-commit) are the orchestrating session's.

Cycles: 3 of a maximum of 3. Final verdict: revise. Cycle 1 F-1..F-10, cycle 2 F-11..F-13, cycle 3 F-14. Dispositions:

| Finding | Disposition | Commit |
|---|---|---|
| F-1 `docs/ai/reviews/review-001.md:10` | Rejected: dated verbatim review record, not rewritten; supersession recorded in V-000c, defects-caught and ADR-004 | |
| F-2, F-3, F-4, F-6, F-8, F-9, F-10 | Fixed | 4ecb8f0 |
| F-5 SPEC TC-31 text, F-7 SPEC:268 | Rejected: true as written (the test accepts any SQLSTATE mix, L-001); F-7 restates L-002, now scoped | |
| F-11 `src/scheduler/application/ports.py:91` | Out of scope (docs only); reported to the author | |
| F-12, F-13 | Fixed | b69d8ad |
| F-14 `README.md:160` | Fixed after the last cycle; not re-verified by Codex | 6b72d6d |

## Cycle 1 output (verbatim)

```text
Verdict: revise
F-1 — `docs/ai/reviews/review-001.md:10` — "40P01 is a lost candidate, randomised candidate order, barrier-based test" — Mark this historical disposition superseded by D-048: 40P01 counts an attempt but keeps the pair.
F-2 — `docs/ai/verification-ledger.md:9` — "Design changed: 40P01 is a lost candidate; candidate order randomised; barrier-based concurrency test" — Record D-048’s supersession and state that 40P01 keeps the candidate.
F-3 — `docs/ai/defects-caught.md:10` — "40P01 treated as a lost candidate; randomised candidate order; barrier-based concurrency test" — Mark the lost-candidate policy superseded by D-048 and describe the keep-the-pair policy.
F-4 — `docs/ai/README.md:41` — "Exclusion constraints; FIFO, application lock and `SELECT ... FOR UPDATE` rejected, the last kept as fallback adapter" — Remove the nonexistent `SELECT ... FOR UPDATE` fallback; ADR-004 and the code reject and do not implement it.
F-5 — `docs/ai/specs/SPEC-001-booking-service.md:205` — "yield exactly 4 × 201 and 4 × 409 `capacity_exhausted`, distinct bays and technicians among winners, 8 committed key rows, overlap count 0, whatever mix of 23P01 and 40P01 occurred." — State that TC-31’s lock-honouring path expects no 40P01; retain retry/SQLSTATE coverage for TC-39 or a dedicated fallback test.
F-6 — `docs/ai/lessons.md:8` — "Evidence runs use the production retry policy (bound 5, `deadlock_timeout` 100 ms); a spike with a different policy proves nothing about the service" — Correct it: `race_savepoint.py` uses `RETRY_BOUND = N + 1` and its cited trace reports `deadlock_timeout=1s`; limit the production-policy claim to the implementation tests/demo.
F-7 — `docs/ai/specs/SPEC-001-booking-service.md:268` — "L-002 evidence runs with the production retry policy (bound 5, 100 ms deadlock timeout)." — Remove or qualify this repetition; the cited spike evidence uses a different bound and timeout.
F-8 — `docs/ai/verification-ledger.md:13` — "**Open.** Rule: the test accepts either SQLSTATE (23P01 or 40P01) and asserts the invariant, never the code path; 40P01 does not appear at every run" — Update V-002 to passed with the current TC-31 evidence; its open status contradicts the completed test and documented runs.
F-9 — `docs/adr/ADR-010.md:43` — "Staleness is by design and visible through `as_of`, which states the last commit the answer reflects." — Define `as_of` as a lower-bound/replay watermark, or read the watermark and availability data in one consistent snapshot; the code obtains them through separate connections, so post-watermark commits may be included.
F-10 — `docs/ai/specs/SPEC-001-booking-service.md:69` — "The system design is unchanged; after the audit, design.md section 2 gains one line naming the layers (D-038)." — Add the promised layer statement to `docs/design.md` section 2 or change this to an explicitly unresolved follow-up.
```

## Cycle 2 output (verbatim)

```text
Verdict: revise
F-11 — `src/scheduler/application/ports.py:91` — "Every booking of a dealership takes the same single lock before its first attempt, so attempts form no lock cycles and no 40P01 arises under contention (ADR-004 amendment, D-048)." — Scope this to writers that honour `serialise`; D-050/TC-39 prove an outside writer can still cause an attempt-path conflict.
F-12 — `docs/ai/specs/SPEC-001-booking-service.md:362` — "one at a time; no lock cycles, so no 40P01 under contention (ADR-004 amendment, D-048)" — Add the same “between writers that honour the lock” qualification and retain the D-050 fallback.
F-13 — `docs/adr/ADR-004.md:15` — "The spikes and the concurrency test start their clients behind a barrier." — Say that `race_savepoint.py` and the concurrency test use barriers; `race.py` deliberately uses a 50 ms stagger.
```

## Cycle 3 output (verbatim)

```text
Verdict: revise
F-14 — `README.md:160` — "Every row of the ADR-008 boundary, including the order 400, 404, then schema 422" — replace with the rows `tests/test_idempotency.py` actually covers; it contains no coverage for 23P01, 40P01, contention, crashes, 5xx, or final-409 replay rows.
```
