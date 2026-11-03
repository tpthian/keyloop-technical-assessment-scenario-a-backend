"""Spike V-001: ROLLBACK TO SAVEPOINT recovers from 40P01 (deadlock) and 23P01
(exclusion violation) inside ONE transaction that already holds the idempotency
key row, so retry-next-candidate can run in a single transaction (design.md
section 3, "One savepoint per attempt").

What it does:
  * N clients, each in one transaction: INSERT its idempotency key row, then wait
    on a barrier so every first INSERT into appointment is issued at the same
    instant (true simultaneity, the condition that produces 40P01 instead of 23P01).
  * Each attempt is wrapped in SAVEPOINT attempt_i. On 23P01 or 40P01 the client
    issues ROLLBACK TO SAVEPOINT and tries the next candidate; the key row is
    untouched. On success it RELEASE SAVEPOINT and COMMIT.
  * All clients target the same first candidate (worst case), so at most one wins
    the first pair and the rest must recover.

Pass criteria:
  1. Every client ends with exactly one appointment (candidates >= clients).
  2. No pair is used twice; the exclusion constraints hold.
  3. Every client's key row is committed (the rollback did not undo it).
  4. At least one 40P01 was seen and recovered from (otherwise the test did not
     exercise V-001; re-run).

Run:  make spike   (compose database, n_clients=8), or
      DATABASE_URL=postgresql://user:pass@host:port/db python -I race_savepoint.py [n_clients]
      DATABASE_URL defaults to the original throwaway spike container below.
"""

import os
import sys
import threading
import time

import psycopg
from psycopg import errors

DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:spike@localhost:55439/spike").replace(
    "postgresql+psycopg://",
    "postgresql://",  # accept the SQLAlchemy form used by the app
)
START, END = "2026-11-10 09:00+07", "2026-11-10 10:30+07"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
CANDIDATES = [(b, t) for b, t in zip(range(1, N + 2), range(11, N + 12), strict=True)]  # N+1 pairs
RETRY_BOUND = N + 1  # enough to reach a free pair; prod bound is 5

KEY_SCHEMA = """
CREATE TABLE IF NOT EXISTS idem_key (
    key text PRIMARY KEY,
    appointment_id int,
    outcome text
);
TRUNCATE idem_key;
"""

log_lock = threading.Lock()
results: dict[str, dict] = {}
t0 = time.perf_counter()
barrier = threading.Barrier(N)


def log(msg: str) -> None:
    with log_lock:
        print(f"[{(time.perf_counter() - t0) * 1000:8.1f} ms] {msg}", flush=True)


def client(who: str) -> None:
    rec = {"attempts": 0, "e23P01": 0, "e40P01": 0, "won": None, "error": None}
    results[who] = rec
    try:
        with psycopg.connect(DSN) as conn:
            with conn.transaction():
                conn.execute("INSERT INTO idem_key (key) VALUES (%s)", (who,))
                barrier.wait()  # every first appointment INSERT leaves at once
                for i, (bay, tech) in enumerate(CANDIDATES[:RETRY_BOUND]):
                    rec["attempts"] += 1
                    conn.execute(f"SAVEPOINT attempt_{i}")
                    try:
                        row = conn.execute(
                            "INSERT INTO appointment (dealership_id, bay_id, technician_id,"
                            " start_at, end_at, label) VALUES (1, %s, %s, %s, %s, %s) RETURNING id",
                            (bay, tech, START, END, who),
                        ).fetchone()
                    except errors.ExclusionViolation as e:
                        rec["e23P01"] += 1
                        log(f"{who}: LOST bay={bay} tech={tech} 23P01 {e.diag.constraint_name}")
                        conn.execute(f"ROLLBACK TO SAVEPOINT attempt_{i}")
                        continue
                    except errors.DeadlockDetected:
                        rec["e40P01"] += 1
                        log(f"{who}: LOST bay={bay} tech={tech} 40P01 deadlock")
                        conn.execute(f"ROLLBACK TO SAVEPOINT attempt_{i}")
                        continue
                    conn.execute(f"RELEASE SAVEPOINT attempt_{i}")
                    conn.execute(
                        "UPDATE idem_key SET appointment_id=%s, outcome='201' WHERE key=%s",
                        (row[0], who),
                    )
                    rec["won"] = (bay, tech)
                    log(f"{who}: WON bay={bay} tech={tech} after {rec['attempts']} attempt(s)")
                    break
                else:
                    log(f"{who}: 409 after {rec['attempts']} attempts")
            # transaction committed here (key row + appointment, or key row only)
    except Exception as e:  # noqa: BLE001 - spike: record anything unexpected
        rec["error"] = f"{type(e).__name__}: {e}"
        log(f"{who}: UNEXPECTED {rec['error']}")
    rec["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)


def main() -> None:
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(open(__file__.replace("race_savepoint.py", "schema.sql")).read())
        conn.execute(KEY_SCHEMA)
        dl = conn.execute("SHOW deadlock_timeout").fetchone()[0]
    print(f"clients={N} candidates={len(CANDIDATES)} deadlock_timeout={dl}\n")

    threads = [threading.Thread(target=client, args=(f"C{i}",)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with psycopg.connect(DSN) as conn:
        appts = conn.execute(
            "SELECT label, bay_id, technician_id FROM appointment ORDER BY label"
        ).fetchall()
        keys = conn.execute(
            "SELECT key, appointment_id, outcome FROM idem_key ORDER BY key"
        ).fetchall()
        overlaps = conn.execute(
            """SELECT count(*) FROM appointment a JOIN appointment b ON a.id < b.id
               AND (a.bay_id = b.bay_id OR a.technician_id = b.technician_id)
               AND tstzrange(a.start_at, a.end_at) && tstzrange(b.start_at, b.end_at)"""
        ).fetchone()[0]

    print("\nappointment:", *appts, sep="\n   ")
    print("idem_key:", *keys, sep="\n   ")
    print("\nper client:")
    for who, r in sorted(results.items()):
        print(f"   {who}: {r}")

    total_40 = sum(r["e40P01"] for r in results.values())
    total_23 = sum(r["e23P01"] for r in results.values())
    errors_ = [w for w, r in results.items() if r["error"]]
    print(f"\n23P01={total_23} 40P01={total_40} overlaps={overlaps} unexpected={errors_}")

    assert not errors_, "a client raised something other than 23P01/40P01"
    assert overlaps == 0, "exclusion constraint violated"
    assert len(appts) == N, "every client should hold exactly one appointment"
    assert len(keys) == N and all(k[1] is not None for k in keys), (
        "every key row must be committed with its appointment id"
    )
    assert {a[0] for a in appts} == {k[0] for k in keys}
    if total_40 == 0:
        print("\nINCONCLUSIVE for V-001: no 40P01 this run (only 23P01). Re-run.")
        sys.exit(2)
    print(
        "\nOK V-001: ROLLBACK TO SAVEPOINT recovered from 40P01 inside one transaction;"
        " key rows and winners committed together; zero overlaps."
    )


if __name__ == "__main__":
    main()
