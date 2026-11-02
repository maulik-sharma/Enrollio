# Architecture

> Status: Milestones M0, M1, and M2.1 (foundation, identity, lead CRM schema).
> This document is updated as milestones land.

## 1. Repository layout

```text
.
├── backend/                 # FastAPI application (Python 3.12)
│   ├── app/
│   │   ├── core/            # config, logging, masking, database, Redis, domain enums
│   │   ├── api/             # HTTP routers (health today, domain routers later)
│   │   ├── models/          # SQLAlchemy 2.0 models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # business rules and writes
│   │   ├── repositories/    # query helpers
│   │   ├── agents/          # LLM orchestrator and typed tools
│   │   ├── workflows/       # event handlers and rules
│   │   ├── integrations/    # provider interfaces and adapters
│   │   └── workers/         # Celery application and tasks
│   ├── migrations/          # Alembic environment and versions
│   ├── tests/               # unit, integration, eval, fixtures
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
├── frontend/                # Next.js 15 App Router (TypeScript, Tailwind 4)
│   ├── app/                 # routes: `/`, `/login`, `/sections/[slug]`
│   ├── components/          # auth provider, protected shell, navigation
│   ├── lib/                 # API client, types, navigation catalog
│   ├── tests/               # Vitest
│   └── e2e/                 # Playwright
├── docker-compose.yml       # api, web, worker, db, redis, minio
├── Makefile                 # dev, test, lint, migrate, seed, smoke
├── .env.example
├── AGENTS.md                # workflow rules for contributors and agents
└── docs/
    ├── PROJECT_CONTEXT.md   # living status, decisions, risks, handoff
```

The plan's Section 0.2 tree is respected, with one deliberate deviation: Python
dependencies are managed with `pip` + `venv` + `requirements.txt` (team
decision), while `pyproject.toml` holds only tool configuration.

## 2. Runtime topology

| Service | Image / build | Host port | Purpose |
| --- | --- | --- | --- |
| `db` | `pgvector/pgvector:pg16` | 5432 | PostgreSQL 16 with pgvector |
| `redis` | `redis:7-alpine` | 6379 | Celery broker/result backend |
| `minio` | `pgsty/minio:RELEASE.2026-08-04T00-00-00Z` | 9000 / 9001 | S3-compatible object storage |
| `api` | `backend/Dockerfile` | 8000 | FastAPI; runs migrations then Uvicorn |
| `worker` | `backend/Dockerfile` | – | Celery worker |
| `web` | `frontend/Dockerfile` | 3000 | Next.js production server |

The API waits for healthy `db`, `redis`, and `minio`. The web app waits for a
healthy API. `make smoke` asserts every service is healthy within 120 seconds.

> **MinIO image note:** MinIO's official images were removed from Docker Hub
> (`minio/minio` now returns 404) and `quay.io/minio/minio` requires
> authentication. Compose uses the PIGSTY mirror, pinned to a release tag. If
> the mirror becomes unavailable, swap the tag for another MinIO mirror or a
> different S3-compatible server; the application only depends on the S3 API.

## 3. Configuration

`app/core/config.py` defines a single Pydantic Settings model. Values are read
from environment variables and, for local development, the repository-root
`.env` (`.env.example` is the canonical template).

Rules:

- `USE_MOCK_<PROVIDER>=true` selects the in-process mock adapter. Mocks are the
  default for every provider: email, WhatsApp, calendar, LLM, speech, storage.
- The `*_PROVIDER` values name the real adapter used when its mock flag is
  disabled. Real credentials are only required when the corresponding mock flag
  is false.
- In `ENV=production`, startup fails if `JWT_SECRET` is missing or still a
  placeholder, if `SEED_DEMO_USERS` is true, or if a real provider is selected
  without credentials.
- Secrets are never committed. `.env` is ignored by Git; `.env.example` holds
  placeholders only.

## 4. Health and readiness

- `GET /healthz` — liveness. Always returns `200` with `{"status": "ok"}`.
- `GET /readyz` — readiness. Pings PostgreSQL (`SELECT 1`) and Redis (`PING`)
  with a 2-second budget and returns `200` when both succeed, otherwise `503`
  with per-dependency booleans.

Both endpoints are excluded from the OpenAPI schema.

## 5. Logging and PII

Logging is structured JSON on stdout. Every record includes a timestamp, level,
logger, message, and (when inside a request) a `request_id`. A request ID is
accepted from `X-Request-ID` when it matches `[A-Za-z0-9_-]{1,128}`, otherwise
generated, and is returned in the response header.

`PIIMaskingFilter` is installed on the root handler and rewrites every record:

| Data | Output |
| --- | --- |
| `rahul.sharma@gmail.com` | `r***@gmail.com` |
| `+91 98765 43210` | `98XXXX3210` |
| sensitive fields (`transcript`, `notes`, `content`, …) | `[REDACTED]` |

Masking also applies to free text containing emails or phone numbers. Dates and
short numeric runs are not treated as phone numbers.

## 6. Identity and RBAC data model

| Table | Purpose |
| --- | --- |
| `users` | Staff accounts: unique lowercased email, Argon2id hash, full name, active flag, timestamps |
| `roles` | `system_admin`, `admission_manager`, `admission_counsellor` with display names |
| `permissions` | 17 capabilities copied from PRD §4 (`users.manage`, `leads.view_all`, …) |
| `role_permissions` | Which role grants which permission |
| `user_roles` | A user may hold more than one role |

Primary keys are UUIDs generated by `gen_random_uuid()`; timestamps are
`timestamptz`. A CHECK constraint rejects non-lowercase emails, and services
normalise email before writing. The catalog and role matrix live in
`app/core/permissions.py`; `make seed` upserts it, replaces the links for seeded
roles, and (outside production) creates three `@enrollio.dev` demo accounts,
deleting the legacy `@example.test` demo rows first (D-023).
Seeding is idempotent. Authentication is described in §7; permission
enforcement arrives in M1.3.

### Permission enforcement

- `Depends(require_permission(PermissionName.X))` rejects a role that lacks the
  permission with `403 {"detail": "Insufficient permissions"}`.
- `can_access_lead(user, lead)` in `app/services/access.py` is the single
  resource rule: `leads.view_all` sees every lead, `leads.view_assigned` sees
  only `lead.assigned_counsellor_id == user.id`, everyone else sees none. The
  helper takes a structural `AssignedLead` protocol, so M2's `Lead` model can
  use it unchanged.
- Resource-level denial is rendered as **404**, so a caller cannot distinguish
  "exists but is not yours" from "does not exist" (D-024).
- The cross-counsellor gate is tested against real rows in
  `tests/integration/test_lead_scope.py` (Q-006 resolved in M2.1).

### User and role administration

| Endpoint | Permission | Behaviour |
| --- | --- | --- |
| `GET /api/users` | `users.manage` | List accounts with roles (`limit`/`offset`) |
| `POST /api/users` | `users.manage` | Create an active user; email normalised; role slugs validated |
| `PATCH /api/users/{id}` | `users.manage` | Update name, password, roles, or active state |
| `POST /api/users/{id}/deactivate` | `users.manage` | Deactivate and revoke sessions (idempotent) |
| `GET /api/roles` | `users.manage` | Roles with their permission names, for the role picker |
| `PUT /api/roles/{id}/permissions` | `roles.manage` | Replace the role's permission set |

Services own the rules (`app/services/users.py`, `app/services/roles.py`);
routers only map domain errors: duplicate email → 409, unknown role or
permission → 400, missing user or role → 404. Deactivation and password changes
revoke every refresh token for the user, and `get_current_user` reloads the
account on each request, so existing access tokens stop working immediately
(D-027). A guard against removing the last administrator is not implemented yet
(R-008, Q-007).

## 7. Authentication and sessions

| Endpoint | Purpose |
| --- | --- |
| `POST /api/auth/login` | Email + password → access token in the body, refresh token in a cookie |
| `POST /api/auth/refresh` | Rotate the refresh cookie and return a new access token |
| `POST /api/auth/logout` | Revoke the refresh-token family and clear the cookie |
| `GET /api/auth/me` | The current user, roles, and flattened permissions |

- **Access tokens** are HS256 JWTs valid for `ACCESS_TOKEN_EXPIRE_MINUTES` (15 by
  default) with `sub`, `type=access`, `jti`, `iat`, `exp`, and `iss=enrollio`.
  `get_current_user` validates the signature and reloads the user on every
  request, so deactivation and role changes apply immediately.
- **Refresh tokens** are opaque 256-bit values; the database stores only their
  SHA-256 hash. Each login opens a family; each refresh revokes the presented
  token, links `replaced_by_id` to its successor, and returns the successor.
  Presenting an already-rotated token is treated as theft and revokes the whole
  family (D-020).
- **Cookie:** `refresh_token`, `HttpOnly`, `Secure`, `SameSite=Strict`,
  `path=/api/auth`, `Max-Age` derived from `REFRESH_TOKEN_EXPIRE_DAYS`.
- **Lockout:** five failures inside `LOGIN_FAILURE_WINDOW_MINUTES` lock the
  account for `LOGIN_LOCKOUT_MINUTES`. Unknown emails pay the same Argon2 cost
  and every failure returns the same generic 401, so neither response body nor
  timing reveals whether an account exists (D-022).
- **CORS:** `CORS_ORIGINS` (comma-separated) with credentials enabled, so the
  Next.js app can call the API from a different origin.

### Frontend session handling

- `lib/api.ts` keeps the access token in a module variable. It is never written
  to `localStorage` or a cookie. `apiRequest` retries a request once after a 401
  by calling `/api/auth/refresh`, which uses the HttpOnly cookie.
- `components/auth-provider.tsx` restores the session on load by asking
  `/api/auth/me` (refreshing first when needed) and exposes `user`, `loading`,
  `login`, and `logout`.
- `components/require-auth.tsx` redirects anonymous visitors to `/login` and
  renders a loading state while the cookie exchange runs. This is convenience,
  not a security boundary: the API checks every request (D-029, R-009).
- `lib/navigation.ts` maps each menu item to one permission; the shell renders
  only the items the user's flattened permissions allow. `/sections/[slug]` is a
  placeholder until the corresponding module lands.
- `NEXT_PUBLIC_API_URL` lives in `frontend/.env.example` and defaults to
  `http://localhost:8000` (D-030).

## 8. Lead CRM data model

Migration `0004` adds the M2 foundation. Domain enums live in
`app/core/domain.py` and are stored as `VARCHAR` + `CHECK` (D-033).

| Table | Purpose and key columns |
| --- | --- |
| `students` | Person identity: `first_name`, `last_name`, `email_normalised`, `phone_e164`, optional `date_of_birth` |
| `leads` | One enquiry: `student_id`, nullable `programme_id`/`campus_id`/`source_id`, `admission_cycle`, `lifecycle_status`, `assigned_counsellor_id`, `raw_import_row` (JSONB) |
| `programmes` | Academic programmes: unique `name`, optional unique `code`, active flag |
| `campuses` | Locations: unique `name`, optional `city`, active flag |
| `lead_sources` | Acquisition channels: unique `name`, `description` |
| `consent_records` | Append-only grants/revocations: `student_id`, `channel`, `category`, `granted`, `source`, `method`, `recorded_at` |
| `timeline_events` | Immutable activity: `student_id`, nullable `lead_id`, `event_type`, `actor_type`, `actor_id`, `payload` (JSONB), `created_at` |

- **Duplicate prevention:** `UNIQUE (student_id, programme_id, admission_cycle)`
  stops a re-import from creating a second lead for the same enquiry (FR-02).
  A different programme or cycle is a legitimate new lead.
- **Student identity keys:** a student must have an email or a phone. Each is
  unique when present through partial indexes, and email must be lowercase. The
  importer normalises before writing (M2.2); the database enforces the invariant
  against future callers (D-034).
- **Cascade rules:** deleting a student removes their leads, consent records, and
  timeline. Deleting a programme, campus, source, or staff account nulls the
  reference instead of deleting enquiry history (D-032).
- **Consent** rows are never updated: the newest row for a
  student/channel/category is the current decision, preserving the audit trail
  required by AC4.4 (D-035).
- **Timeline** is ordered by `(student_id, created_at)`. `actor_id` is a plain
  UUID because the actor may be a user, agent, or system process.

## 9. Database migrations

Alembic runs against the async SQLAlchemy engine. The first migration (`0001`)
enables the `vector`, `btree_gist`, and `pgcrypto` extensions and is reversible.
Migrations are the only way schema changes are applied; the API container runs
`alembic upgrade head` before starting. `0004` adds the lead CRM tables
(§8). The migration test downgrades to base, upgrades to head, and asserts that
every table disappears again, so every revision must round-trip.

## 10. Testing

| Layer | Location | Requirements |
| --- | --- | --- |
| Unit | `backend/tests/unit` | No infrastructure |
| Integration | `backend/tests/integration` | PostgreSQL and Redis |
| Frontend unit | `frontend/tests` | Node only |
| End-to-end | `frontend/e2e` | API on `:8000`, seeded demo users, Chromium |

Integration tests use a dedicated `enrollio_test` database through
`TEST_DATABASE_URL`; they never touch `DATABASE_URL`. Locally, unreachable
PostgreSQL or Redis skips the tests so the unit suite runs anywhere; in CI
(`CI=true`) the same condition fails instead. `make create-test-db` creates the
database and `make migrate-test` applies migrations to it. The migration test
upgrades, downgrades, and re-upgrades the test schema and refuses to run when
the database name does not end in `_test` (R-001, D-013).

Lead-specific tests (`tests/integration/test_lead_model.py`) prove the
`(student, programme, cycle)` uniqueness and defaults, while
`tests/integration/test_lead_scope.py` exercises the cross-counsellor rule with
real users, leads, and access tokens: own lead 200, another counsellor's lead
404, manager 200, unknown id 404.

Playwright (`frontend/e2e/auth.spec.ts`) drives the real stack: it logs in as
each seeded role, asserts the role-specific menu, logs out, and confirms a
reload cannot restore the session. `make test-e2e` runs it against a locally
running API; CI uses a dedicated job with Postgres, Redis, migrations, seed,
Uvicorn, and Chromium (D-031).

CI (`.github/workflows/ci.yml`) runs backend lint/type-check/tests against
`pgvector/pgvector:pg16` and Redis service containers, frontend
lint/type-check/tests/build, and Docker image builds.

## 11. Decisions, status, and handoff

This document describes the resulting design. The **decision log with rationale**,
current milestone status, environment quirks, known risks, and open engineering
questions live in [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md). Workflow rules for
contributors and coding agents are in [`../AGENTS.md`](../AGENTS.md).

When a decision changes the design: append the decision to
`PROJECT_CONTEXT.md` first, then update the relevant section here.
