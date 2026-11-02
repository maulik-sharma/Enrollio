# AGENTS.md

Entry point for anyone — human or AI — working on Enrollio. Read this before
changing code. Coding agents should load it automatically.

## Read order

1. This file (`AGENTS.md`).
2. [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md) — current status, decisions,
   environment quirks, open implementation questions.
3. The current milestone/task in [`docs/plan.md`](docs/plan.md).
4. [`docs/prd.md`](docs/prd.md), [`docs/tech_stack.md`](docs/tech_stack.md), and
   [`docs/testing_strategy.md`](docs/testing_strategy.md) as needed.
5. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the resulting design.

If sources disagree: `docs/plan.md` defines scope, `docs/PROJECT_CONTEXT.md`
defines the current decision and status, `docs/ARCHITECTURE.md` explains the
implementation.

## Non-negotiables

These come from `docs/plan.md` §0.1 and are not optional:

- Work through milestones and tasks **in order**. Do not start a milestone until
  the previous milestone's tests pass.
- Every task ends with **passing tests**. A task is not complete if any test fails.
- Agents never touch the database directly. Agent code calls typed tools in
  `app/agents/tools/`; tools call services; services own business rules.
- Every external provider (email, WhatsApp, calendar, storage, transcription,
  LLM) sits behind an interface with at least one mock. Mocks are the default.
- No secrets in code. Use environment variables through `app/core/config.py`,
  and add every new key to `.env.example` with a comment.
- Schema changes use **Alembic migrations only**, and every migration must be
  reversible.
- Never log PII. Use `app/core/masking.py`; health/readiness and future endpoints
  must not leak emails, phones, transcripts, or message content.
- Do not add features outside the task list. If something seems missing, add it
  to the open-questions section of `docs/PROJECT_CONTEXT.md` and continue.
- Commit after each task with the task ID in the message, e.g.
  `M1.1: users, roles, and permissions`.

## Workflow

### Before starting a task

1. `git status` must be clean; pull or fetch if collaborating.
2. Read the current position in `docs/PROJECT_CONTEXT.md` and the task in
   `docs/plan.md`.
3. Install dependencies if needed: `make install`.
4. Start infrastructure if the task needs it:
   `docker compose up -d --wait db redis` (or `make docker-up` for the full stack).
5. Run the baseline: `make test`.

### While implementing

- Keep the layering: `api/` → `services/` → `repositories/` → `models/`.
  Routers stay thin; writes happen in services.
- Add new providers under `app/integrations/<provider>/` with an interface and a
  mock implementation. Never call a vendor SDK from business logic.
- Add config in `Settings`, then `.env.example`, then code — in that order.
- Put tests at the right layer: pure logic in `tests/unit`, anything touching
  Postgres/Redis/HTTP in `tests/integration`.
- New endpoints need a permission declaration and an unauthorised-role test
  (403; lead-scoped reads return 404 to avoid leaking existence).

### Before committing a task

Run, in order:

```bash
make lint
make typecheck
make test
```

Plus, when the task touches Docker, migrations, or readiness:

```bash
make smoke          # full stack healthy within 120s
```

Then update the living docs **in the same commit**:

- `docs/PROJECT_CONTEXT.md`: move the task to done, add the verification result,
  log new decisions, and record any new open question or risk.
- `docs/ARCHITECTURE.md`: only when the design changed.
- `docs/plan.md` / PRD: do not edit scope; raise questions instead.

Push the task branch and open a pull request; merge only after every CI job
passes (D-038).

Commit with the task ID. Update this file only when the *process* changes, not
for status.

## Where code goes

| Concern | Location |
| --- | --- |
| Configuration and secrets | `backend/app/core/config.py`, `.env.example` |
| Logging, masking, request IDs | `backend/app/core/{logging,masking,middleware}.py` |
| HTTP routers | `backend/app/api/` |
| Business rules and writes | `backend/app/services/` |
| Query helpers | `backend/app/repositories/` |
| SQLAlchemy models | `backend/app/models/` |
| Pydantic schemas | `backend/app/schemas/` |
| Agent orchestrator and typed tools | `backend/app/agents/` |
| Event handlers and rule engine | `backend/app/workflows/` |
| Provider interfaces and adapters | `backend/app/integrations/<provider>/` |
| Celery app and tasks | `backend/app/workers/` |
| Migrations | `backend/migrations/versions/` |
| Backend tests | `backend/tests/{unit,integration,eval}` |
| Frontend app/tests | `frontend/app/`, `frontend/tests/` |
| Opt-in seed data | `backend/app/seed.py` |

## Commands

| Command | Purpose |
| --- | --- |
| `make install` | Backend venv + frontend dependencies |
| `make dev` | API on `:8000` and web on `:3000` |
| `make test` | Backend pytest + frontend Vitest |
| `make test-e2e` | Playwright auth flows (needs the API on `:8000` and seeded demo users) |
| `make lint` | ruff, mypy, ESLint |
| `make typecheck` | mypy + `tsc --noEmit` |
| `make migrate` | Apply Alembic migrations |
| `make seed` | Load seed data (no-op until M1.1) |
| `make smoke` | Compose stack healthy within 120s |
| `make docker-up` / `docker-down` | Start/stop the full stack |

## Conventions

- **Commits:** `<task-id>: <summary>` (e.g. `M2.3: CSV/XLSX import pipeline`).
  One task per commit. Do not mix refactors into a feature commit.
- **Branches:** one branch and pull request per task; merge only when the full CI
  run is green (D-038). Never commit a task directly to `main`.
- **Python:** 3.12, type hints on public functions, ruff + mypy strict must pass.
- **Frontend:** TypeScript strict, App Router, Tailwind. Add libraries only when
  the milestone needs them.
- **API paths:** `/api/<domain>` for authenticated endpoints, `/api/public/...`
  for public ones, `/api/webhooks/...` for provider callbacks.
- **Errors:** reject with explicit domain errors; never leak existence of
  resources the caller cannot access.

## Do not

- Do not edit `docs/plan.md`, `docs/prd.md`, or `docs/testing_strategy.md` to make
  an implementation easier. Record the gap and ask.
- Do not hand-edit database tables or commit generated SQL dumps.
- Do not commit `.env`, credentials, recordings, or student data.
- Do not call provider SDKs outside `app/integrations/`.
- Do not mark a task done with skipped tests unless the only reason is missing
  local infrastructure — and then say so in `PROJECT_CONTEXT.md` and let CI run
  them.
