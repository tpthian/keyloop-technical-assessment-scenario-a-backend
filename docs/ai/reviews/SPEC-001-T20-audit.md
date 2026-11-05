# SPEC-001 T20 audit

Task: T20 (security posture and request bounds, D-058)
Base-SHA: `f79be29`
Head-SHA: `ac9c6195af8a1342bf362df4a10a1d211116c7b1`
Commits:
- `84f6f7cc541697b2c10163c54f445a4dd3aa71a3 SPEC-001 T20: request body cap 413 and string max lengths; TC-40 (design §7, ADR-014)`
- `35007fe9b4ec574d44df413bf893fd79107f6b28 SPEC-001 T20: ADR-014 security posture and trust boundary; design section 7; 413 in ADR-008 and the ADR-013 SLI (design §7, ADR-014)`
- `023385b51883a3f62450be0fbd0b2d9d6b64e90f SPEC-001 T20: README deliverables map to ADR-014, 413 in the code table, narrative wording and security bullet (design §7, ADR-014)`
- `c20d9c2f2d8d3276a7067263790a0061276f2c6b SPEC-001 T20: 413 named in every pre-claim list; /docs gating stated as deferred; README counts (design §7, ADR-014)`
- `d87c51f96e36c99f7023a1689486453ee0ab7a13 SPEC-001 T20: 413 in the booking route's OpenAPI responses; XSS and Swagger rows scoped; SPEC contract sources to ADR-014 (design §7, ADR-014)`
- `ac9c6195af8a1342bf362df4a10a1d211116c7b1 SPEC-001 T20: fixes after Codex cycle 3, unverified by Codex: 413 in the SPEC code table, README and ADR index; TC-40 counts key rows (design §7, ADR-014)`

Allowed-Paths: `docs/adr/ADR-014.md`, `docs/adr/README.md`, `docs/design.md`, `src/scheduler/interfaces/http/` (`limits.py`, `errors.py`, `schemas.py`, `appointments.py`), `src/scheduler/main.py`, `tests/test_booking_api.py` (TC-40 only), `docs/ai/specs/SPEC-001-booking-service.md`, `docs/ai/specs/SPEC-001-status.md`, `README.md`; consistency rows in `docs/adr/ADR-008.md` and `docs/adr/ADR-013.md`; and this report path.
Changed-Paths:
- `M README.md`
- `M docs/adr/ADR-008.md`
- `M docs/adr/ADR-013.md`
- `A docs/adr/ADR-014.md`
- `M docs/adr/README.md`
- `M docs/ai/specs/SPEC-001-booking-service.md`
- `M docs/design.md`
- `M src/scheduler/interfaces/http/appointments.py`
- `M src/scheduler/interfaces/http/errors.py`
- `A src/scheduler/interfaces/http/limits.py`
- `M src/scheduler/interfaces/http/schemas.py`
- `M src/scheduler/main.py`
- `M tests/test_booking_api.py`

Checks (leg, on the head):
- `uv run pre-commit run --all-files` — exit `0` — all hooks passed.
- `uv run mypy src` — exit `0` — no issues found in 34 source files.
- `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest -q` — exit `0` — `110 passed`.

Auditor: Codex, read-only (`codex exec -s read-only`), cap of three cycles. Each cycle's verdict follows verbatim.

## Cycle 1 (head 023385b)

Findings:

1. `docs/adr/ADR-014.md:31` — Claims production disables or gates `/docs` and `/openapi.json` through a setting, but no such setting exists; FastAPI defaults leave both exposed. — State this as a deferred requirement or implement/document the setting.
2. `docs/design.md:111` — The pre-claim flow lists 400/404/422 but omits the new pre-claim 413. — Add 413 `validation`, never stored.
3. `docs/design.md:142` — The idempotency-boundary status list omits 413 despite describing all responses before `BEGIN`. — Include 413 as never stored.
4. `docs/ai/specs/SPEC-001-booking-service.md:202` — AC-04 says every ADR-008 row holds but omits its new 413 row. — Add the 413 pre-claim/no-key-row case.
5. `docs/ai/specs/SPEC-001-booking-service.md:535` — The documented booking-handler sequence omits the 413 body-cap outcome before dealership loading. — Document `BodyTooLarge`/413 at `request.json()`.
6. `docs/adr/ADR-013.md:17` — The event-schema description’s pre-outcome response list omits 413, whose booking fields are likewise null. — Add 413 to the list.
7. `README.md:205` — States 16 acceptance criteria and 39 test cases, but SPEC now has AC-17 and TC-40. — Update to 17 and 40.
8. `README.md:208` — States 109 tests, but the added TC-40 function brings the suite to 110. — Update the count to 110.

Verdict: revise

Fixed in c20d9c2.

## Cycle 2 (head c20d9c2)

Findings:

1. `docs/adr/ADR-014.md:55` — Claims the API “renders no HTML,” but FastAPI’s default `/docs` serves Swagger UI HTML. — Qualify this as the booking API not rendering request data, and assess the docs UI separately.

2. `docs/adr/ADR-014.md:64` — States production “disables or gates” Swagger/OpenAPI, contradicting line 31: no setting exists and this is deferred. — Reword as a deferred requirement.

3. `src/scheduler/interfaces/http/appointments.py:30` — The served OpenAPI contract omits 413 even though the booking endpoint returns it and all Markdown status tables document it. — Add a 413 `ErrorOut` response entry.

4. `docs/ai/specs/SPEC-001-booking-service.md:14` — Contract sources still end at ADR-013 despite AC-17 and T20 relying on ADR-014. — Extend the range through ADR-014.

Verdict: revise

Fixed in d87c51f.

## Cycle 3 (head d87c51f)

Findings:
1. tests/test_booking_api.py:54 — TC-40’s “no key row” check selects nullable `response_code`; a claimed but unrecorded key also returns `None` — assert that no row exists (for example, `COUNT(*) == 0`).
2. docs/ai/specs/SPEC-001-booking-service.md:171 — the Wire-format status table omits the implemented 413 pre-BEGIN `validation` response — add 413 body-over-cap, never stored.
3. README.md:62 — the pre-transaction idempotency list omits 413 — include body-over-cap 413 as never stored.
4. docs/adr/README.md:14 — ADR-008’s summary omits 413 from pre-claim refusals — include 413 `validation`.

Verdict: revise

Cap reached with findings open: BLOCKED. All four findings fixed in ac9c619 after the cap; that commit is not re-verified by Codex. Gates on ac9c619 as above.
