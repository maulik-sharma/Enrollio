# Enrollio

An agentic CRM that takes every admission enquiry from first contact to fee
payment with counsellors in the loop.

## Status

Milestone M0 (foundation) is implemented: repository tooling, Docker Compose
stack, typed configuration, structured logging with PII masking, readiness
probes, and CI. Domain features start at M1.

## Quick start

```bash
cp .env.example .env          # local defaults; all providers stay mocked
make install                  # backend venv + frontend node_modules
make docker-up                # api, web, worker, db, redis, minio
```

- Web: <http://localhost:3000>
- API: <http://localhost:8000>
- API docs: <http://localhost:8000/docs>
- MinIO console: <http://localhost:9001>

The API container applies Alembic migrations before starting.

To run only the app processes (requires PostgreSQL and Redis on localhost):

```bash
make migrate
make seed
make dev
```

## Common commands

| Command | Purpose |
| --- | --- |
| `make dev` | Run the API (`:8000`) and web (`:3000`) dev servers together |
| `make test` | Backend pytest + frontend Vitest |
| `make lint` | ruff, mypy, ESLint |
| `make typecheck` | mypy + `tsc --noEmit` |
| `make migrate` | `alembic upgrade head` |
| `make seed` | Seed data (roles arrive in M1.1) |
| `make smoke` | Assert the Compose stack is healthy within 120s |
| `make docker-down` | Stop the stack and remove volumes |

## Working on the project

1. Read [`AGENTS.md`](AGENTS.md) — the mandatory workflow, rules, and commands.
2. Read [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md) — current status,
   decisions, environment quirks, risks, and open questions.
3. Pick the next task from [`docs/plan.md`](docs/plan.md).

Every task commit **must** update `docs/PROJECT_CONTEXT.md` (status, decisions,
verification) and add the task ID to the commit message. The PR checklist in
[`.github/pull_request_template.md`](.github/pull_request_template.md) enforces
the rest.

## Layout

- `backend/` — FastAPI, SQLAlchemy 2.0 async, Alembic, Celery.
- `frontend/` — Next.js 15 App Router, TypeScript, Tailwind, Vitest.
- `docs/` — requirements, plan, testing strategy, architecture, project context.
- `AGENTS.md` — contributor and coding-agent rules.
- `docker-compose.yml` — local full stack.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for configuration, logging, and
testing details.
