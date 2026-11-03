# Verification ledger

One row per claim the design depends on. A claim is closed only by the method in its row; an open claim stays open until its test runs.

| ID | Claim | Method | Result | Evidence |
|---|---|---|---|---|
| V-000a | Two concurrent bookings on one bay cannot both commit | Spike: 2 threads, B starts 50 ms after A, PostgreSQL 16 | Pass: B blocks inside INSERT until A commits, gets 23P01 `no_bay_overlap`, and is confirmed on the next candidate. Limitation: the stagger excludes true simultaneity (see V-000c) | `docs/evidence/spike/race.py`, `docs/evidence/spike/race-output.txt` |
| V-000b | pre-commit gates the repository skeleton | `pre-commit run --all-files` on the fresh clone | False pass: untracked files are skipped, so nothing was checked. Re-run after `git add -N`: all hooks pass on the real files | `docs/ai/defects-caught.md` |
| V-000c | Simultaneous INSERTs on the same pair give 23P01 to the loser | Adversarial review agent: 8 clients, same pair, live PostgreSQL | Fail: 40P01 deadlock in 9 of 11 transactions, average latency 11.7 s. Design changed: 40P01 is a lost candidate; candidate order randomised; barrier-based concurrency test | `docs/ai/reviews/review-001.md` (finding 1) |
| V-001 | `ROLLBACK TO SAVEPOINT` recovers from 40P01 and 23P01 inside the one transaction that holds the key row | Spike: N clients behind a barrier, one transaction each, savepoint per attempt; N = 2, 4, 8 | Pass at N = 8: 24 x 23P01 and 4 x 40P01 recovered; 8 of 8 key rows committed with their appointment ids; 0 overlaps. N = 2 and N = 4 produced no 40P01: pass for 23P01, inconclusive for the deadlock path | `docs/evidence/spike/race_savepoint.py`, `docs/evidence/spike/race-savepoint-output-n8.txt` |
| V-001r | V-001 reproduces with the parameterised script | 8 reruns at N = 8 against the original spike database after the DSN was parameterised | 5 runs saw 40P01 and passed; 3 saw only 23P01 and exited 2 (inconclusive); no run failed an assertion (0 overlaps, every key committed) | `docs/evidence/spike/race_savepoint.py`; rerun with `make spike` |
| V-003 | Worked example in ADR-010: a 4,320 min service starting Fri 2027-03-26 09:00 `Europe/London` ends Mon 2027-03-29 09:00Z (10:00 BST); latest start before E2 is 2027-03-26 11:00Z | `zoneinfo` arithmetic: convert the start to UTC, add the duration, convert back | Pass: end 2027-03-29 09:00+00:00, local 10:00+01:00; E2 start 2027-03-29 11:00Z minus 72 h = 2027-03-26 11:00Z | Command below |
| V-002 | The implementation's concurrency test holds the invariant under a production-shaped race: five-attempt bound, pruning by constraint name, randomised order, concurrent duplicate keys, crash points, asserted HTTP and domain outcomes, booking latency recorded | Barrier-based integration test against PostgreSQL (testcontainers) | **Open.** Rule: the test accepts either SQLSTATE (23P01 or 40P01) and asserts the invariant, never the code path; 40P01 does not appear at every run | Added in the implementation phase |

V-003 command:

```bash
python3 -I -c '
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
L = ZoneInfo("Europe/London")
s = datetime(2027, 3, 26, 9, 0, tzinfo=L)
e = s.astimezone(timezone.utc) + timedelta(minutes=4320)
print(e, e.astimezone(L))
e2 = datetime(2027, 3, 29, 12, 0, tzinfo=L).astimezone(timezone.utc)
print(e2, e2 - timedelta(hours=72))
'
```

Notes:

- The spike scripts differ from the runs that produced the traces only in the DSN line, which reads `DATABASE_URL` with the original value as default.
- `race_savepoint.py` exits 2 when a run sees no 40P01; `make spike` then stops, and the run is repeated.
