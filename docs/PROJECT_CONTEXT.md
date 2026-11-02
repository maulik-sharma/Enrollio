# Project Context

**Living handoff document.** Read this before starting work and update it before
committing every task. It records what is done, what was decided and why, how the
project is operated, and what is still open.

- **Last updated:** 2026-11-02, after `M1.5` (frontend authentication shell)
- **Current position:** M0 complete · **M1 complete** → **next task M2.1**
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
| M1 Identity and RBAC | ✅ Complete | M1.0–M1.5 complete; authenticated shell ships with role-aware navigation |
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
| M0.5 CI pipeline | ✅ written / ⚠️ not executed | Workflow for lint, types, tests with PG+Redis services, frontend build, Playwright e2e, Docker builds; requires a push |

### M1 task detail

| Task | Status | What exists |
| --- | --- | --- |
| M1.0 Test database isolation (R-001) | ✅ | `enrollio_test` created by Compose init / `make create-test-db`; `TEST_DATABASE_URL`; destructive migration test refuses non-`_test` databases; sentinel test proves the dev database survives |
| M1.1 Users, roles, permissions | ✅ | Migration `0002`; 17 permissions and 3 roles in `app/core/permissions.py`; idempotent `make seed`; Argon2id password hashing; three dev demo accounts |
| M1.2 Authentication | ✅ | Migration `0003` (lockout columns, `refresh_tokens`); JWT access tokens; opaque rotating refresh tokens in an HttpOnly/Secure/SameSite=Strict cookie scoped to `/api/auth`; login, refresh, logout, `/api/auth/me`; 5-failure lockout with generic 401; CORS for the web app |
| M1.3 Permission enforcement | ✅ code / ⚠️ lead gate deferred | `require_permission` (403) in `app/api/deps.py`; `can_access_lead` in `app/services/access.py` (view-all vs assigned-only); unit + API tests. The real cross-counsellor DB test needs `leads` and moves to M2.1 (Q-006) |
| M1.4 User and role administration | ✅ | `GET/POST /api/users`, `PATCH /api/users/{id}`, `POST /api/users/{id}/deactivate`, `GET /api/roles`, `PUT /api/roles/{id}/permissions`; services normalise email, validate roles/permissions, revoke sessions on deactivation or password change; 403/404/409/400 tests |
| M1.5 Frontend authentication shell | ✅ | `/login`, client-side protected shell, in-memory access token with refresh-on-401, role-aware navigation from the permission list, logout; Vitest nav tests and 4 Playwright flows (three roles + invalid login) |

### Verification snapshot (2026-11-01)

```text
make lint                 pass (ruff, ruff format --check, mypy, eslint)
make typecheck            pass (mypy strict, tsc --noEmit)
make test                 93 backend tests pass, 4 frontend tests pass
make test-e2e             4 Playwright flows pass (three roles + invalid login)
make migrate              pass (0003 applied)
make migrate-test         pass (0003 applied to enrollio_test)
make seed                 pass (3 roles, 17 permissions, 3 demo users; idempotent)
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
make create-test-db
make migrate
make migrate-test
make test-backend
docker compose down -v
```

Without Postgres/Redis the integration tests **skip**; in CI they fail instead
so a broken service container cannot pass silently. The migration test always
uses `TEST_DATABASE_URL` and refuses a database whose name does not end in
`_test` (R-001).

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
| D-013 | Integration tests use a dedicated `enrollio_test` database via `TEST_DATABASE_URL`; there is no fallback to `DATABASE_URL`, and destructive migration tests fail unless the database name ends in `_test` | Makes R-001 impossible: `make test` can no longer wipe development data | Shared database, testcontainers |
| D-014 | Locally, unreachable Postgres/Redis skips integration tests; when `CI=true` the same condition fails | Keeps laptops usable without Docker while preventing a silent CI pass | Always skip, always fail |
| D-015 | The RBAC catalog lives in `app/core/permissions.py`: 17 permissions taken verbatim from PRD §4, three roles, exact matrix; the seed writes this catalog and replaces role-permission links for seeded roles | One source of truth for tests, seed, and future `require_permission` checks; PRD is the authority | Permissions scattered across routers; wildcard admin |
| D-016 | Identity tables use UUID v4 primary keys (`gen_random_uuid()`), `timestamptz` timestamps, and lowercased unique emails enforced by a CHECK; services normalise before writing | Stable public identifiers, deterministic ordering, and case-insensitive login without a `citext` dependency | Bigint IDs, `citext` |
| D-017 | `make seed` also creates three `@enrollio.dev` demo accounts (admin, manager, counsellor) with one `SEED_DEMO_PASSWORD`, only when `SEED_DEMO_USERS` is true and never in production | M1.5 needs three roles to demonstrate different menus; avoids a manual setup step | Roles only; separate fixture script |
| D-018 | Argon2id parameters are settings (`ARGON2_*`); tests lower them, production defaults stay at 3 passes / 64 MiB / 4 lanes | Real hashing in production without a slow test suite | Hardcoded parameters |
| D-019 | Access tokens are 15-minute HS256 JWTs (`sub`, `type=access`, `jti`, `iat`, `exp`, `iss=enrollio`); the frontend keeps them in memory only | Short blast radius and no XSS-readable long-lived credential; the frontend refreshes on load and on 401 | Long-lived JWT in `localStorage`; server-side sessions |
| D-020 | Refresh tokens are opaque 256-bit values; only their SHA-256 hash is stored. Each login starts a family; refresh rotates the token and links `replaced_by_id`. Reusing an already-rotated token revokes the whole family | Database leaks expose no usable token; rotation plus reuse detection catches stolen cookies | JWT refresh tokens; non-rotating opaque tokens |
| D-021 | The refresh token travels in an HttpOnly, Secure, SameSite=Strict cookie scoped to `path=/api/auth`; logout clears it and revokes the family | JavaScript cannot read it, cross-site requests do not carry it, and it is only sent to the two endpoints that need it | Token in the response body; `SameSite=Lax` |
| D-022 | Lockout is stored on `users` (`failed_login_count`, `last_failed_login_at`, `locked_until`): 5 failures inside 15 minutes locks for 15 minutes; every rejection returns the same generic 401 and unknown emails pay the same Argon2 cost | No extra store to operate; responses and timing do not reveal whether an account exists | Redis counters; distinct "locked" responses |
| D-023 | Demo accounts moved from `@example.test` to `@enrollio.dev`; seeding deletes the three legacy demo rows | `EmailStr` rejects special-use/reserved domains such as `.test`, so login validation rejected the seeded users; deleting the old rows keeps an existing dev database at one account per role | Disabling email validation; `@example.com` |
| D-024 | Endpoints declare `require_permission("<name>")`; a missing permission is **403**. Resource scoping is separate: `can_access_lead` decides read access and the API maps denial to **404** | Missing permission is a property of the role, but a lead the caller cannot see must not be distinguishable from a missing one | 404 for permission denial; filtering in the frontend |
| D-025 | `can_access_lead` lives in `app/services/access.py` and takes a structural `AssignedLead` protocol instead of the M2 model | The rule is pure and testable now; M2.1's `Lead` model satisfies the protocol, so the helper does not change when the table arrives | Waiting for the `leads` table; duplicating the rule per service |
| D-026 | User administration lives in `app/services/users.py`; routers only translate domain errors (`EmailAlreadyExists`→409, `UnknownRole`/`UnknownPermission`→400, missing→404). `GET /api/users` and `GET /api/roles` need `users.manage`; `PUT /api/roles/{id}/permissions` needs `roles.manage` | The role picker is part of user administration, but changing the matrix is a separate privilege; domain errors stay HTTP-free | HTTP exceptions inside services; a single admin-only gate |
| D-027 | Deactivating a user or changing their password revokes every refresh token for that user; the next request with an existing access token is rejected because `get_current_user` reloads the user | Deactivation and credential changes must end sessions immediately, not when the access token expires | Waiting for token expiry; blacklists |
| D-028 | The frontend keeps the access token in memory only and restores a session on load by calling `/api/auth/refresh` (via the HttpOnly cookie); `apiRequest` retries once after a 401 | No credential is readable from JavaScript and reloads still work | `localStorage`, which an XSS bug could exfiltrate |
| D-029 | Route protection is a client-side guard (`RequireAuth`); the API remains the security boundary | M1 has no server-rendered private data; every API call is authenticated and permission-checked server-side (D-024) | Server middleware now, which would need a token design change |
| D-030 | Frontend configuration lives in `frontend/.env.example` (`NEXT_PUBLIC_API_URL`), not the root `.env.example`; the browser defaults to `http://localhost:8000` | The root file has an exact-key parity test against backend `Settings` | Relaxing the parity test; passing browser URLs through the backend |
| D-031 | Playwright runs in its own CI job with Postgres, Redis, a migrated and seeded dev database, Uvicorn on `:8000`, and Chromium; the report is uploaded on failure; `make test-e2e` runs it locally | The e2e flow needs a real session and the httpOnly cookie; mocked auth would not prove the integration | Testing only the frontend with mocked fetch |

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
  of `TEST_DATABASE_URL`/`TEST_REDIS_URL` (Redis falls back to `REDIS_URL`) and
  skips if closed. The database never falls back to `DATABASE_URL`; its name must
  end in `_test`. Use `make create-test-db` once per fresh volume and
  `make migrate-test` after adding migrations.
- **Seed:** `make seed` upserts the RBAC catalog and creates the three demo
  accounts. It is idempotent; `SEED_DEMO_USERS=false` keeps accounts out.
- **Demo logins:** `admin@enrollio.dev`, `manager@enrollio.dev`,
  `counsellor@enrollio.dev` with `SEED_DEMO_PASSWORD`. `.dev` is used because
  `EmailStr` rejects `.test` (D-023).
- **Auth cookies:** the refresh cookie is `Secure`, so browsers only send it over
  HTTPS or to `localhost`. API tests use an `https://test` base URL for that
  reason.
- **Frontend API URL:** `NEXT_PUBLIC_API_URL` lives in `frontend/.env.example`
  and defaults to `http://localhost:8000`. Copy it to `frontend/.env.local` only
  when the backend is elsewhere; the root `.env` does not hold browser values.
- **End-to-end:** with the API running on `:8000` and demo users seeded,
  `make test-e2e` runs Playwright (it starts Next.js itself). `SEED_DEMO_PASSWORD`
  must match the backend; it defaults to `dev-only-password`.
- **Authorisation:** protected endpoints take `Depends(require_permission(...))`
  and return 403 when the role lacks it; resource checks use
  `can_access_lead`/equivalent and return 404 on denial. See §6.
- **User administration:** `services/users.py` and `services/roles.py` own the
  rules; routers translate `EmailAlreadyExists`→409, `UnknownRole`/
  `UnknownPermission`→400, and not-found→404. Deactivation and password changes
  revoke every refresh token.
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
- **Frontend:** App Router, TypeScript strict, Tailwind utilities. API calls go
  through `lib/api.ts`; authentication state lives in `components/auth-provider.tsx`;
  navigation items and their permissions in `lib/navigation.ts`.
- **Git:** `Mx.y: summary`; never mix unrelated refactors into a task commit.

## 7. Known risks and pending fixes

| ID | Risk / gap | Action |
| --- | --- | --- |
| R-001 | ~~**Integration tests use the dev database.**~~ **Resolved by D-013 (M1.0).** Tests now use `enrollio_test`, the migration test refuses non-`_test` names, and a sentinel test proves the dev database survives | Done; keep the guard |
| R-002 | `docs/plan.md` M0.5's "deliberately failing test" gate has never run, because nothing is pushed | Keep the workflow green locally; verify on the first push/PR (see Q-003) |
| R-003 | MinIO is served by a third-party mirror | Tag is pinned; image only exposes the S3 API. If unavailable, switch to another S3-compatible image (D-006) |
| R-004 | ~~**No authentication or RBAC.**~~ **Resolved in M1.2–M1.3:** authentication is live and `require_permission`/`can_access_lead` are available. No data endpoint exists yet, so nothing is exposed | Apply both to every endpoint starting with M1.4; cross-counsellor DB gate tracked as Q-006 |
| R-005 | Provider choices for M3/M4 are undecided | Answer Q-001 before M3.1; mocks keep progress unblocked |
| R-006 | CI has no secret scanning, dependency audit, or coverage gate yet | Add when the plan's security/testing tasks require it; not M0 scope |
| R-007 | `docs/plan.md` M0 requires Python 3.12 but the host ships 3.14 | The 3.12 interpreter is installed via uv; document this for new machines |
| R-008 | The last System Admin can deactivate themselves or strip `users.manage`/`roles.manage` from `system_admin`, leaving no one able to administer the system | Add the guard decided in Q-007 before any shared deployment; acceptable for local development |
| R-009 | The frontend route guard is cosmetic: a user can open any `/sections/*` URL | Routes render no data; every API call is authorised server-side. Never move access checks into the UI only |

## 8. Open implementation questions

These are engineering decisions; product/college questions stay in
[`open_questions_next_steps.md`](open_questions_next_steps.md).

| ID | Question | Needed by |
| --- | --- | --- |
| Q-001 | Which real LLM provider (primary + fallback) and email provider should be the first non-mock adapters? | M3.1 / M4.4 |
| Q-002 | ~~Confirm the test-database strategy in R-001~~ **Resolved in M1.0:** dedicated `enrollio_test` database (D-013) | — |
| Q-003 | When do we push the repository and switch to per-task branches so CI and the M0.5 gate actually run? | Before the first collaborative change |
| Q-004 | If the PIGSTY MinIO mirror disappears, which S3-compatible image is the fallback? | When D-006 needs revisiting |
| Q-005 | Should `make dev` eventually run migrations automatically, or stay explicit (`make migrate`)? | M1.1 |
| Q-006 | **Deferred security gate:** `docs/plan.md` M1.3's cross-counsellor integration test (counsellor A gets 404 for counsellor B's lead; manager reads any lead) needs the `leads` table, which arrives in M2.1. `can_access_lead` and `require_permission` are implemented and unit/API tested now | M2.1 — must land before any lead endpoint is exposed |
| Q-007 | Should the API prevent deactivating or demoting the last active System Admin (and stripping `users.manage`/`roles.manage` from `system_admin`)? | Before a shared deployment (R-008) |

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
| 2026-11-01 | M1.0: dedicated `enrollio_test` database, destructive-migration guard, CI/Compose creation, isolation test. R-001 and Q-002 resolved. |
| 2026-11-01 | M1.1: users/roles/permissions migration, permission catalog and role matrix, idempotent seed, Argon2id hashing, demo accounts. |
| 2026-11-02 | M1.2: JWT access tokens, rotating opaque refresh tokens in an HttpOnly cookie, login/refresh/logout/me endpoints, lockout, CORS, demo emails moved to `@enrollio.dev`. |
| 2026-11-02 | M1.3: `require_permission` (403), `can_access_lead` scoping (view-all vs assigned-only), unit and API tests. Real cross-counsellor DB test deferred to M2.1 as Q-006. |
| 2026-11-02 | M1.4: user CRUD/deactivation and role permission APIs, session revocation on deactivation/password change, HTTP mappings and tests. Last-admin guard recorded as R-008/Q-007. |
| 2026-11-02 | M1.5: login page, protected shell, in-memory token with refresh-on-401, role-aware navigation, logout; Vitest and Playwright suites; e2e CI job. **Milestone M1 complete.** |
