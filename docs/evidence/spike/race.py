"""Spike: two 'users' book the same bay + technician + time range concurrently.

Shows:
  1. A inserts and holds its transaction open (simulates in-flight work before commit).
  2. B inserts the same bay/technician/range 50 ms later: B BLOCKS inside INSERT
     until A decides (PostgreSQL waits on the conflicting uncommitted row).
  3. A commits -> B's INSERT fails with exclusion_violation (23P01). A won.
  4. B retries with the next candidate (bay 3, tech 9) and is confirmed too.
Run:  make spike   (compose database), or
      DATABASE_URL=postgresql://user:pass@host:port/db python -I race.py
      DATABASE_URL defaults to the original throwaway spike container below.
"""

import os
import threading
import time

import psycopg
from psycopg import errors

DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:spike@localhost:55439/spike").replace(
    "postgresql+psycopg://",
    "postgresql://",  # accept the SQLAlchemy form used by the app
)
START, END = "2026-11-10 09:00+07", "2026-11-10 10:30+07"

# Resources at the dealership: bays are skill-agnostic; technicians 7 and 9 both hold the skill.
CANDIDATES = [(2, 7), (3, 9)]  # (bay_id, technician_id), first-fit order

log_lock = threading.Lock()
t0 = time.perf_counter()


def log(msg: str) -> None:
    with log_lock:
        print(f"[{(time.perf_counter() - t0) * 1000:7.1f} ms] {msg}", flush=True)


def insert(conn, who: str, bay: int, tech: int) -> None:
    conn.execute(
        "INSERT INTO appointment (dealership_id, bay_id, technician_id, start_at, end_at, label)"
        " VALUES (1, %s, %s, %s, %s, %s)",
        (bay, tech, START, END, who),
    )


def user_a() -> None:
    """Books the first candidate and holds the transaction open for 300 ms before commit."""
    bay, tech = CANDIDATES[0]
    with psycopg.connect(DSN) as conn, conn.transaction():
        insert(conn, "A", bay, tech)
        log(f"A: INSERT bay={bay} tech={tech} (uncommitted, holding 300 ms)")
        time.sleep(0.3)
        log("A: COMMIT")
    log(f"A: CONFIRMED bay={bay} tech={tech}")


def user_b() -> None:
    """Arrives 50 ms after A. Same first candidate. Retries on exclusion violation."""
    with psycopg.connect(DSN) as conn:
        for bay, tech in CANDIDATES:
            try:
                log(f"B: INSERT bay={bay} tech={tech} ...")
                with conn.transaction():
                    insert(conn, "B", bay, tech)
                log(f"B: CONFIRMED bay={bay} tech={tech}")
                return
            except errors.ExclusionViolation as e:
                log(
                    f"B: LOST bay={bay} tech={tech} -> {e.diag.constraint_name} "
                    "(23P01), next candidate"
                )
        log("B: 409 no bay/technician available")


def main() -> None:
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(open(__file__.replace("race.py", "schema.sql")).read())

    a = threading.Thread(target=user_a)
    b = threading.Thread(target=user_b)
    a.start()
    time.sleep(0.05)
    b.start()
    a.join()
    b.join()

    with psycopg.connect(DSN) as conn:
        rows = conn.execute(
            "SELECT label, bay_id, technician_id FROM appointment ORDER BY id"
        ).fetchall()
    print("\nFinal table:", *rows, sep="\n   ")
    assert len(rows) == 2 and len({r[1] for r in rows}) == 2 and len({r[2] for r in rows}) == 2
    print("\nOK: exactly one booking per bay and per technician for the overlapping range.")


if __name__ == "__main__":
    main()
