# SPEC-001 T1 audit

Task: T1 — Dependencies, package skeleton, layer-rule test
Base: `f0f41174f5b666119de9b7857525b6418c571012`
Head sha: `7aad8fe6b793e60b1ebedf5b51ce82a3d32c58ca`
Date: 2026-11-04
Reviewer: Codex

Verdict: pass

## Findings

Cycle 4: None.

## Evidence

- T1-path-scoped `git diff --name-status f0f41174f5b666119de9b7857525b6418c571012..7aad8fe6b793e60b1ebedf5b51ce82a3d32c58ca` contains only the approved T1 paths: `pyproject.toml`, `uv.lock`, the six package `__init__.py` files, `tests/test_architecture.py`, and `docs/ai/specs/SPEC-001-status.md`.
- `pyproject.toml` runtime dependencies are exactly `fastapi`, `uvicorn[standard]`, `psycopg[binary,pool]`, `sqlalchemy[asyncio]>=2`, `greenlet`, `alembic`, and `pydantic-settings`; no other runtime dependency was added. `uv.lock` resolves that declaration.
- `uv run pytest tests/test_architecture.py -q` — `3 passed in 0.03s`.
- Temporary probes `domain/__audit_probe_fastapi.py` (`import fastapi`) and `application/__audit_probe_infrastructure.py` (`from scheduler.infrastructure import probe`) — `1 failed, 2 passed`; the failure reported both forbidden edges. Both probe files were deleted. Post-cleanup rerun: `3 passed in 0.03s`.
- `uv run pre-commit run --all-files` — all hooks passed, including ruff, format, secrets, and mypy.
- `uv run mypy src` — `Success: no issues found in 16 source files`.
- `git diff --check f0f41174f5b666119de9b7857525b6418c571012..7aad8fe6b793e60b1ebedf5b51ce82a3d32c58ca` — no output.
- T1 commits `a919ea6`, `ca49db0`, `1d24569`, and `7aad8fe` use the required `SPEC-001 T1: ... (design §4, D-041)` subject form and include `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- `docs/ai/specs/SPEC-001-status.md` contains the required `# SPEC-001 implementation status` header and a `## T1` section.
- Import-form coverage (Cycle 4): `import module` (including dotted targets and `as` aliases) is collected from `ast.Import` at lines 40-41; absolute `from module import name` is collected from `ast.ImportFrom` at lines 42-52; `from scheduler import infrastructure, interfaces` (including aliases) expands each imported root-layer alias at lines 48-50; valid relative imports at every level resolve from the importing file's package at lines 43-45, and relative package-root aliases then use the same expansion. `__import__` and `importlib` are out of scope. Thus each requested static import form is covered before AC-14 edge checks at lines 67-75 and the main-only outer-layer check at lines 79-91.
