# Unified Service Scheduler (Scenario A, backend)

Status: design settled; implementation pending.

## Quick start

```bash
make install   # uv sync + install pre-commit hooks
make up        # start PostgreSQL 16 (docker compose, db only)
make migrate   # alembic upgrade head
make run       # uvicorn with --reload on :8000
make test      # pytest
make lint      # pre-commit run --all-files
make spike     # rerun the design-phase spikes against the compose database
make down      # stop the database
```

Copy `.env.example` to `.env` to override defaults.

## Deliverables map

Where each item the brief asks for lives in this repository.

| Brief | Required content | File |
|---|---|---|
| Part 1: System Design Document | Architecture diagram, component roles, data flow, technologies with justification, observability strategy, GenAI in the design phase | [docs/design.md](docs/design.md), sections 1 to 6 in that order, with a TL;DR on top. Decisions and rejected alternatives: [docs/adr/](docs/adr/README.md) (ADR-001 to ADR-013) |
| Part 1, supporting: design evidence | Code that produced every spike trace cited in the design | [docs/evidence/spike/](docs/evidence/spike/): `schema.sql`, `race.py`, `race_savepoint.py` and their traces; rerun with `make spike` |
| Part 1, supporting: GenAI in the design phase | Pipeline, gates, reviews, verification ledger, defects caught | [docs/ai/README.md](docs/ai/README.md), [docs/ai/verification-ledger.md](docs/ai/verification-ledger.md), [docs/ai/defects-caught.md](docs/ai/defects-caught.md), [docs/ai/reviews/](docs/ai/reviews/review-001.md) |
| Part 2: Backend, API and data layer | Appointment booking API, availability check with no double booking under concurrency, multi-tenant data model | `src/scheduler/`, `migrations/`; API table in design.md section 3; Swagger UI at `/docs` when running |
| Part 2: README, build, run, test | How to build, run and test | This file: Quick start, Running the demo, Testing |
| Part 2: AI Collaboration Narrative | How AI was used in implementation, how its output was verified, what it got wrong | This file, section "AI Collaboration Narrative" (written in the implementation phase), with the evidence in [docs/ai/](docs/ai/README.md) |
| Part 2: Tests validating core logic | Tests for the booking guarantee, retry, idempotency, time rules | `tests/`, run with `make test` |
| Part 3: Video | 5 to 10 minute walkthrough | Link in the submission email and at the top of this file once recorded |

## System design

Read [docs/design.md](docs/design.md) first. The TL;DR gives the whole design in a page; the six sections follow the brief's list. Each decision has an ADR in [docs/adr/](docs/adr/README.md) with the alternatives rejected.

## Design evidence

- `make spike` starts the compose database, creates a separate `spike` database on it and runs both spikes there; the spikes drop and recreate their own tables, so they never touch the application database.
- `race.py` reproduces the first race trace; `race_savepoint.py 8` reproduces savepoint recovery from 23P01 and 40P01.
- A `race_savepoint.py` run that sees no 40P01 exits 2 (inconclusive) and is repeated; 40P01 needs truly simultaneous inserts and does not occur on every run.

## API

Written in the implementation phase.

## Running the demo

Written in the implementation phase.

## Testing

Written in the implementation phase.

## AI Collaboration Narrative

Written in the implementation phase. Design-phase procedure and evidence: [docs/ai/README.md](docs/ai/README.md).

## Quality gates

pre-commit (ruff format and lint, mypy on the application package, gitleaks, whitespace and end-of-file fixers) runs locally; GitHub Actions runs the same configuration plus pytest on every push (ADR-011).
