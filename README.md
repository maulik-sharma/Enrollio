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

## Layout

- `backend/` — FastAPI, SQLAlchemy 2.0 async, Alembic, Celery.
- `frontend/` — Next.js 15 App Router, TypeScript, Tailwind, Vitest.
- `docs/` — product requirements, plan, testing strategy, architecture.
- `docker-compose.yml` — local full stack.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for configuration, logging, and
testing details.
