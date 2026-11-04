# SPEC-001 T6 Audit

Task: T6 — Ports, outcomes, booking use case, fakes
Base: `877284d86bfcb39517a78555741340829b70471e`
Head: `3f9429ab5268372cc4af3b05d1142e84e3f9f6ac`
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings

None.

## Sequence check

| SPEC / ADR-008 requirement | Implementation evidence | Result |
|---|---|---|
| Step 4: canonicalise and hash with the loaded dealership's zone before `BEGIN` | `book_appointment.py:65` calls `canonical_hash(cmd, dealership.zone)` before the context manager. | Pass |
| Step 5: enter one UoW and claim first | `67-70` enters `self.uow()` and immediately calls `idempotency.claim`. | Pass |
| Existing different hash raises `ReplayConflict` inside the block | `71-74` compares hashes and raises before leaving the context. | Pass |
| Existing same hash returns a final replay with no attempt | `74` returns `replay_outcome`; no validation, gate, candidate query, or reserve follows on that branch. | Pass |
| Step 6 validation order: unknown service → local conversion/gap → past → horizon → hours → qualified technician | `_validate`, `151-167`, is in exactly that order. Each failure is returned to `75-81`, where a business `validation` body is recorded before the transaction exits. | Pass |
| End is elapsed UTC; candidate order is qualified → free candidates → shuffled | `83` uses domain `end_at`; `84-89` obtains qualified technicians, calls `free_candidates`, then wraps the result in `shuffled`. | Pass |
| Gate is awaited once before attempts | `99-101` awaits the optional gate immediately before one `run_attempts` call. | Pass |
| Confirmed result is loaded, presented, recorded, and returned with counters and winning resource IDs | `102-118` calls `by_id`, `appointment_body`, `record`, and constructs the complete final `Outcome`. | Pass |
| Final capacity and vehicle conflicts are recorded | `119-131` records both final 409 variants and returns counters. | Pass |
| Contention leaves the block, rolls back the claim, and becomes a non-final outcome outside it | `132` raises `Contention` in the context; `133-141` catches it outside and returns `final=False` with counters. | Pass |
| No database exception is caught; no dealership lookup or `NotFound` is raised | The only catches are `GapTime` (`155-157`) and outer `Contention` (`133`); no `reads.dealership` or `NotFound` reference occurs. | Pass |

The implementation differs from the illustrative booking block only by using named constants instead of repeated string literals and by adding defensive assertions after validation / confirmation. These are behaviour-preserving for the specified domain functions and ports.

`ports.py` has all seven required Protocols, their specified members, argument names, and specified types/returns. Its `UnitOfWork.__aexit__` additionally annotates the reference block's otherwise untyped `et`, `ev`, and `tb` arguments (`type[BaseException] | None`, `BaseException | None`, and `TracebackType | None`); this is a behaviour-preserving typing refinement, not a contract change. `__aenter__` uses an unquoted forward reference under `from __future__ import annotations`, equivalent to the reference block's quoted form.

`Outcome` matches the specified frozen fields and defaults. Error bodies have the required `code` and `message` shape. `replay_outcome` correctly returns final replay counters at zero, extracts resource IDs only from a stored confirmed body (consistent with ADR-013's “null when not a 201” rule), and rejects an unrecorded claimed row (`code is None`) with `RuntimeError`. `appointment_body` has exactly the 201/GET keys and UTC `Z` instant format; `GetAppointment` performs the required dealership-scoped lookup and `NotFound` handling.

TC coverage is one test function for every listed clause: TC-09 has dealership/no-lookup, different-hash conflict, and same-hash replay; TC-10 has each of the six business failures; TC-11 has each final/transient result plus a gate-order observation. The contention test observes rollback and absent key/appointment rows; the gate test asserts `gate` precedes every `reserve`.

## Evidence

| Command / inspection | Result |
|---|---|
| `git diff --name-status 877284d86bfcb39517a78555741340829b70471e..HEAD` | Exactly seven added paths, all in T6's approved Paths list; no out-of-scope paths. |
| `git show` of both commits | Exact required subjects: `SPEC-001 T6a: application ports and outcomes (design §2)` and `SPEC-001 T6b: BookAppointment use case with fakes (design §3, ADR-008)`; both include `Co-Authored-By`. |
| `uv run pytest tests/test_book_appointment_usecase.py tests/test_architecture.py -q` | `17 passed in 0.10s` |
| `uv run mypy src tests/fakes.py` | `Success: no issues found in 22 source files` |
| `uv run mypy src` | `Success: no issues found in 21 source files` |
| `uv run pre-commit run --all-files` | All hooks passed, including ruff and mypy. |
| Temporary probe: change `FakeReads.service_type(service_type_id: int)` to `str`; run `uv run mypy tests/fakes.py` | Failed as required: Protocol assignment errors at `tests/fakes.py:171` and `:229`, reporting expected `int` versus actual `str` (plus the local incompatible dictionary lookup errors). |
| Restore probe then `git diff --exit-code tests/fakes.py` | Exit 0; no residual fake-file change. Follow-up mypy check: `Success: no issues found in 1 source file`. |
| Application import scan and `tests/test_architecture.py` | Application imports only `scheduler.application`, `scheduler.domain`, and standard-library modules; architecture suite passed. |
