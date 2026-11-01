# Project Context

**Living handoff document.** Read this before starting work and update it before
committing every task. It records what is done, what was decided and why, how the
project is operated, and what is still open.

- **Last updated:** 2026-11-01, after the M0 task commits (last code commit `7c5a9e7`)
- **Current position:** M0 complete → **next task M1.1**
- **Maintainers:** every contributor, in the same commit as the task

## 1. How to use this file

- **Read it first.** Workflow rules are in [`../AGENTS.md`](../AGENTS.md); scope is
  in [`plan.md`](plan.md); design details are in [`ARCHITECTURE.md`](ARCHITECTURE.md).
- **Update it in the task's commit**, not in a separate "docs" commit afterwards.
- Status sections are overwritten. The decision log is **append-only**: never
  rewrite or delete an entry; mark it `superseded by D-0xx` and add a new one.
- Product/college questions belong in
  [`open_questions_next_steps.md`](open_questions_next_steps.md). Engineering
  questions belong in §8 here.
- Keep it short. Link to code and docs instead of copying them.

## 2. Status

| Milestone | Status | Notes |
| --- | --- | --- |
| M0 Foundation | ✅ Complete | Verified locally against Docker on 2026-11-01 |
| M1 Identity and RBAC | ⬜ Not started | Next: M1.1 data model for users/roles/permissions |
| M2 Lead CRM and ingestion | ⬜ Not started | |
| M3 Communication and campaigns | ⬜ Not started | |
| M4 Knowledge, RAG, enquiry agent | ⬜ Not started | |
| M5 Scheduling and assignment | ⬜ Not started | |
| M6 Lead/conversation intelligence | ⬜ Not started | |
| M7 Follow-up, SLAs, audit | ⬜ Not started | |

### M0 task detail

| Task | Status | What exists |
| --- | --- | --- |
| M0.1 Repository and tooling | ✅ | Backend (Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic, pytest, ruff, mypy), frontend (Next.js 15 App Router, TS, Tailwind 4, ESLint, Vitest), Makefile |
| M0.2 Docker Compose environment | ✅ | `api`, `web`, `worker`, `db` (pgvector/pg16), `redis`, `minio`; extension migration; `/healthz` + `/readyz`; smoke script |
| M0.3 Configuration and secrets | ✅ | `core/config.py`, `.env.example`, production fail-fast, mock flags |
| M0.4 Logging and PII masking | ✅ | JSON logs, request IDs, masking filter on all handlers |
| M0.5 CI pipeline | ✅ written / ⚠️ not executed | Workflow for lint, types, tests with PG+Redis services, frontend build, Docker builds; requires a push |

### Verification snapshot (2026-11-01)

```text
make lint                 pass (ruff, ruff format --check, mypy, eslint)
make typecheck            pass (mypy strict, tsc --noEmit)
make test                 33 backend tests pass, 1 frontend test passes
make migrate              pass (0001 applied)
make seed                 pass (no-op until M1.1)
make smoke                6/6 services healthy within 120s
docker compose build      backend + web images build
GET /readyz               200 with PG+Redis up
GET /readyz               HTTP 503 with the db container stopped, 200 after restart
GET /healthz              200
GET localhost:3000        200
```

Reproduce integration tests:

```bash
docker compose up -d --wait db redis
make migrate
make test-backend
docker compose down -v
```

Without Postgres/Redis the integration tests **skip** (see §6); CI supplies both.

## 3. Decisions log

Append-only. Each entry states the decision, why, and the alternative that was
not taken.

| ID | Decision | Why | Alternatives rejected |
| --- | --- | --- | --- |
| D-001 | Python 3.12 with `pip` + `venv` + `requirements*.txt`; `pyproject.toml` holds tool config only | Team preference; simple, universally understood | uv, Poetry |
| D-002 | npm for the frontend | Already installed; no extra tooling | pnpm |
| D-003 | M0 frontend is minimal (Next, TS, Tailwind, ESLint, Vitest); no shadcn/ui, TanStack Query, RHF, or Zod yet | Do not install libraries before a milestone needs them | Full stack at M0 |
| D-004 | Providers are generic enums (`mock`, `openai`, `anthropic`, `ses`, `sendgrid`, …) and `USE_MOCK_*` flags are authoritative; mocks are default and no vendor SDK is installed | M3/M4 provider choice is still open; keeps tests hermetic | Commit to OpenAI+SES now |
| D-005 | One `.env` at the repository root, read by both the backend and Compose | Avoids two env files drifting apart | Separate `backend/.env` |
| D-006 | `minio` service uses `pgsty/minio:RELEASE.2026-08-04T00-00-00Z` | MinIO removed official Docker Hub images (404) and quay.io now returns 401; the PIGSTY mirror keeps real MinIO behaviour | adobe/s3mock, bitnamilegacy/minio, SeaweedFS |
| D-007 | Keep existing doc filenames (`prd.md`, `open_questions_next_steps.md`); add `ARCHITECTURE.md` | Avoid churn in documents already written | Rename to plan's uppercase names |
| D-008 | One local commit per task, task ID in the message; no push/PR yet | User choice while pre-release; CI verifies nothing until pushed | Branch + PR per task |
| D-009 | `/readyz` checks PG and Redis with a 2s budget; integration tests auto-skip when they are unreachable | Local runs without infra stay green; CI runs everything | Hard-fail without infrastructure |
| D-010 | Health endpoints are public and excluded from OpenAPI; no auth until M1 | Correct for M0 scope; probes must not require credentials | Token-protected probes |
| D-011 | Compose uses `minioadmin`/`enrollio` dev credentials as defaults; real deployments must override them | Local one-command startup; `.env` is gitignored | Forcing users to create secrets |
| D-012 | `AGENTS.md` + this file are the shared context; every task updates this file | Prevent multiple contributors/agents from diverging | Rely on chat history / architecture doc alone |

## 4. Architecture in one paragraph

One FastAPI modular monolith plus one Celery worker, Postgres 16 (pgvector,
excluded constraints later), Redis for Celery, and S3-compatible object storage.
Code is layered API → services → repositories → models. LLM/agent code only calls
typed tools, which call services. Every external provider has an interface and a
mock. Frontend is a separate Next.js app. Full detail:
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## 5. Environment and quirks

- **Python:** 3.12.15 interpreter installed via `uv python install 3.12` and
  exposed as `python3.12`; dependencies live in `backend/.venv` (pip). `uv` is
  only used to obtain the interpreter.
- **Node:** 22; npm 9. Frontend dependencies are locked by
  `frontend/package-lock.json`.
- **Docker:** the Linux user must be in the `docker` group (or have socket
  access); otherwise compose commands fail with a permission error.
- **Ports (host):** web 3000, API 8000, Postgres 5432, Redis 6379, MinIO 9000
  (console 9001). Compose project name: `enrollio`.
- **Compose startup order:** `db`/`redis`/`minio` healthy → `api` runs
  `alembic upgrade head` then Uvicorn → `web` waits for healthy `api`.
- **MinIO:** official images are unavailable; see D-006. `curl` exists in the
  pinned image, which the healthcheck relies on.
- **Integration test detection:** `backend/tests/conftest.py` probes the host/port
  of `TEST_DATABASE_URL`/`TEST_REDIS_URL` (falling back to
  `DATABASE_URL`/`REDIS_URL`, then localhost) and skips if closed.
- **Seed:** `make seed` is a deliberate no-op until M1.1 adds roles.
- **Local `.env`:** created from `.env.example`; it is gitignored and must stay
  that way.

## 6. How things are done

Details live in [`ARCHITECTURE.md`](ARCHITECTURE.md); this is the quick version.

- **Config:** add fields to `Settings`, then to `.env.example` with a comment,
  then use them. Production fails fast on missing/placeholder secrets. Never read
  raw secrets with `os.getenv` inside business code.
- **Logging:** use module loggers; pass structured data via `extra=`. Never log
  message bodies, emails, phones, or transcripts. `PIIMaskingFilter` is installed
  on the root handler; add tests when logging new shapes of data.
- **Migrations:** generate with Alembic, keep `downgrade()` real, confirm
  upgrade/downgrade on a scratch database.
- **Tests:** unit tests are pure and require no infra; integration tests carry
  `@pytest.mark.integration` and use real Postgres/Redis. Frontend tests use
  Vitest + Testing Library under `frontend/tests/`.
- **Providers:** interface + mock under `app/integrations/<provider>/`; real
  adapter disabled by default. Downstream code depends on the interface only.
- **Frontend:** App Router, TypeScript strict, Tailwind utilities. API calls will
  enter through `lib/` once M1.5 introduces the client.
- **Git:** `Mx.y: summary`; never mix unrelated refactors into a task commit.

## 7. Known risks and pending fixes

| ID | Risk / gap | Action |
| --- | --- | --- |
| R-001 | **Integration tests use the dev database.** Once tables exist, `test_migrations.py`'s `downgrade base` will delete dev data | Fix **before M1.1 adds tables**: use a dedicated `enrollio_test` database via `TEST_DATABASE_URL`, create it in Compose/CI, and make the migration test require it |
| R-002 | `docs/plan.md` M0.5's "deliberately failing test" gate has never run, because nothing is pushed | Keep the workflow green locally; verify on the first push/PR (see Q-003) |
| R-003 | MinIO is served by a third-party mirror | Tag is pinned; image only exposes the S3 API. If unavailable, switch to another S3-compatible image (D-006) |
| R-004 | No authentication or RBAC yet | Do not expose the API beyond localhost until M1 lands |
| R-005 | Provider choices for M3/M4 are undecided | Answer Q-001 before M3.1; mocks keep progress unblocked |
| R-006 | CI has no secret scanning, dependency audit, or coverage gate yet | Add when the plan's security/testing tasks require it; not M0 scope |
| R-007 | `docs/plan.md` M0 requires Python 3.12 but the host ships 3.14 | The 3.12 interpreter is installed via uv; document this for new machines |

## 8. Open implementation questions

These are engineering decisions; product/college questions stay in
[`open_questions_next_steps.md`](open_questions_next_steps.md).

| ID | Question | Needed by |
| --- | --- | --- |
| Q-001 | Which real LLM provider (primary + fallback) and email provider should be the first non-mock adapters? | M3.1 / M4.4 |
| Q-002 | Confirm the test-database strategy in R-001 (separate local DB vs testcontainers) | Before M1.1 |
| Q-003 | When do we push the repository and switch to per-task branches so CI and the M0.5 gate actually run? | Before the first collaborative change |
| Q-004 | If the PIGSTY MinIO mirror disappears, which S3-compatible image is the fallback? | When D-006 needs revisiting |
| Q-005 | Should `make dev` eventually run migrations automatically, or stay explicit (`make migrate`)? | M1.1 |

## 9. Update template

Copy this into §2/§10 when completing a task:

```markdown
### Task <ID> — <name> (<YYYY-MM-DD>)

- Status: done | blocked
- Commit: <hash>
- Verification: `make lint` pass · `make typecheck` pass · `make test` <N> pass
- Decisions: D-0xx (or "none")
- Docs touched: ARCHITECTURE / plan / none
- Notes or new risks: <text>
```

Checklist for every task commit:

- [ ] Task is marked done and its verification line is recorded.
- [ ] New decisions appended with an ID and rationale.
- [ ] New risks/open questions added, resolved ones marked.
- [ ] `ARCHITECTURE.md` updated if the design changed.
- [ ] Current position points at the next task.
- [ ] `.env.example` updated for any new configuration.
- [ ] Commit message starts with the task ID.

## 10. Change log

| Date | Change |
| --- | --- |
| 2026-11-01 | Context system created (`AGENTS.md` + this file). Milestone M0 recorded as complete; M1.1 identified as next. |
