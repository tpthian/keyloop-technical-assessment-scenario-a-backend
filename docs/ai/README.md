# AI collaboration: procedure and evidence

This directory holds the artefacts of the procedure in [design.md section 6](../design.md#6-how-genai-was-used-in-the-design-phase). Each file stands on its own.

## Roles

- Human (the author): proposes, decides, overrides, and reads every artefact before commit.
- AI, primary (Claude Code): challenges proposals, drafts documents from the decision log, runs spikes and checks, records the verification ledger. Separate agents run the drafting, the edits, the adversarial review and the spikes. Review agents report findings only and edit nothing.
- AI, second model (Codex): independent review of the design after the primary model's own review; findings only.

| Activity | Human | AI |
|---|---|---|
| Propose | Every design proposal and business stance: the first architecture sketch, the CRM stance, multi-day services, the scope checks | Alternatives inside a challenge; concrete values on request (timeouts, bounds, peak factor), each marked as a proposal for the author to strike |
| Challenge | AI drafts and figures: the observability section, the 1,000-site figure, the end-before-close reading, whether `/availability` should exist | Every human proposal, before it enters the decision log |
| Decide | Every decision-log entry | None |
| Draft | None; reads the drafts end to end | `docs/design.md`, the ADRs and the README, from the decision log only; lists every addition not in the log |
| Review | A disposition for every finding: adopted, wording, dismissed with reason, or limitation | Adversarial review by a separate agent; independent review by a second model; a triage proposal per finding |
| Verify | Reads the traces and the ledger | Live spikes against PostgreSQL; date and DST arithmetic; greps for the repository's writing rules; ledger entries |
| Override | CRM off the booking path; end-before-close struck; observability as a strategy; the sizing figure relabelled | None |

## How the pipeline runs

| Step | Actor | Gate | Artefact |
|---|---|---|---|
| 1. Proposal | Human | Not written into a repository document before steps 2 and 3 | None |
| 2. Challenge | AI | Every proposal receives a counter-argument or a named alternative | [Decision ownership](#decision-ownership) below |
| 3. Decision log | Human decides; AI records | Each entry states context, options, choice, rationale and consequence | Working log outside the repository; each entry is restated in an ADR and cited as D-nnn ([../adr/](../adr/README.md)) |
| 4. Draft docs | AI drafting agent | Drafted from the decision log only; each addition not in the log is listed for the author to accept or strike | [../design.md](../design.md), [../adr/](../adr/README.md) |
| 5. Adversarial review | AI, separate agent, findings only, no edits | Each finding gets a disposition from the author before any edit | [reviews/review-001.md](reviews/review-001.md) |
| 6. Live spike | AI runs; human reads the trace | A claim about the concurrency mechanism (constraint conflict, deadlock, savepoint recovery) enters the design only with a trace from a live database | [../evidence/spike/](../evidence/spike/) |
| 7. Independent second-model review | AI, second model, findings only | AI triage proposes a disposition per finding; the author accepts or strikes each | [reviews/review-002.md](reviews/review-002.md) |
| 8. Verification ledger | AI records; human reads | Each claim carries method, result and evidence path; an open claim stays open until its test runs | [verification-ledger.md](verification-ledger.md) |
| 9. Author's read | Human | End-to-end read of design.md and the ADRs | None |
| 10. Commit | Human | pre-commit hooks locally; the same checks plus pytest in CI (ADR-011) | Git history |

## Decision ownership

| Topic | Human proposal | AI challenge | Decision | Decided by |
|---|---|---|---|---|
| Who owns bay and technician calendars (ADR-003) | A separate "ServiceBay service" owns dealerships, bays, slots and technicians; the scheduler looks them up | "Check then confirm" becomes a cross-service write with no shared transaction; the guarantee becomes a saga or reservation protocol | The scheduler owns bays, technicians, skills and the calendar | Human, adopting the challenge |
| How double booking is prevented (ADR-004) | A FIFO queue or an application-level check | PostgreSQL exclusion constraints with commit-order arbitration; a queue gives an asynchronous "accepted", a broker and a throughput cap; an application lock is not valid across instances | Exclusion constraints; FIFO, application lock and `SELECT ... FOR UPDATE` rejected, the last kept as fallback adapter | Human, adopting the challenge |
| Idempotency key (ADR-008) | Key derived from request content | A retry and a deliberate later rebooking of the same car are indistinguishable by content | Mandatory client-generated key, now a UUID | Human, adopting the challenge |
| CRM on the booking path (ADR-007) | Never turn a customer away over data quality; the CRM reconciles later | CRM as a port with a stub adapter; open question whether to validate IDs synchronously against the CRM, fail-closed | Booking never calls the CRM; the scheduler is an intake point; the CRM reconciles from `AppointmentConfirmed` | Human, overriding the AI |
| Scope and demonstration surface (ADR-012) | Is a UI needed to demonstrate a backend? Standing rule: thinking over code, demonstrable, never perfected | No custom UI: Swagger UI and a demo script; a UI costs about half a day and cannot show the concurrency guarantee | Cover the challenge exactly; Swagger UI, demo script and curl; no custom frontend | Human |
| Services longer than opening hours (ADR-005, ADR-009) | Strike the drafted "appointment must end before closing"; services span days; store the end snapped to the next opening instant | The snap buys no safety (identical conflict sets when starts lie inside hours), puts a calendar walk in the write path and loses the true completion time | Start inside opening hours; `end_at` is the true elapsed end, unconstrained; `pickup_from` derived | Human: struck the AI reading, adopted the challenge to the snap |
| Observability (ADR-013) | The brief asks for a strategy, not a server; later import must be trivial; serve the engineer and the business at once; no personal data | The first draft listed tools with no questions behind them; the revised proposal: wide event, derived metrics, event-based SLO, overlap audit | One wide event per request is the product; servers are documented extensions; metrics endpoint and background audit later cut, the overlap query kept in the concurrency test and `demo.sh` | Human, overriding the AI draft |
| The 1,000-site figure (ADR-004) | Does a service business have 1,000 sites? | Brief checked: it gives no count; the figure came from the scaling debate and was written as if given | Labelled as a sizing assumption; the design is unchanged for a handful of sites | Human, who caught it |
| Quality gates (ADR-011) | Pre-commit hooks first, so code stays uniform if others join | Hooks are opt-in and bypassable; tooling is not the opening move, the guarantee is | Pre-commit plus CI running the same checks, set up after the design | Human, adopting the challenge |
| Availability endpoint (ADR-010) | Drop `/availability`, since it is stale between view and book | Keep it, advisory, stamped with `as_of`; booking is authoritative | Advisory availability with `as_of` | Human, adopting the challenge |

Defects caught before code, with what each changed: [defects-caught.md](defects-caught.md).

## Gates

- A finding is never applied without a disposition: adopted, wording, dismissed with a stated reason, or limitation.
- An edit agent reports every sentence it adds beyond its instruction as an addition; the author accepts or strikes each.
- A reviewer receives the brief, the design, the ADRs and the evidence, and is told what earlier reviews found, so it hunts new ground.
- A spike result is cited with the file that produced it. `make spike` reruns both spikes against the compose database.
- A green check is read for what it checked: a pass that inspected nothing is recorded as a false pass (see V-000b).
- Tests are written from the acceptance criteria, not from the code (implementation phase).

## Where each artefact lives

| Artefact | Path | Phase |
|---|---|---|
| Design document | [../design.md](../design.md) | Design |
| Decision records | [../adr/](../adr/README.md) | Design |
| Spike code and traces | [../evidence/spike/](../evidence/spike/) | Design |
| Adversarial review | [reviews/review-001.md](reviews/review-001.md) | Design |
| Second-model review | [reviews/review-002.md](reviews/review-002.md) | Design |
| Verification ledger | [verification-ledger.md](verification-ledger.md) | Design, continued in implementation |
| Defects caught before code | [defects-caught.md](defects-caught.md) | Design |
| SPEC (contract and execution plan per task) | [specs/SPEC-001-booking-service.md](specs/SPEC-001-booking-service.md); per-task status, gates and deviations in [specs/SPEC-001-status.md](specs/SPEC-001-status.md) | Implementation |
| SPEC review (second model) | [reviews/SPEC-001-spec-review.md](reviews/SPEC-001-spec-review.md) | Implementation |
| Code audit against the SPEC | Whole SPEC: [reviews/SPEC-001-code-audit.md](reviews/SPEC-001-code-audit.md); one audit per task series: `reviews/SPEC-001-T<n>-audit.md` | Implementation |
| AI Collaboration Narrative | `README.md` at the repository root, written in the implementation phase | Implementation |

Implementation-phase roles: spec author (Claude), spec reviewer (Codex), implementation agent, code auditor (Claude), each a separate agent with its own artefact here.
