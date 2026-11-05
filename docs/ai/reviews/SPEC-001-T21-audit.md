# SPEC-001 T21: decision register cross-check (Codex)

Adversarial read of `docs/decisions.md` and its three pointer lines against every passage in `README.md`, `docs/`, `src/`, `tests/`, `scripts/` and `migrations/` that cites a D-nnn id, by Codex (`codex exec -s read-only`). Checks: each row's sentence agrees with every citing passage; each "Restated in" target exists and carries the rule; instruction-book voice; one row per cited id. The working log is not in the repository and was not shown to the reviewer.

Base-SHA: `f79be29`
Cycles: 3 of a maximum of 3. Final verdict: approve. Cycle 1 F-1..F-9, cycle 2 F-1..F-7 (numbered per cycle), cycle 3 none. Dispositions:

| Finding | Disposition | Commit |
|---|---|---|
| C1 F-1, F-2 (D-001, D-002 narrower than ADR-001, ADR-002) | Fixed | 68ac7f6 |
| C1 F-3, C2 F-4 (ADR-004:17 and ADR-007:11 cite D-036 for the `deadlock_timeout` grant and VIN normalisation) | Rejected: citing passages are not changed by this task; reported to the author | |
| C1 F-4, F-5 (D-041, D-046 targets) | Fixed: targets widened | 68ac7f6 |
| C1 F-6 (D-050 origin against SPEC Scope Amendments) | Fixed: origin `review, accepted` | 68ac7f6 |
| C1 F-7 (origin header) | Fixed: wording | 68ac7f6 |
| C1 F-8 (technology names such as Swagger UI, curl) | Rejected: the voice rule bars AI model and agent names, not technology names; prompt clarified | |
| C1 F-9 (adoption wording) | Fixed for D-024, D-032, D-040; other rows already state a rule | 68ac7f6 |
| C2 F-1, F-2, F-3, F-5, F-6, F-7 (D-010, D-025, D-035, D-038, D-045, D-048) | Fixed: rows narrowed to what their targets state; D-048 scoped to writers that honour the lock | 15ee258, 544f7f5 |

## Cycle 1 output (verbatim)

```text
Verdict: revise
F-1 — `docs/adr/ADR-001.md:9` — "The client is stubbed with the OpenAPI contract, curl examples and a demo script." — D-001 substitutes Swagger UI and omits the cited OpenAPI contract; align the register sentence with this rule.
F-2 — `docs/adr/ADR-002.md:9` — "Python 3.12, FastAPI, psycopg 3 (async) with SQLAlchemy 2 Core, Alembic, PostgreSQL 16 with `btree_gist`." — D-002 omits most of the cited stack; state the complete decision or narrow the cited rule.
F-3 — `docs/adr/ADR-004.md:17` — "`deadlock_timeout` ... requires `GRANT SET ON PARAMETER deadlock_timeout` ... (D-036)." — D-036’s register sentence is about document length and detail placement, but this citation uses D-036 for the parameter grant; ADR-007 also uses it for VIN normalization. Reconcile the D-036 sentence and restatement targets with all cited rules.
F-4 — `docs/design.md:99` — "the code has four layers and a composition root" — D-041’s `design.md §2` target carries only the layer rule, not the entry’s ports and seven gate items. Narrow the row/target or add targets that carry every stated rule.
F-5 — `docs/ai/lessons.md:3` — "recorded here so the code and the specification can cite it." — D-046 claims that the SPEC, code comments, and README cite only L-ids; this target neither covers README nor the exclusivity claim. Point to the code-audit finding that establishes it, or revise the decision sentence.
F-6 — `docs/ai/specs/SPEC-001-booking-service.md:859` — "D-048 audit cycle 3 F-001" — D-050 is attributed to a code-audit finding, which the register defines as `review, accepted`, but its Origin is `AI, accepted`. Correct the Origin value or its definition.
F-7 — `docs/decisions.md:5` — "Origin names where a decision came from, not who approved it ... accepted by the author ... the author struck or reversed" — the Origin description contradicts itself by encoding approval and who acted. Rename the column/definition to cover provenance and disposition, or remove approval narratives.
F-8 — `docs/decisions.md:9` — "Swagger UI, curl and a demo script" — the register forbids tool product names, but these appear here and at lines 10, 12, 13, 21, 27, 32, and 40. Replace them with product-neutral rule descriptions.
F-9 — `docs/decisions.md:26` — "All fourteen findings of adversarial review 001 are adopted" — this is transcript-like process history, as are the adoption/proposal wording at lines 31, 35, 37, 40, and 46. Rewrite these as impersonal instruction-book rules.
```

## Cycle 2 output (verbatim)

```text
Verdict: revise
F-1 — `docs/decisions.md:15` — "customer creation belongs to the CRM" — ADR-007 does not state that rule; it only defines intake, snapshots, and later CRM reconciliation. Add an explicit restatement or remove the unsupported clause.
F-2 — `docs/decisions.md:27` — "every route is scoped by `dealership_id`; no customer accounts" — neither listed restatement target carries these rules. Add targets that do, or narrow the row to the authentication and `btree_gist` rules the targets actually state.
F-3 — `docs/decisions.md:32` — "`scripts/demo.sh` runs against the live service and ends with the race." — the demo’s race is section 7; section 8 prints the overlap query last. Replace “ends with the race” with the overlap-check outcome.
F-4 — `docs/adr/ADR-004.md:17` — "`deadlock_timeout` ... (D-036)" — this D-036 citation assigns a technical database-setting rule, but the D-036 row only describes document length and placement of detail. Expand D-036 to cover its cited rules or correct the citations.
F-5 — `docs/decisions.md:35` — "`docs/ai` ... gain their code-phase content after the code audit" — `docs/ai/README.md` does not state that timing rule. Remove it from “Restated in” or add an explicit restatement there.
F-6 — `docs/decisions.md:40` — "The final task is done ... green" — this is completion-status wording, not instruction-book register voice, and names tool products. State the enduring completion rule impersonally instead.
F-7 — `docs/decisions.md:42` — "so no lock cycle forms" — the cited design and ADR scope that guarantee to writers that honour the dealership lock; D-050 expressly permits bypass writers. Add that qualification.
```

## Cycle 3 output (verbatim)

```text
Verdict: approve
```
