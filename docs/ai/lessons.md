# Lessons

Each row is a rule learned while building this service, recorded here so the code and the specification can cite it. IDs are local to this repository.

| ID | Rule | Origin | Applied in |
|---|---|---|---|
| L-001 | A barrier race at low client counts rarely produces a 40P01 deadlock; a concurrency test asserts the invariant (no overlap, correct winner count) and accepts either SQLSTATE | Spike `race_savepoint.py`: 23P01 only at N=2 and N=4, 40P01 appeared at N=8 | TC-31, `tests/test_concurrency.py` |
| L-002 | Evidence runs use the production retry policy (bound 5, `deadlock_timeout` 100 ms); a spike with a different policy proves nothing about the service | Spike re-run after the policy was fixed in ADR-004 | `tests/test_concurrency.py`, `scripts/demo.sh` |
| L-003 | SQLAlchemy's asyncio extension needs `greenlet`; a plain `sqlalchemy` dependency fails at `create_async_engine` | Dependency check during T1 | `pyproject.toml` |
| L-004 | Never write a value a CHECK constraint refuses; `weekday` is 0..6 with 0 = Monday | Seed design review | `migrations/versions/0002_seed.py`, `tests/test_seed.py` |
| L-005 | Concurrent inserts against exclusion constraints with shuffled resource order form lock cycles; PostgreSQL only runs the deadlock detector after `deadlock_timeout`, so under contention the waits stack. Serialise writers per tenant with a transaction-scoped advisory lock; keep the constraints as the invariant | T11 race evidence (D-048) | `src/scheduler/application/book_appointment.py`, `src/scheduler/infrastructure/postgres/unit_of_work.py` |
