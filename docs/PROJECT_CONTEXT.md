# Project Context

**Living handoff document.** Read this before starting work and update it before
committing every task. It records what is done, what was decided and why, how the
project is operated, and what is still open.

- **Last updated:** 2026-11-05, after `M3.3` (single messaging entry point)
- **Current position:** M0 · M1 · M2 complete · M3.1–M3.3 complete → **next task M3.4**
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
| M0 Foundation | ✅ Complete | Verified locally against Docker on 2026-11-01; the CI gate ran on GitHub Actions on 2026-11-02 |
| M1 Identity and RBAC | ✅ Complete | M1.0–M1.5 complete; authenticated shell ships with role-aware navigation |
| M2 Lead CRM and ingestion | ✅ Complete | M2.1–M2.10 complete; lead management screens ship with import, list, detail, and manual entry |
| M3 Communication and campaigns | 🚧 In progress | M3.1–M3.3 complete; next M3.4 template engine |
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
| M0.5 CI pipeline | ✅ | `.github/workflows/ci.yml` runs four jobs — backend lint/types/tests (Postgres + Redis service containers), frontend lint/types/tests/build, Playwright auth flows, Docker image builds. Gate verified: a deliberately failing commit failed CI on PR #1, removing it made CI pass (D-038) |

### M1 task detail

| Task | Status | What exists |
| --- | --- | --- |
| M1.0 Test database isolation (R-001) | ✅ | `enrollio_test` created by Compose init / `make create-test-db`; `TEST_DATABASE_URL`; destructive migration test refuses non-`_test` databases; sentinel test proves the dev database survives |
| M1.1 Users, roles, permissions | ✅ | Migration `0002`; 17 permissions and 3 roles in `app/core/permissions.py`; idempotent `make seed`; Argon2id password hashing; three dev demo accounts |
| M1.2 Authentication | ✅ | Migration `0003` (lockout columns, `refresh_tokens`); JWT access tokens; opaque rotating refresh tokens in an HttpOnly/Secure/SameSite=Strict cookie scoped to `/api/auth`; login, refresh, logout, `/api/auth/me`; 5-failure lockout with generic 401; CORS for the web app |
| M1.3 Permission enforcement | ✅ | `require_permission` (403) in `app/api/deps.py`; `can_access_lead` in `app/services/access.py` (view-all vs assigned-only); unit + API tests. The real cross-counsellor DB gate landed with M2.1 |
| M1.4 User and role administration | ✅ | `GET/POST /api/users`, `PATCH /api/users/{id}`, `POST /api/users/{id}/deactivate`, `GET /api/roles`, `PUT /api/roles/{id}/permissions`; services normalise email, validate roles/permissions, revoke sessions on deactivation or password change; 403/404/409/400 tests |
| M1.5 Frontend authentication shell | ✅ | `/login`, client-side protected shell, in-memory access token with refresh-on-401, role-aware navigation from the permission list, logout; Vitest nav tests and 4 Playwright flows (three roles + invalid login) |

### M2 task detail

| Task | Status | What exists |
| --- | --- | --- |
| M2.1 Lead CRM core model | ✅ | Migration `0004`: `students`, `leads`, `programmes`, `campuses`, `lead_sources`, `consent_records`, `timeline_events`; unique `(student_id, programme_id, admission_cycle)`; partial unique indexes on normalised email/phone; cross-counsellor gate now tested against real leads (Q-006 resolved) |
| M2.2 Normalisation utilities | ✅ | `app/core/normalisation.py`: email (trim, lowercase, `email-validator`), phone (`phonenumbers`, IN default, E.164), name (whitespace collapse, case preserved), score (0–100, optional `%`); typed errors with stable reason codes; 102 parametrised cases, 100% branch coverage |
| M2.3 CSV/XLSX import pipeline | ✅ | Migration `0005` adds `import_jobs`, `mapping_templates`, `import_row_results`, `leads.import_job_id`, and student score/graduation-year columns; `POST /api/leads/import`, mapping/start, history, template, detail, and errors CSV endpoints; CSV/XLSX parsing with 10 MB/10,000-row limits; local/memory storage adapter; Celery task with inline mode for dev/tests; exact 85/5/10 fixture counts and provenance tested |
| M2.4 Duplicate detection and merge | ✅ | Migration `0006` adds `duplicate_candidates`; pure `decide_match` covers email-only/phone-only/both/same/conflict/name-only; name-only imports create a student + pending candidate (never auto-merge); conflicting contacts reject the row and create a candidate; `GET /api/duplicates` and `POST /api/duplicates/{id}/resolve` (`merge`, `keep_separate`, `reject`); merge moves leads/consent/timeline and fills only empty fields; re-import and non-overwrite integration tests pass |
| M2.5 Lifecycle state machine | ✅ | `services/lifecycle.py`: explicit transition table (linear funnel, any active state to Lost/Disqualified/Unresponsive/Opted Out), actor-aware rules, `TransitionActor` for users/system/agents, terminal reopen to New Enquiry by an Admission Manager, Converted by system or manager (never an agent), one `lifecycle_transition` timeline event per change; matrix and integration tests pass |
| M2.6 Consent management | ✅ | Append-only consent records; `POST /api/students/{id}/consent` (grant or revoke via `granted`) and `DELETE /api/students/{id}/consent/{channel}/{category}`; `can_send` blocks promotional without an explicit grant, allows transactional until explicitly revoked; revoking the last granted promotional channel closes active leads as Opted Out when `CONSENT_PROMOTIONAL_OPT_OUT_LIFECYCLE=true`; manager scope via `leads.view_all`; unit and integration tests pass |
| M2.7 Lead CRUD and search APIs | ✅ | `GET /api/leads` with opaque cursor pagination, created/updated sorting, lifecycle/programme/source/campus/counsellor/date filters, and `leads.view_all` vs `leads.view_assigned` scoping; `GET /api/leads/{id}` returns lead, student, consent summary, and an empty assessments list until the assessment model lands; `POST /api/leads` reuses the M2.3 dedupe/merge rules and returns `duplicate_detected`; `PATCH /api/leads/{id}` edits allowed fields only, rejects lifecycle input, and requires `leads.assign` to reassign; performance test seeds 10,000 leads and checks P95 against a conservative 1.5 s threshold |
| M2.8 Public web enquiry form | ✅ | Unauthenticated `POST /api/public/enquiries` with a Redis fixed-window limit of 10 requests/IP/hour, pluggable CAPTCHA verifier with a deterministic mock, `Website` source creation, the shared M2.3 dedupe/lead path, and `web_form` consent records for the submitted email/WhatsApp channels; duplicate submissions return the existing lead with `duplicate_detected`; submissions appear in the authenticated lead list |
| M2.9 Generic API ingestion endpoint | ✅ | Migration `0007` adds source-scoped hashed API keys; admin `POST /api/integrations/api-keys` returns plaintext once; `POST /api/integrations/leads` accepts `X-API-Key` or Bearer auth, ignores body source, validates through the import parser, enforces 1,000 records/413, isolates each record in a savepoint, returns `created`/`merged`/`duplicate`/`rejected` per record, and reuses the shared dedupe/name-only/conflict rules; HMAC-SHA256 webhook helper with a timestamp tolerance |
| M2.10 Frontend lead management | ✅ | `/sections/leads` (search, lifecycle/programme/campus/source filters, cursor pagination), `/sections/my-leads` (assigned scope), `/sections/leads/new` (validated manual form with duplicate notice), `/sections/leads/import` (upload → saved/guessed mapping → preview → inline results → error CSV), and `/sections/leads/[id]` (student/lead details, permission-filtered lifecycle control, consent panel, timeline empty state); backend adds escaped `?search=`, `GET /api/catalogues`, `POST /api/leads/{id}/lifecycle`, enriched list/detail names, and `allowed_transitions`. Vitest mapping test, Playwright import/counts and counsellor-scope tests pass |

### M3 task detail

| Task | Status | What exists |
| --- | --- | --- |
| M3.1 Provider interfaces and mocks | ✅ | `EmailProvider` protocol (`send`, `parse_inbound`, `verify_webhook`) and provider-neutral `EmailMessage`/`InboundMessage`; DB-backed `MockEmailProvider` (migration `0008` creates `mock_email_messages`) with outbound sends, inbound-reply capture, and delivery-event helpers; SendGrid v3 and Resend HTTP adapters over injected `httpx` with offline contract tests, Basic-auth Inbound Parse verification, and Svix-signed Resend webhooks that fetch the received body; factory defaults to the mock and fails closed for SES; WhatsApp interface plus a stub that raises `WhatsAppNotImplemented` |
| M3.2 Message and conversation data model | ✅ | Migration `0009` adds `conversations` (one per lead/channel, open/closed, `last_message_at`), `messages` (direction, channel, text/HTML, provider id unique per channel, status, intent, nullable `created_by_agent_action_id`), and `message_events` (event type, globally unique `provider_event_id`, `occurred_at`); lead → conversation → message → event deletes cascade, and a duplicate provider event is rejected without applying a second status change |
| M3.3 Single messaging entry point | ✅ | `app/services/messaging.py::send` is the only call path to a provider adapter, guarded in order by consent → promotional frequency cap (timeline `message_sent` events) → quiet hours (promotional sends queue as `queued` message rows with `next_allowed_at`) → approval (sensitive categories create a pending `approval_items` row, migration `0010`; repeats return the existing pending item). Missing recipient address blocks; a unit grep test keeps every other module away from the adapters |

### Verification snapshot (2026-11-05, after M3.3)

```text
make lint                 pass (ruff, ruff format --check, mypy; ESLint)
make typecheck            pass (mypy strict; frontend tsc --noEmit)
make test                 391 backend tests pass (2 opt-in live provider checks skipped),
                          frontend unchanged since M2.10 (8 tests)
make test-e2e             6 Playwright tests pass locally with the API on :8000 and
                          IMPORT_PROCESSING_MODE=inline (last run for M2.10; M3 has no UI change)
make migrate              pass (0010 applied)
make migrate-test         pass (0010 applied; migration test upgrades/downgrades;
                          0010 downgrade/upgrade re-verified manually)
make seed                 pass (3 roles, 17 permissions, 3 demo users, 4 programmes,
                          2 campuses, 4 lead sources; idempotent)
make smoke                not rerun after M2.3/M2.9 (host port 5432 is occupied by the
                          local PG 18; Docker changes are storage volume and no new services)
GET /readyz               200 with PG+Redis up (verified before M2.3)
GET /healthz              200
GET localhost:3000        200
`pytest -m performance`   10,000-lead list P95 under the conservative 1.5 s threshold
```

Normalisation coverage:

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_normalisation.py \
  --cov=app.core.normalisation --cov-branch --cov-fail-under=100
# 102 passed, app/core/normalisation.py 100% (62 statements, 22 branches)
```

CI verification (GitHub Actions, 2026-11-02):

| Run | Ref | Result |
| --- | --- | --- |
| `41387057466` | `main` push (M2.2) | ✅ all four jobs pass (backend, frontend, Playwright, Docker) |
| `41387484976` | PR #1, deliberate `assert False` probe | ❌ backend job fails at **lint** (`B011`) — proves the lint gate blocks a merge |
| `41387583084` | PR #1, probe rewritten as `raise AssertionError` | ❌ backend job fails at **pytest** — proves the test gate blocks a merge |
| final PR #1 run | `m0.5-ci-gate` after probe removal | ✅ run `41387966429` — all four jobs pass, merged to `main` |

The probe never landed on `main`: it existed only on the `m0.5-ci-gate` branch
and was removed in the same PR that records this verification.

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
| D-008 | ~~One local commit per task, task ID in the message; no push/PR yet~~ **Superseded by D-038** | User choice while pre-release; CI verifies nothing until pushed | Branch + PR per task |
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
| D-032 | Migration `0004` adds the core CRM tables. `leads.student_id` cascades on delete; catalogue FKs (`programme`, `campus`, `source`) and `assigned_counsellor_id` use `ON DELETE SET NULL`; `programme_id`/`campus_id`/`source_id` are nullable because course, campus, and source are optional on import | A lead is meaningless without its student, but losing a programme or counsellor must not delete enquiry history | Cascading catalogue deletes; non-null programme/campus |
| D-033 | Lifecycle, actor, and consent enums live in `app/core/domain.py` and are stored as `VARCHAR` + `CHECK` (`native_enum=False`, `create_constraint=True`) | Adding a value is a normal constraint migration; PostgreSQL enum types are awkward to alter and complicate downgrade | Native PostgreSQL enums; free-text columns with no check |
| D-034 | `students` requires at least one of `email_normalised`/`phone_e164`, each is unique when present (partial indexes), and email must be lowercase | FR-02 identifies a student by exact email or phone; the database enforces the invariant even if a future caller bypasses the normaliser | Application-only validation; `citext` |
| D-035 | `consent_records` is append-only (latest row per student/channel/category wins); `timeline_events.actor_id` is a plain UUID because the actor may be a user, agent, or system; timeline has `created_at` only | Consent needs the full grant/revoke history (AC4.4) and timeline events are immutable; one actor column cannot reference three tables | Updating consent rows in place; separate event tables per actor type |
| D-036 | Normalisation lives in `app/core/normalisation.py`; each helper raises a `NormalisationError` subclass with a stable `code` (`invalid_email`, `invalid_phone`, `invalid_name`, `invalid_score`) | M2.3 stores those codes as import rejection reasons, so messages can change without breaking reporting | Returning `None`; string parsing of error messages |
| D-037 | Emails are fully lowercased after `email-validator`; phones use `phonenumbers` with default region `IN` and must pass `is_valid_number`; international numbers are accepted when they carry a country code; scores become floats | Import data is messy and Indian numbers arrive in many forms; canonical values keep duplicate detection exact and country-agnostic | Storing raw input; assuming every number is Indian |
| D-038 | The repository lives on GitHub and every task ships on a per-task branch via a pull request; `main` only moves when the PR's full four-job CI run is green (D-008 superseded) | The M0.5 gate must actually block bad code; branch protection plus a green PR is the only evidence it does | Continuing to commit to `main`; pushing without a PR |
| D-039 | Import state lives in `import_jobs` (status, headers, mapping, counters, storage key) with one `import_row_results` row per source row; every created/merged lead stores `import_job_id` and `raw_import_row` | Counts, errors, and provenance are queryable without re-reading the file, and the raw row preserves the audit trail | Counters only; storing raw rows in logs |
| D-040 | Upload parses CSV/XLSX synchronously (headers, 10 MB, 10,000 rows) and processing runs through a Celery task; `IMPORT_PROCESSING_MODE=inline` runs the same service in-request for local dev and tests | Invalid files fail at upload with a clear 4xx, while real imports do not hold an HTTP request; tests stay hermetic | Parsing in the worker only; always-inline processing |
| D-041 | Import matching is exact on normalised email or phone: an existing lead for the same programme/cycle is `duplicate`; an existing student with no lead is `merged` (fill empty fields only); new identity is `created`; conflicting email/phone is `conflicting_contact` and rejected | Implements the M2.3 counts and the M2.4 fill-empty merge policy without overwriting data; conflicts are visible rather than silently merged | Fuzzy matching; overwriting non-empty student fields |
| D-042 | `mapping_templates` is keyed by `source_name` and upserted when a job starts; `GET /api/imports/mapping-template?source_name=` returns it | Reusing a mapping is the point of the template, and source name is the user-facing grouping used by the import form | Template per uploader; mapping only on the job |
| D-043 | Import endpoints reuse `leads.view_all`; the router maps domain errors to 400/404/409/413/422 and never exposes row contents in list/detail responses | No new permission is needed for bulk ingress, and the error CSV is the only row-level report | A separate `leads.import` permission |
| D-044 | Storage is an interface (`Storage`) with `LocalStorage` for local/dev and `MemoryStorage` for mock mode; the factory keeps local disk even when `USE_MOCK_STORAGE=true` | Import files must survive the request and be readable by the worker; tests need an isolated temp directory without S3 | Reading files back from the HTTP request; hardcoding a vendor SDK |
| D-045 | `duplicate_candidates` stores the existing student (`student_id`), the newly created student for name-only hits (`candidate_student_id`), the other contact owner for conflicts (`conflicting_student_id`), the import job/row, and the raw row | A reviewer needs to see both sides of the possible match, and the import row remains auditable after the job finishes | Storing only names/emails; creating a separate table per match type |
| D-046 | Name-only matches never merge automatically: the row still creates a student/lead and records a pending `name_only` candidate (AC2.5); conflicting email/phone matches reject the row and record a `conflicting_contact` candidate for review | Preserves import throughput without silently combining people, and makes both ambiguous cases visible in one queue | Auto-merging on name; dropping name-only rows without review |
| D-047 | Resolution actions are `merge` (fill only empty fields, move leads/consent/timeline, delete the source student), `keep_separate` (leave both), and `reject` (delete the created candidate student for a name-only hit; conflicts keep both existing students) | Gives reviewers an explicit, reversible-by-audit decision without overwriting non-empty data; moving dependent rows preserves history | Hard-deleting on reject without a record; overwriting target fields |
| D-048 | Duplicate endpoints reuse `leads.view_all`; `GET /api/duplicates` returns pending candidates by default and `POST /api/duplicates/{id}/resolve` takes `action`, rejecting an already-resolved candidate with 409 | Keeps duplicate review in the existing lead-management scope and prevents double decisions | A new `duplicates.manage` permission; idempotent re-resolution |
| D-049 | Lifecycle transitions are an explicit table in `services/lifecycle.py`: the funnel is linear, every active state can close to Lost/Disqualified/Unresponsive/Opted Out, and Converted is treated as terminal in the state machine; terminal leads can only reopen to New Enquiry | One reviewable table drives validation and tests; no implicit jumps, and closed leads cannot silently re-enter the funnel | Free-form status assignment; allowing skips/backward moves |
| D-050 | `TransitionActor` carries `ActorType`, user id, role slugs, and permission names. A manager is an Admission Manager role holder or a user with `leads.view_all`; system actors can convert, agents never can, and a non-manager user cannot reopen | Reuses the existing permission matrix (no new `admission.mark_converted` permission) while enforcing AC3.4; the actor is explicit so agents cannot borrow user rights | Adding a permission; inferring the actor from ambient context |
| D-051 | Every accepted transition writes one `lifecycle_transition` timeline event with `from_state`, `to_state`, `reason`, actor type/id; rejected transitions log the lead and states only (never the reason) and leave the lead untouched | Satisfies AC3.2 and AC3.1 without leaking free-text reasons into logs; the payload is the audit record | Mutating status without a timeline; logging reasons |
| D-052 | Consent is append-only and the newest row for a student/channel/category wins. With no row, promotional is blocked and transactional is allowed; any explicit row (grant or revoke) overrides that default | PRD guardrail 1 forbids promotional sends without an active grant, while booking confirmations and reminders must not depend on marketing opt-in | Treating silence as promotional consent; requiring a record for transactional messages |
| D-053 | `POST /api/students/{id}/consent` appends a grant by default and accepts `granted=false`; `DELETE .../{channel}/{category}` appends a revocation. `source`/`method` default to `staff`/`manual_entry` but can be supplied for AC4.4 | One write path keeps the audit trail intact; staff entry and unsubscribe use the same mechanism, and DELETE remains the obvious opt-out verb | Updating rows in place; separate opt-out storage |
| D-054 | Revoking promotional consent closes every active lead as Opted Out only when no other channel still has a granted promotional record. `CONSENT_PROMOTIONAL_OPT_OUT_LIFECYCLE=false` disables the lifecycle side effect | Matches "opts out completely" and the configurable requirement, while leaving a single-channel unsubscribe with other active consents untouched; system-actor lifecycle transitions write timeline events | Opting out on any single revoke; editing lifecycle without an event |
| D-055 | Consent endpoints reuse `leads.view_all`; unknown students are 404 and counsellors get 403 | Consent is staff administration over student records, consistent with import/duplicate review; no new permission is needed yet | A new `consent.manage` permission; allowing counsellors to change consent |
| D-056 | M2.7 keeps one lead service for manual creation: it applies the same `decide_match` rules as import, persists name-only candidates, returns an existing lead with HTTP 200 + `duplicate_detected` instead of creating a second one, and requires at least one contact key. `GET /api/leads` uses an opaque base64 cursor containing the sort value and lead id; `leads.view_all` sees everything and `leads.view_assigned` is filtered to the caller. Detail denial is 404, lifecycle fields are rejected by PATCH (422), and assignment requires `leads.assign` | Manual entry must not bypass the import invariants; a cursor avoids offset drift while new leads arrive; scope denial must not reveal existence; keeping lifecycle in M2.5 prevents two write paths | Duplicating import logic in the router; page/offset pagination; allowing lifecycle through PATCH |
| D-057 | `POST /api/public/enquiries` is unauthenticated but runs through a Redis fixed-window limiter before CAPTCHA verification and lead creation. CAPTCHA sits behind a `CaptchaVerifier` protocol with a deterministic mock; rate limiting fails closed with 503 if Redis is unavailable. Public leads always use the `Website` source, reuse `create_or_get_lead`, and record promotional/transactional consent only for channels actually supplied, with `source=method=web_form`. The response is a minimal acknowledgement and never echoes PII | Keeps the public surface from bypassing dedupe or consent, limits abuse before touching the database, and avoids revealing whether an enquiry matched an existing student; mocks keep tests hermetic | Trusting client-supplied source; requiring consent to create the lead; accepting unbounded unauthenticated writes; calling a vendor SDK from the router |
| D-058 | Partner API keys are random `enr_` tokens generated with `secrets.token_urlsafe(32)`; only the SHA-256 hash and a 12-character prefix are stored. Each key is scoped to one `lead_sources` row, may expire, and is provisioned by an admin through `POST /api/integrations/api-keys` (`integrations.manage`); partners send `X-API-Key` or Bearer. `POST /api/integrations/leads` ignores any body `source`, validates every record through the import parser, commits each record inside a savepoint, enforces the configurable 1,000-record cap before writing, and reports `created`/`merged`/`duplicate`/`rejected` with candidate/conflict handling. Webhook signatures use `t=<unix>,v1=<hmac-sha256>` with a five-minute default tolerance | Hashing at rest limits key leaks, source scoping prevents a partner from spoofing another channel, savepoints keep one bad record from aborting a batch, and reusing the import path prevents API/import drift | Storing plaintext keys; trusting a body source; failing the whole batch on one bad record; inventing a second validation path |
| D-059 | M2.10 adds only the backend read/write support the screens need: `GET /api/leads?search=` searches owned-scope leads with an escaped contains match over first/last/full name, email, and phone; `GET /api/catalogues` returns active programmes/campuses/sources to `leads.view_all` or `leads.view_assigned`; and `POST /api/leads/{id}/lifecycle` takes `to_state` + `reason`, applies the M2.5 actor rules (422 invalid pair, 403 not permitted, 404 out of scope), and writes the usual timeline event. List rows gain `student` plus programme/campus/source/counsellor names, and detail gains the same names plus `allowed_transitions` in funnel order | The UI must not invent endpoints or duplicate permission/lifecycle logic; one service stays authoritative, the list avoids N+1 follow-up calls for display names, and the frontend can disable impossible buttons while the API still enforces them | Querying catalogues per filter field; returning raw ids for the UI to resolve; a second lifecycle write path; client-side transition validation only |
| D-060 | Search escapes `%`, `_`, and `\` and uses `ILIKE ... ESCAPE '\'`, and every search remains inside the caller's `leads.view_assigned` scope | A literal wildcard must not broaden a counsellor's visible set or turn into an accidental full-table scan; scoping stays identical to the unfiltered list | Unescaped `ILIKE`; a separate search permission |
| D-061 | Lead management UI is split by permission: `/sections/leads` and `/sections/leads/import` require `leads.view_all`, while `/sections/my-leads` requires `leads.view_assigned`; `/sections/leads/new` is available to both and detail pages adapt the back link. `RequirePermission` renders an access message, but the API remains the enforcement boundary (R-009) | Managers and counsellors see different navigation already, and the list/detail routes must not silently show empty data to a role that cannot call the API; keeping the server authoritative avoids a second authorization source | One shared route that hides controls client-side; adding new permissions for UI routes |
| D-062 | The import wizard uploads first (headers only), then loads a saved template by source name or guesses from common headers, previews mapped fields, starts processing, and renders terminal counts plus the error CSV. The Playwright import test copies the committed 100-row fixture with unique emails/phones per run, and CI sets `IMPORT_PROCESSING_MODE=inline` for the e2e job | Saving nothing until the user confirms the mapping matches the M2.3 API, and unique contacts keep the counted 85 created/5 duplicates/10 rejected stable across repeated runs; inline mode lets the browser flow finish without a Celery worker while the default stays `celery` | Creating leads during upload; reusing fixed contacts (later runs would become duplicates); running a worker in the Playwright job |
| D-063 | Email uses one provider-neutral contract in `app/integrations/email/base.py`: `send` returns the provider message id, `parse_inbound` returns an `InboundMessage`, and `verify_webhook` returns a boolean. The mock is selected whenever `USE_MOCK_EMAIL` is true, regardless of `EMAIL_PROVIDER`, and stores sends/replies in `mock_email_messages` (migration `0008`) with test helpers for inbound replies and delivery events | Downstream services must never see a vendor payload or SDK; the mock needs durable, inspectable state for M3.2–M3.5 tests, and D-004's mock flags stay authoritative | In-memory-only mock; provider-specific message classes leaking into services; calling a vendor SDK directly |
| D-064 | The first real email adapter is SendGrid: `httpx` posts the v3 payload, the `X-Message-Id` header is the provider id, non-2xx/transport failures raise `EmailDeliveryError`, and Inbound Parse webhooks require HTTP Basic auth `sendgrid:<EMAIL_WEBHOOK_SECRET>`. `AsyncClient` can be injected so contract tests assert the request offline. SES remains enumerated but raises `EmailNotConfigured` | SendGrid needs one bearer key that the existing settings already model, and an injected client lets CI verify the wire contract without credentials or real mail. A future SES adapter can implement the same protocol without touching callers | Adding boto3 now; committing to SES without credentials; accepting unsigned webhooks |
| D-065 | M3 defines the WhatsApp interface, message dataclasses, and a stub provider whose methods raise `WhatsAppNotImplemented`; no factory selects a Cloud API adapter until Phase 2 | Keeps downstream signatures stable without pretending an untested vendor integration works; the task explicitly marks WhatsApp as a stub | Implementing Cloud API early; omitting the interface |
| D-066 | M3.2 stores messaging state in three tables: `conversations` is unique per `(lead_id, channel)` and carries `last_message_at`; `messages` denormalises `channel`, scopes `provider_message_id` uniqueness to the channel, and keeps `created_by_agent_action_id` as a plain UUID; `message_events` holds an append-only event log with a globally unique `provider_event_id`. Deletes cascade lead → conversation → message → event, and webhook handlers must insert the event before applying a status change so a replayed event fails the unique constraint | One thread per lead/channel makes inbound and outbound paths converge without a race; provider ids are only unique inside a provider namespace; the event uniqueness is the idempotency boundary, and ordering the insert first prevents a duplicate payload from mutating message state | A second thread per lead/channel; global provider-message uniqueness that blocks cross-channel ids; updating status before recording the event; storing the agent action as a hard FK before the agent-run table exists |
| D-067 | Resend is the second real email adapter. Sending posts to `https://api.resend.com/emails` with a Bearer key and reads the response `id`; metadata becomes Resend tags. Inbound `email.received` webhooks are verified as Svix signatures (`svix-id`, `svix-timestamp`, `svix-signature`, five-minute tolerance), then the adapter fetches `GET /emails/receiving/{id}` for subject, body, and headers because Resend webhooks carry metadata only. `EMAIL_WEBHOOK_SECRET` is the `whsec_...` signing secret for Resend and the Basic-auth password for SendGrid | Resend provides inbound email with a single provider, and fetching the body is the documented flow; implementing the signature check locally keeps `httpx` as the only HTTP dependency and avoids a vendor SDK. The generic email settings mean switching providers changes one enum value | Treating the metadata-only webhook as a full message; skipping Svix verification; importing the Resend SDK into business code |
| D-068 | M3.3 makes `app/services/messaging.py::send(session, settings, provider, lead=…, channel=…, category=…, content=…, actor=…)` the single path to any provider adapter (enforced by a unit grep test over `app/`). Guard order is consent → promotional frequency cap → quiet hours → approval. Sensitive categories (scholarship, fee, admission offer, deadline change) ride the transactional consent class and require a pending `approval_items` row (`type=message_send`, migration `0010`); a repeat request returns the existing pending item instead of duplicating it. Promotional sends inside quiet hours create a `queued` message row, skip the provider and the `message_sent` timeline event, and return `next_allowed_at`, the window end in `QUIET_HOURS_TIMEZONE`. Missing recipient address blocks with `missing_recipient_address`; non-email channels raise `WhatsAppNotImplemented` until Phase 2 | The plan requires every guard to run for every send and the grep check to hold; counting cap usage from timeline events reuses the append-only audit trail instead of a new counter table; approval-first for sensitive categories means unsent content never touches a provider | Bypassing `send` from campaign or agent code (grep gate fails); recording a `sent` timeline event for a queued or refused send; a second approval item per repeat request; per-lead cap counters that drift from the timeline |

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
- **Local M2.3 verification:** the host PostgreSQL 18 lacks `pgvector` and
  occupies 5432, so the test/dev database ran in
  `docker run ... -p 55432:5432 pgvector/pgvector:pg16` (database `enrollio`,
  test database `enrollio_test`); the local `.env` points both URLs at 55432.
  This is a workstation quirk, not the project default.
- **Compose startup order:** `db`/`redis`/`minio` healthy → `api` runs
  `alembic upgrade head` then Uvicorn → `web` waits for healthy `api`.
- **MinIO:** official images are unavailable; see D-006. `curl` exists in the
  pinned image, which the healthcheck relies on.
- **Integration test detection:** `backend/tests/conftest.py` probes the host/port
  of `TEST_DATABASE_URL`/`TEST_REDIS_URL` (Redis falls back to `REDIS_URL`) and
  skips if closed. The database never falls back to `DATABASE_URL`; its name must
  end in `_test`. Use `make create-test-db` once per fresh volume and
  `make migrate-test` after adding migrations.
- **Seed:** `make seed` upserts the RBAC catalog, creates the three demo
  accounts, and adds demo programmes, campuses, and lead sources for imports.
  It is idempotent; `SEED_DEMO_USERS=false` keeps users out.
- **Imports:** uploaded files are parsed synchronously, then rows run through a
  Celery task. `IMPORT_PROCESSING_MODE=inline` processes them in the request so
  `make dev` works without a worker; the local `.env` sets inline, tests do too,
  and the default remains `celery` for the full stack. Limits are 10,000 rows and
  10 MB per file.
- **Email providers:** `USE_MOCK_EMAIL=true` is the default and always selects
  the DB-backed mock, even if `EMAIL_PROVIDER` names SendGrid or Resend. The
  mock's webhook signature is `X-Mock-Signature: sha256=<hmac>` over the raw
  body. SendGrid uses `EMAIL_API_KEY` and Basic-auth Inbound Parse with username
  `sendgrid` and `EMAIL_WEBHOOK_SECRET`. Resend uses the same Bearer key and a
  `whsec_...` Svix signing secret, then fetches the received body. The opt-in
  live checks also need `EMAIL_CONTRACT_TO` (plus `EMAIL_PROVIDER=resend` for
  Resend). `EMAIL_PROVIDER=ses` fails with `EmailNotConfigured` until an adapter
  lands.
- **Messaging guards (M3.3):** quiet hours default 21:00–09:00 `Asia/Kolkata`
  and only promotional sends queue inside them; the integration tests disable
  the window (start 9, end 9) so they are time-of-day independent. The
  promotional cap counts `message_sent` timeline events per student
  (default 2 per 7 days). Approval items carry `type=message_send` payloads
  with channel/category/subject.
- **Demo logins:** `admin@enrollio.dev`, `manager@enrollio.dev`,
  `counsellor@enrollio.dev` with `SEED_DEMO_PASSWORD`. `.dev` is used because
  `EmailStr` rejects `.test` (D-023).
- **Auth cookies:** the refresh cookie is `Secure`, so browsers only send it over
  HTTPS or to `localhost`. API tests use an `https://test` base URL for that
  reason.
- **Frontend API URL:** `NEXT_PUBLIC_API_URL` lives in `frontend/.env.example`
  and defaults to `http://localhost:8000`. Copy it to `frontend/.env.local` only
  when the backend is elsewhere; the root `.env` does not hold browser values.
- **End-to-end:** with the API running on `:8000` with `IMPORT_PROCESSING_MODE=inline`
  and demo users seeded, `make test-e2e` runs Playwright (it starts Next.js
  itself). `SEED_DEMO_PASSWORD` must match the backend; it defaults to
  `dev-only-password`. The import spec copies the committed 100-row fixture with
  unique contacts per run and asserts 85 created, 5 duplicates, 10 rejected.
  CI's Playwright job exports the same inline mode so no worker is needed.
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
- **Git:** `Mx.y: summary` on a per-task branch; open a pull request and merge only
  when the full four-job CI run is green (D-038). Never mix unrelated refactors
  into a task commit.

## 7. Known risks and pending fixes

| ID | Risk / gap | Action |
| --- | --- | --- |
| R-001 | ~~**Integration tests use the dev database.**~~ **Resolved by D-013 (M1.0).** Tests now use `enrollio_test`, the migration test refuses non-`_test` names, and a sentinel test proves the dev database survives | Done; keep the guard |
| R-002 | ~~`docs/plan.md` M0.5's "deliberately failing test" gate has never run, because nothing is pushed~~ **Resolved 2026-11-02:** runs `41387484976` and `41387583084` failed on a deliberate probe (lint and pytest respectively); `main` run `41387057466` passes all four jobs (D-038) | Keep `main` green; never merge a red PR |
| R-003 | MinIO is served by a third-party mirror | Tag is pinned; image only exposes the S3 API. If unavailable, switch to another S3-compatible image (D-006) |
| R-004 | ~~**No authentication or RBAC.**~~ **Resolved in M1.2–M1.3, and M2.7 now exercises the real lead endpoints:** `GET/PATCH /api/leads/{id}` return 404 for another counsellor and 200 for the assigned owner or a `leads.view_all` manager; list results are scoped identically | Every new endpoint must declare a permission and a resource scope |
| R-005 | Provider choices for M3/M4 are undecided | Answer Q-001 before M3.1; mocks keep progress unblocked |
| R-006 | CI has no secret scanning, dependency audit, or coverage gate yet | Add when the plan's security/testing tasks require it; not M0 scope |
| R-007 | `docs/plan.md` M0 requires Python 3.12 but the host ships 3.14 | The 3.12 interpreter is installed via uv; document this for new machines |
| R-008 | The last System Admin can deactivate themselves or strip `users.manage`/`roles.manage` from `system_admin`, leaving no one able to administer the system | Add the guard decided in Q-007 before any shared deployment; acceptable for local development |
| R-009 | The frontend route guard is cosmetic: a user can open any `/sections/*` URL | Routes render no data; every API call is authorised server-side. Never move access checks into the UI only |
| R-010 | ~~M2.3 rejects a row whose email and phone point at different existing students without a review record~~ **Resolved in M2.4:** conflicting contacts now reject the row and create a pending `duplicate_candidates` entry; name-only matches create candidates without auto-merging | Done; keep the stable `conflicting_contact` reason |
| R-011 | ~~M2.5 ships the lifecycle service but no HTTP endpoint; M2.7 rejects `lifecycle_status` in `PATCH /api/leads/{id}`~~ **Resolved in M2.10:** `POST /api/leads/{id}/lifecycle` applies the actor rules with `to_state` + `reason`, and detail returns `allowed_transitions` | Keep lifecycle writes on the dedicated endpoint; PATCH stays lifecycle-free |
| R-012 | `GET /api/leads/{id}` returns `assessments: []` because no assessment table/model exists yet, although the M2.7 plan names latest assessments | Wire the query when M6.1 adds assessments; the response shape already reserves the field |
| R-013 | The public enquiry CAPTCHA is a mock verifier. `USE_MOCK_CAPTCHA=false` currently has no real adapter and fails closed with a 500 at the dependency | Add a Turnstile/reCAPTCHA adapter before exposing the form publicly; the provider interface and mock already exist |
| R-014 | Public enquiry rate limiting keys on `request.client.host`; behind a reverse proxy every request may share the proxy IP and exhaust the allowance | Decide trusted-proxy/forwarded-header handling before deployment; do not trust `X-Forwarded-For` blindly |
| R-015 | Partner API keys can be created but not listed or revoked through HTTP; rotation requires direct database updates | Add list/revoke endpoints and an audit trail before onboarding real partners |
| R-016 | `EMAIL_PROVIDER=ses` is accepted by configuration but has no adapter, so selecting it fails with `EmailNotConfigured`; SendGrid and Resend are implemented | Implement SES (or remove the enum value) once Q-001 is answered; mocks keep M3 unblocked |
| R-017 | The live SendGrid and Resend contract tests are skipped unless their opt-in environment is set, so CI proves both request shapes through `httpx.MockTransport` but never delivers real mail. The SendGrid check needs `EMAIL_API_KEY` + `EMAIL_CONTRACT_TO`; the Resend check additionally needs `EMAIL_PROVIDER=resend` | Run the opt-in live checks before production and record the verified sender/domain setup |

## 8. Open implementation questions

These are engineering decisions; product/college questions stay in
[`open_questions_next_steps.md`](open_questions_next_steps.md).

| ID | Question | Needed by |
| --- | --- | --- |
| Q-001 | Which real LLM provider (primary + fallback) and email provider should be the first non-mock adapters? **Partial 2026-11-03:** M3.1 ships SendGrid and Resend behind the existing email settings; SES remains unimplemented (R-016). LLM choice is still open. | M3.1 / M4.4 |
| Q-002 | ~~Confirm the test-database strategy in R-001~~ **Resolved in M1.0:** dedicated `enrollio_test` database (D-013) | — |
| Q-003 | ~~When do we push the repository and switch to per-task branches so CI and the M0.5 gate actually run?~~ **Resolved 2026-11-02:** the repository is pushed, CI runs on every push and pull request, and tasks now go through per-task branches and PRs (D-038) | — |
| Q-004 | If the PIGSTY MinIO mirror disappears, which S3-compatible image is the fallback? | When D-006 needs revisiting |
| Q-005 | Should `make dev` eventually run migrations automatically, or stay explicit (`make migrate`)? | M1.1 |
| Q-006 | ~~Deferred security gate: M1.3's cross-counsellor test needs the `leads` table~~ **Resolved in M2.1:** `test_lead_scope.py` creates real leads for two counsellors and proves 404 cross-scope, 200 own scope, and manager view-all | — |
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
| 2026-11-02 | M2.1: migration `0004` adds students, leads, programmes, campuses, lead sources, consent records, and timeline events; lead uniqueness and student contact keys enforced in the database; Q-006 cross-counsellor gate tested against real leads. |
| 2026-11-02 | M2.2: email/phone/name/score normalisers with typed reason codes, `phonenumbers` dependency, 102 cases at 100% branch coverage. |
| 2026-11-02 | M0.5: repository pushed; CI verified on GitHub Actions (green `main` run `41387057466`; deliberate probe failed lint then pytest on PR #1). R-002 and Q-003 resolved; tasks now ship on per-task branches with a green PR before merge (D-038). |
| 2026-11-02 | M2.3: migration `0005`, import jobs/templates/row results, CSV/XLSX upload with limits, mapping/start (Celery or inline), duplicate/merge/reject outcomes, error CSV, local/memory storage, demo catalogue seed; 240 backend tests and 4 frontend tests pass. |
| 2026-11-02 | M2.4: migration `0006` adds duplicate candidates; exact contact/name matching, pending review for name-only and conflicting contacts, merge/keep-separate/reject resolution, and non-overwrite tests; 249 backend tests and 4 frontend tests pass. |
| 2026-11-02 | M2.5: explicit lifecycle transition table, actor-aware rules (agents cannot convert), manager-only terminal reopen, one timeline event per transition; 290 backend tests and 4 frontend tests pass. |
| 2026-11-02 | M2.6: append-only consent API, promotional/transactional send checks, configurable promotional opt-out closing active leads, and tests; 297 backend tests and 4 frontend tests pass. |
| 2026-11-03 | M2.7: cursor-paginated scoped lead list with filters and sorting, lead detail with student/consent summary, manual creation through the shared dedupe path, lifecycle-free PATCH, assignment checks, and a 10,000-lead P95 performance test; 304 backend tests and 4 frontend tests pass. |
| 2026-11-03 | M2.8: public enquiry endpoint with Redis per-IP rate limiting, mock CAPTCHA verifier, Website source, shared dedupe lead creation, web-form consent records, and duplicate detection; 315 backend tests and 4 frontend tests pass. |
| 2026-11-03 | M2.9: migration `0007` adds source-scoped hashed API keys; admin key provisioning, API-key/Bearer authentication, import-equivalent batch validation and dedupe, per-record results and savepoint isolation, 1,000-record limit, and an HMAC webhook signature helper; 323 backend tests and 4 frontend tests pass. |
| 2026-11-03 | M2.10: lead list with escaped search/filters/cursor paging, my-leads scoping, validated manual entry, import wizard with saved/guessed mapping and error CSV, lead detail with permission-filtered lifecycle and consent panel; backend adds catalogues, lifecycle transition endpoint, enriched names, and `allowed_transitions`; 328 backend tests, 8 frontend tests, and 6 Playwright flows pass. **Milestone M2 complete.** |
| 2026-11-03 | M3.1: provider-neutral email contract, DB-backed mock with inbound/delivery helpers (migration `0008`), SendGrid v3 adapter over injected `httpx` with Basic-auth inbound verification, mock-first factory, WhatsApp interface and stub, contract/factory tests; 347 backend tests pass with 1 opt-in live SendGrid test skipped. |
| 2026-11-03 | M3.2: migration `0009` adds `conversations`, `messages`, and `message_events` with one thread per lead/channel, channel-scoped provider message ids, globally unique provider event ids, and lead → conversation → message → event cascades; integration tests prove conversation defaults/uniqueness, provider message uniqueness, duplicate-event rejection without a second status change, and SQL/ORM cascade deletion; 352 backend tests pass with 1 opt-in live SendGrid test skipped. |
| 2026-11-03 | Resend adapter (M3.1 extension): `POST /emails` sending with tags, Svix signature verification with a five-minute tolerance, `email.received` handling that fetches `/emails/receiving/{id}` for the body, factory selection via `EMAIL_PROVIDER=resend`, shared contract tests across mock/SendGrid/Resend, Resend payload/inbound/signature tests, and opt-in live checks; 360 backend tests pass with 2 live provider checks skipped. |
| 2026-11-05 | M3.3: migration `0010` adds `approval_items`; `messaging.send` becomes the single provider call path with consent, promotional frequency cap (counted from `message_sent` timeline events), quiet-hours queueing, and pending approvals for sensitive categories; repositories for conversations/messages/approvals/timeline and a unit grep test that keeps adapter access inside the entry point; 391 backend tests pass with 2 live provider checks skipped. |
