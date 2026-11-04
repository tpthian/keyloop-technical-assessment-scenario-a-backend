# SPEC-001 T12 audit

Task: T12 — Demo, compose, Makefile
Base: `a51ee968628fe85b67a74bae3fc38f80335fdb56`
Head: `f9c64ec1593a14779b72753e69c50deae28a4ff6`
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings

None.

## Evidence

- Scope: `git diff --name-status a51ee96..HEAD -- scripts docker-compose.yml Makefile` reported only `Makefile`, `docker-compose.yml`, deletion of the replaced `scripts/.gitkeep`, and `scripts/demo.sh`. The `Makefile` socket-override line is the stated T13/orchestrator addition and was not scored against T12. `PYTHONUNBUFFERED: "1"` makes the ADR-013 JSON events promptly visible to the required compose-log step and is appropriate.
- Exact wiring: `docker-compose.yml:27-30` runs `alembic upgrade head && uvicorn scheduler.main:create_app --factory --host 0.0.0.0 --port 8000`; `Makefile:26-28` runs exactly `docker compose up -d --build --wait db api` followed by `scripts/demo.sh`.
- Contract/design: the booking payload uses the specified POST path, UUID header, naive whole-minute local time, and required customer/vehicle fields; all asserted statuses/codes match the Wire formats. The availability request uses the specified GET path and `service_type_id`, `from`, and `to` query fields, and prints `as_of` plus per-pair windows. `scripts/demo.sh:26-31` is textually equivalent to `tests/conftest.py`'s design §5 / ADR-013 overlap query.
- Race/barrier: bodies and keys are created before launch; all eight clients create an armed marker and spin on one start marker. The parent polls for all eight for at most five seconds, releases the marker before reporting an incomplete cohort (so waiters cannot hang), and on the success path waits for every recorded PID. Each response has its own `race-N.json` and `race-N.status`, is printed per client, the split is asserted as 2 x 201 and 6 x 409 `capacity_exhausted` (D-044 seed 2x2), and the final eight `book_appointment` JSON events are printed from compose logs.
- Clean-run handling: the script documents `make down && make demo` and rejects any non-empty `appointment` table before section 1.
- Commit protocol: `dc353b1`, `6cd7753`, `6429cdd`, and `f9c64ec` each have a `SPEC-001 T12:` subject and a `Co-Authored-By` trailer.
- Identifier scan: `git diff a51ee96..HEAD -- scripts docker-compose.yml Makefile | rg 'ERR-[0-9]+|LSN-[A-Za-z0-9_-]+'` produced no matches.
- `git diff --check a51ee96..HEAD -- scripts docker-compose.yml Makefile` produced no output; `git show --check dc353b1 6cd7753 6429cdd f9c64ec` produced no whitespace errors.
- `bash -n scripts/demo.sh` → `PASS`.
- `uvx --from shellcheck-py shellcheck scripts/demo.sh` was attempted with isolated writable uv cache/tool directories but could not fetch `shellcheck-py` because sandbox DNS is unavailable; no shellcheck result is available. Docker is unavailable in this audit environment, so `docker compose config -q` was skipped.
- Verification-leg evidence: real `make down && make demo` reached section 6 and exited 2 only because T10b's availability endpoint is not merged (404). The supplied clean-stack diagnostic copy with only section 6 removed exited 0 with final line `0`; it also records five prior clean runs with the same race outcome.

| Demo section | Verdict | Evidence |
|---|---|---|
| 1. Health | pass | `/health/live` and `/health/ready` each returned 200 with `{"status":"ok"}`. |
| 2. Book Oil change | pass | Next-Monday 09:00 request returned 201 with the specified appointment wire body. |
| 3. Same-key replay | pass | Returned 201 and the same `appointment_id`. |
| 4. Same key, different body | pass | Returned 422 `replay_conflict`. |
| 5. Same car overlap | pass | Normalised VIN request returned 409 `vehicle_already_booked`. |
| 6. Availability | pending T10b | Static request/output format is correct; real run received 404 because the endpoint is not yet merged, not because of T12. |
| 7. Eight-client race | pass | Diagnostic run and five prior clean runs each recorded 2 x 201, 6 x 409 `capacity_exhausted`, per-client files/lines, and eight final booking events. |
| 8. Overlap count | pass | The design §5 query printed last and returned `0`. |
