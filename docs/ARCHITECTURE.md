# Architecture

> Status: Milestones M0, M1, and M2.1–M2.9 (foundation, identity, lead CRM
> schema, normalisation, CSV/XLSX import, duplicate review, lifecycle, consent,
> lead CRUD/search, the public web enquiry form, and partner API ingestion). This
> document is updated as milestones land.

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
│   │   ├── integrations/    # provider interfaces and adapters (incl. storage)
│   │   └── workers/         # Celery application and tasks
│   ├── migrations/          # Alembic environment and versions
│   ├── tests/               # unit, integration, eval, fixtures
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
├── frontend/                # Next.js 15 App Router (TypeScript, Tailwind 4)
│   ├── app/                 # routes: `/`, `/login`, `/sections/leads`, `/sections/my-leads`, `/sections/[slug]`
│   ├── components/          # auth provider, protected shell, navigation, lead screens, import wizard
│   ├── lib/                 # API clients, types, navigation catalog, lifecycle helpers
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
- `IMPORT_PROCESSING_MODE` selects `celery` (default) or `inline` for import
  processing; `IMPORT_MAX_ROWS` and `IMPORT_MAX_FILE_BYTES` bound uploads.
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
| `students` | Person identity: `first_name`, `last_name`, `email_normalised`, `phone_e164`, optional `date_of_birth`, `academic_score`, `graduation_year` |
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

### Normalisation (M2.2)

`app/core/normalisation.py` is the single place incoming values are canonicalised.
Every helper returns a canonical value or raises a `NormalisationError` subclass
whose stable `code` becomes the import rejection reason (D-036):

| Helper | Rule | Example |
| --- | --- | --- |
| `normalise_email` | Trim, validate with `email-validator` (no delivery check), lowercase | `Rahul.Sharma@Gmail.com` → `rahul.sharma@gmail.com` |
| `normalise_phone` | Parse with `phonenumbers`, default region `IN`, require a valid number, format E.164 | `098765 43210` → `+919876543210` |
| `normalise_name` | Collapse all whitespace, preserve case and punctuation | `"  Asha   Rao "` → `Asha Rao` |
| `normalise_score` | Accept numeric 0–100 with optional trailing `%`; reject booleans, NaN, infinity, text | `85%` → `85.0` |

Emails are lowercased entirely, not just the domain, so duplicate detection and
login stay case-insensitive (D-037). Phone numbers without a country code are
read as Indian; numbers with one may be international.

### Import pipeline (M2.3)

Migration `0005` adds the import tables plus `leads.import_job_id` and the
student score/year columns (D-039):

| Table | Purpose and key columns |
| --- | --- |
| `import_jobs` | One upload: `source_name`, filename, `storage_key`, `file_type`, status, `headers`, `mapping`, row counters, `uploaded_by_id` |
| `mapping_templates` | Reusable `source_name` → `mapping` JSON, unique per source name (D-042) |
| `import_row_results` | One row outcome: `row_number`, status (`created`/`merged`/`duplicate`/`rejected`), stable `reason`, optional `student_id`/`lead_id`, `raw_row` |

Flow:

1. `POST /api/leads/import` validates the upload, parses headers, stores the
   file, and returns an `uploaded` job. CSV and XLSX are supported; files over
   10 MB or 10,000 rows are rejected before processing.
2. `POST /api/imports/{id}/mapping` validates the mapping against the system
   fields, saves/upserts the template by source name, and starts processing.
   With `celery` the API commits `processing` and enqueues the task; with
   `inline` the same service runs in the request.
3. The worker re-reads the stored file and validates/normalises every row.
   Required: name plus email or phone. Optional: course, score, graduation year,
   source, campus, admission cycle. Catalogue values must exist; unknown values
   reject with a stable reason.
4. Outcomes: `created` (new student and lead), `merged` (existing student, no
   lead for that programme/cycle; fill empty fields only), `duplicate` (a lead
   already exists), or `rejected` (validation/conflict). The job counters are the
   sum of these outcomes; processing failures set `failed` with a safe message.
5. `GET /api/imports` lists jobs, `GET /api/imports/{id}` returns one,
   `GET /api/imports/mapping-template` returns a saved mapping, and
   `GET /api/imports/{id}/errors.csv` streams `row_number,reason` only (D-043).

Storage is behind `app/integrations/storage/`: `LocalStorage` writes under
`LOCAL_STORAGE_PATH` for local/dev, `MemoryStorage` is the mock, and the factory
keeps local disk even when `USE_MOCK_STORAGE=true` so a Celery worker can read
the upload (D-044). Import endpoints require `leads.view_all`.
### Duplicate review (M2.4)

`app/services/deduplication.py` is the pure matcher: exact email or phone links
to an existing student; email and phone pointing at different students is a
conflict; a name-only hit is flagged; no hit creates a new student. Import keeps
the M2.3 counts while adding candidates (D-045–D-048):

| Situation | Import outcome | Candidate |
| --- | --- | --- |
| Email or phone matches one student | `merged` or `duplicate` | none |
| No contact match, same name as an existing student | row creates a student/lead (`created`) | pending `name_only` |
| Email and phone match different students | row is `rejected` (`conflicting_contact`) | pending `conflicting_contact` |

Migration `0006` adds `duplicate_candidates` with the existing student, the new
name-only student, the conflicting student, import job/row provenance, raw row,
status, resolution, and resolver/timestamp. `GET /api/duplicates` lists pending
candidates by default; `POST /api/duplicates/{id}/resolve` accepts
`{"action": "merge" | "keep_separate" | "reject"}` and returns 409 if already
resolved. A merge fills only empty target fields, moves leads (dropping a lead
that duplicates the target's enquiry), moves consent/timeline rows, and deletes
the source student; reject deletes the newly created name-only student, while a
conflicting pair keeps both existing students. Both endpoints require
`leads.view_all`.

### Lifecycle state machine (M2.5)

`app/services/lifecycle.py` owns the only write path for
`leads.lifecycle_status` (D-049–D-051). The transition table is linear along the
FR-03 funnel; every active state can close to `Lost`, `Disqualified`,
`Unresponsive`, or `Opted Out`; `Converted` is terminal for transition purposes.
A terminal lead can only reopen to `New Enquiry`, and only an Admission Manager
acting as a user can do it.

| Actor | Normal transition | Convert | Reopen terminal |
| --- | --- | --- | --- |
| User (Admission Manager / `leads.view_all`) | yes | yes | yes |
| User (other roles) | yes | no | no |
| System event | yes | yes | no |
| AI agent | yes | no | no |

`transition(session, lead_id, to_state, actor, reason)` validates the pair,
updates the lead, and inserts exactly one `lifecycle_transition` timeline event
with `from_state`, `to_state`, and `reason`. Rejections raise
`InvalidLifecycleTransition` or `TransitionNotPermitted`, log only the lead and
state names, and leave the row unchanged. `TransitionActor.from_user(user)`
builds the actor from the loaded role/permission graph; it succeeds the current
`leads.view_all` proxy for the manager capability. M2.5 does not expose an HTTP
endpoint yet (R-011); M2.7 also excludes lifecycle from `PATCH /api/leads/{id}`.

### Consent (M2.6)

Consent checks live in `app/services/consent.py`; `consent_records` remains the
append-only audit trail from M2.1 (D-052–D-056). The newest row for a
student/channel/category is authoritative:

| Latest record | Promotional | Transactional |
| --- | --- | --- |
| none | blocked | allowed |
| granted | allowed | allowed |
| revoked | blocked | blocked |

`can_send(session, student_id=..., channel=..., category=...)` is the guard that
M3.3's single messaging entry point will call. `record_consent` appends a grant
(or revocation with `granted=false`); `revoke_consent` is the DELETE path.
`POST /api/students/{id}/consent` and
`DELETE /api/students/{id}/consent/{channel}/{category}` require
`leads.view_all`, default `source`/`method` to `staff`/`manual_entry`, and return
the appended record. Unknown students are 404.

When a promotional revocation leaves no channel with a granted promotional
record, active leads are closed as `Opted Out` through the lifecycle service
(system actor, timeline events), unless
`CONSENT_PROMOTIONAL_OPT_OUT_LIFECYCLE=false`. Transactional consent is
independent, so a promotional opt-out does not block booking confirmations. A
single revoke with another promotional channel still granted does not close
leads.

### Lead CRUD and search (M2.7)

`app/api/leads.py` now serves the authenticated lead surface. The router has no
router-wide permission because reads and writes share `leads.view_all` or
`leads.view_assigned`, while the bulk import route stays manager-only.
Resource checks use the M1.3 rule: a lead outside the caller's scope is a 404,
identical to a missing id.

`GET /api/leads` accepts `limit` (1–100, default 25), an opaque cursor, a
`created_at`/`updated_at` sort (prefix `-` for descending), lifecycle,
programme, source, campus, assigned-counsellor, and created-date filters. The
cursor encodes the sort value plus lead id in base64; the next page uses a
strict `(value, id)` comparison so inserts do not shift rows between pages.
Counsellors without `leads.view_all` are always constrained to their own
`assigned_counsellor_id`.

`GET /api/leads/{id}` returns the lead, student, latest consent decision per
channel/category, and an `assessments` list. The list is empty until the
assessment model arrives in M6; the response shape is already stable.

`POST /api/leads` normalises email/phone, requires at least one contact key, and
calls `services.leads.create_or_get_lead`, which applies the same
`decide_match` policy as import: an existing student/lead is returned with
`duplicate_detected=true` (HTTP 200), a name-only match creates a pending
candidate, and conflicting email/phone owners return 409. Counsellors create
leads assigned to themselves; assigning anyone else needs `leads.assign`.

`PATCH /api/leads/{id}` accepts student/lead fields except lifecycle.
`LeadUpdateRequest` forbids extra fields, so `lifecycle_status` is a 422. Email
and phone remain unique across students; clearing both is a 422. Changing
`assigned_counsellor_id` also requires `leads.assign`. Lifecycle writes continue
to go through M2.5 (R-011).

### Public web enquiries (M2.8)

`POST /api/public/enquiries` is the only unauthenticated write path. The request
is validated and normalised with the M2.2 helpers, then `services.enquiries`
applies the same ordering every time:

1. Redis fixed-window rate limit keyed by client IP (default 10 requests per
   3,600 seconds; Lua makes the increment + first expiry atomic). Redis failure
   is a 503, not an unlimited path.
2. CAPTCHA verification through `integrations/captcha`; the current adapter is a
   deterministic mock, selected while `USE_MOCK_CAPTCHA=true`.
3. `create_or_get_lead` with the `Website` source, so duplicates, name-only
   candidates, and conflicting contacts follow the import/M2.7 rules.
4. Consent rows with `source=method=web_form` for the channels supplied:
   promotional and/or transactional for email, and for WhatsApp when a phone is
   present. Missing checkboxes create no consent row.

The endpoint returns only the lead/student ids, `duplicate_detected`, and a
`received` status; it never echoes contact data. The lead is immediately visible
in `GET /api/leads` to a manager. Programmes can be selected by id, name, or code;
campuses by id or name. The optional message is accepted but not persisted
because no enquiry-message column exists yet.

### Partner API ingestion (M2.9)

`api_keys` (migration `0007`) stores a random key's SHA-256 hash and a short
prefix, never the plaintext. A key belongs to exactly one `lead_sources` row and
may have an expiry and an active flag. An admin with `integrations.manage` calls
`POST /api/integrations/api-keys` with a source id/name and receives the
plaintext key once. `POST /api/integrations/leads` accepts that key through
`X-API-Key` or `Authorization: Bearer`, rejects missing/invalid/expired keys with
401, and always uses the key's source. A body `source` is ignored so a partner
cannot write into another channel.

The request body is a JSON array of canonical lead objects (a `{ "leads": [...] }`
envelope is also accepted). Every record runs through the M2.3 import parser, so
email/phone/name/score/year normalisation and catalogue names/ids behave exactly
like CSV import. The ingest service commits each record in its own savepoint;
an invalid record, unknown programme/campus, conflicting contacts, or concurrent
contact insert is reported in that record's result without aborting the batch.
The shared `create_or_get_lead` path supplies duplicate and name-only handling,
and conflicting contacts create a pending `conflicting_contact` candidate.

`created` means a new student and lead; `merged` means a known student gained a
lead; `duplicate` means the same student/programme/cycle already existed;
`rejected` includes a stable reason. `API_INGESTION_MAX_RECORDS` defaults to 1,000
and is checked before any write (413). `core/webhooks.py` provides
`sign_webhook`/`verify_webhook_signature` using `t=<unix>,v1=<hmac-sha256>` with
a five-minute default tolerance; no provider webhook route uses it yet.

### Frontend lead management (M2.10)

The authenticated Next.js app now renders the M2 lead workflows. Routes are
permission-scoped in the UI and always re-checked by the API (R-009):

- `/sections/leads` — manager list with a search box, lifecycle/programme/
  campus/source filters, and cursor paging. Previous pages replay saved cursors
  so a stack of `(sort value, id)` cursors never returns to page one.
- `/sections/my-leads` — the same list for `leads.view_assigned`; the API adds
  the counsellor scope.
- `/sections/leads/new` — validated manual creation; a `duplicate_detected`
  response shows the existing lead instead of navigating to a new one.
- `/sections/leads/import` — three steps: upload (headers only), column mapping
  (saved template by source name, otherwise header guessing, with ignored
  columns removed from the payload), then results. Results show total/created/
  merged/duplicate/rejected counts and offer the error CSV. Processing is polled
  until `completed`/`failed`; local and CI e2e runs use `IMPORT_PROCESSING_MODE=inline`.
- `/sections/leads/[id]` — student and lead details, consent table with
  grant/revoke controls for managers, the timeline placeholder, and a lifecycle
  form built from `allowed_transitions`. The API still rejects invalid,
  unpermitted, or out-of-scope transitions.

Supporting API additions:

- `GET /api/leads?search=` adds an escaped `ILIKE` contains match over student
  first/last/full name, email, and phone; it composes with every existing filter
  and the caller's scope (D-060).
- `GET /api/catalogues` returns active programmes, campuses, and sources to lead
  staff so filters and forms do not need one request per catalogue.
- List rows embed a `student` summary plus programme/campus/source/counsellor
  names (eager-loaded, no per-row follow-up); detail adds the same names and
  `allowed_transitions` in funnel order.
- `POST /api/leads/{id}/lifecycle` accepts `to_state` + `reason` and delegates to
  the M2.5 service, mapping invalid pairs to 422, permission failures to 403,
  and out-of-scope/missing leads to 404 (R-011 resolved).

Frontend API clients live in `lib/leads-api.ts` and `lib/imports-api.ts`; the
latter also holds `suggestMapping`, `mappingPayload`, and the system-field list
used by the mapping component. `lib/lifecycle.ts` owns labels, tones, and date/
name formatting. `lib/api.ts` now leaves multipart bodies untouched so the
browser sets the upload boundary.

## 9. Communication providers (M3.1)

Business code depends on `app/integrations/email/base.py`, never on a vendor SDK.
The `EmailProvider` protocol is `send(message) -> provider_message_id`,
`parse_inbound(webhook_payload) -> InboundMessage`, and
`verify_webhook(headers, body) -> bool`. `EmailMessage` and `InboundMessage` are
provider-neutral dataclasses; shared helpers parse ``Name <address>`` strings,
mapping addresses, headers supplied as JSON or text, and ISO timestamps.

`MockEmailProvider` is the default from `build_email_provider`. It writes
`mock_email_messages` (migration `0008`) with direction (`outbound`/`inbound`),
provider message id, addresses, subject, text/HTML bodies, status, `in_reply_to`,
and `last_event_at`. `send` returns `mock-<uuid>`. Test helpers
`simulate_inbound_reply` persists a parsed reply and marks the original outbound
message as `replied` when `In-Reply-To` matches; `simulate_delivery_event`
updates an outbound message to `delivered`/`opened`/`clicked`/`bounced`/
`complained`/`deferred`. Mock webhooks require
`X-Mock-Signature: sha256=<hmac-sha256>` over the raw body and fail closed when
no secret is configured.

`SendGridEmailProvider` posts the v3 payload through `httpx`, reads the
`X-Message-Id` response header, and maps transport or non-2xx responses to
`EmailDeliveryError`. Inbound Parse is authenticated with HTTP Basic
`sendgrid:<EMAIL_WEBHOOK_SECRET>`. An injected `httpx.AsyncClient` lets contract
tests exercise the request shape offline; a live send test runs only when
`EMAIL_API_KEY` and `EMAIL_CONTRACT_TO` are set. `EMAIL_PROVIDER=ses` has no
adapter yet and raises `EmailNotConfigured` (R-016).

WhatsApp is interface-only in M3: `WhatsAppProvider`, `WhatsAppMessage`,
`InboundWhatsAppMessage`, and a `StubWhatsAppProvider` whose methods raise
`WhatsAppNotImplemented`. The Cloud API adapter belongs to Phase 2.

### Messaging schema (M3.2)

Migration `0009` adds the conversation/message/event tables used by M3.3 onward:

- `conversations` — `lead_id`, `channel`, `status` (`open`/`closed`), and
  `last_message_at`. `(lead_id, channel)` is unique so inbound and outbound
  paths cannot create two threads for the same lead, and an index on
  `last_message_at` supports inbox ordering.
- `messages` — `conversation_id`, `direction`, `channel`, `content_text`,
  `content_html`, nullable `provider_message_id`, `status`, `intent`, and a
  nullable `created_by_agent_action_id`. Provider ids are unique per channel
  (`UNIQUE (channel, provider_message_id)`), and NULL provider ids are allowed
  for drafts or failed sends. The agent action id is deliberately a plain UUID
  until the agent-run table exists.
- `message_events` — `message_id`, `event_type`, a globally unique
  `provider_event_id`, `occurred_at`, and `created_at`. Events are append-only.

`leads.id → conversations.lead_id`, `conversations.id → messages.conversation_id`,
and `messages.id → message_events.message_id` all use `ON DELETE CASCADE`, so
removing a lead removes its communication history. The unique provider event id
is the idempotency boundary (D-066): webhook handlers insert the event before
applying a status change, so a replayed delivery is rejected by the database
instead of updating the message twice. Inbound replies, status transitions, and
timeline emissions are implemented in M3.3 onward; M3.2 ships the schema and
its database-level guarantees.

## 10. Database migrations

Alembic runs against the async SQLAlchemy engine. The first migration (`0001`)
enables the `vector`, `btree_gist`, and `pgcrypto` extensions and is reversible.
Migrations are the only way schema changes are applied; the API container runs
`alembic upgrade head` before starting. `0004` adds the lead CRM tables and
`0005` adds the import pipeline plus student score/year columns and `0006` adds
duplicate candidates; `0007` adds source-scoped hashed API keys (§8); `0008`
adds the mock email provider's `mock_email_messages` table (§9); and `0009` adds
the messaging schema (§9). M2.7, M2.8, and M2.10 add no migration; their
contracts are recorded in D-056/D-057/D-059, and M2.9 is recorded in D-058. The
migration test downgrades to base, upgrades to head, and asserts that every
table disappears again, so every revision must round-trip.

## 11. Testing

| Layer | Location | Requirements |
| --- | --- | --- |
| Unit | `backend/tests/unit` | No infrastructure |
| Integration | `backend/tests/integration` | PostgreSQL and Redis |
| Frontend unit | `frontend/tests` | Node only |
| End-to-end | `frontend/e2e` | API on `:8000` with `IMPORT_PROCESSING_MODE=inline`, seeded demo users, Chromium |

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
404, manager 200, unknown id 404. Normaliser cases live in
`tests/unit/test_normalisation.py` and must keep 100% branch coverage of
`app/core/normalisation.py`.

Import tests live in `tests/integration/test_import_pipeline.py` with programmatic
fixtures in `tests/fixtures/import_files.py`: a 100-row mixed file must yield
exactly 85 created, 5 duplicates, and 10 rejected; re-importing it must create
nothing; a merged-header XLSX must return 422; 10,001 rows must return 413; the
error CSV must contain the original row numbers and stable reasons; mapping
templates must round-trip; and the endpoints must require `leads.view_all`.
Parser/validator cases are in `tests/unit/test_import_parsing.py`.

Duplicate tests: `tests/unit/test_deduplication.py` covers email-only,
phone-only, both-same, both-conflict, name-only, and no-match decisions;
`tests/integration/test_import_pipeline.py` proves name-only candidates merge
into one student, conflicting contacts create a reviewable candidate and reject
the row, and an existing non-empty contact is never overwritten.

Lifecycle tests: `tests/unit/test_lifecycle.py` checks every allowed and
disallowed pair against the transition table, the linear funnel, closing
transitions, agent/counsellor conversion denial, system conversion, and reopen
rules. `tests/integration/test_lifecycle_transitions.py` walks the whole funnel
and asserts one timeline event per accepted transition, proves a rejected
transition changes nothing, and covers agent conversion denial plus manager
reopen.

Consent tests: `tests/unit/test_consent.py` covers the missing-record defaults
and explicit grant/revoke decisions. `tests/integration/test_consent.py` proves
the API appends records, promotional revocation blocks sends, transactional
messages remain allowed until explicitly revoked, the last promotional channel
closes active leads, another granted channel prevents that side effect, and
counsellors are rejected.

Lead API tests (`tests/integration/test_leads_api.py`) cover stable cursor
pages, counsellor scoping, filters, detail/consent summary, 404 for foreign or
missing leads, manual creation dedupe/name-only/conflict paths, PATCH field
updates, lifecycle rejection, assignment permissions, and a separately marked
`performance` test that bulk-inserts 10,000 leads and checks list P95 against a
conservative 1.5 s threshold.

Lead screen support tests (`tests/integration/test_lead_screens_api.py`) cover
the escaped search over name/email/phone (including a literal `%` and counsellor
scoping), catalogue access and role denial, actor-filtered
`allowed_transitions`, lifecycle endpoint success and 422/403/404 cases with
timeline writes, and manual creation defaults used by the form.

Public enquiry tests (`tests/integration/test_public_enquiries.py`) submit the
real endpoint and assert the Website source, consent rows, missing-checkbox
behaviour, duplicate flag, CAPTCHA rejection, contact requirement, programme
validation, appearance in the manager lead list, and the 11th-request 429 with a
`Retry-After` header. `tests/unit/test_captcha.py` covers the mock verifier and
factory selection.

Partner ingestion tests (`tests/integration/test_api_ingestion.py`) provision a
key as admin, reject manager/anon creation, assert the key's source overrides a
body source, report every per-record outcome in one batch, isolate invalid
records, create conflicting-contact candidates, verify missing/invalid/expired
keys, enforce the 1,000-record 413 before writes, accept the envelope form, and
push 500 leads successfully. `tests/unit/test_webhooks.py` covers valid HMAC
signatures, tampering, wrong secrets, stale timestamps, and malformed headers.

Provider contract tests (`tests/integration/test_email_provider_contract.py`)
parameterise the mock and a SendGrid adapter backed by `httpx.MockTransport`:
both must return a provider id and record the send, parse the shared inbound
payload, and reject an unsigned webhook. Mock-only tests cover HMAC body binding,
delivery-event status changes, inbound reply linkage, duplicate inbound ids, and
the unknown-message error. SendGrid-only tests inspect the v3 payload/auth header
and a non-2xx failure; a live send is skipped unless `EMAIL_API_KEY` and
`EMAIL_CONTRACT_TO` are set. Factory/default and WhatsApp stub tests live in
`tests/unit/test_email_providers.py`.

Messaging model tests (`tests/integration/test_message_model.py`) prove the
M3.2 guarantees against PostgreSQL: conversation defaults and the unique
`(lead_id, channel)` constraint, provider-message uniqueness per channel,
rejection of a duplicate `provider_event_id` without a second status change,
and cascade deletion from lead through conversation, message, and event.

Frontend unit tests (`frontend/tests/navigation.test.tsx` and
`import-mapping.test.tsx`) cover the permission-filtered menu and prove the
mapping component's suggested/saved/ignored selections produce the payload the
API receives.

Playwright (`frontend/e2e/auth.spec.ts`) drives the real stack: it logs in as
each seeded role, asserts the role-specific menu, logs out, and confirms a
reload cannot restore the session. `frontend/e2e/leads.spec.ts` imports a
100-row CSV through the wizard, asserts the 100/85/0/5/10 counts and the 10-row
error report, then signs in as a counsellor and proves an unassigned lead is
absent from `/sections/my-leads`. The import spec rewrites the committed fixture
with unique contacts per run, so repeated local runs still exercise creation
rather than becoming all-duplicate runs. Both specs need the API with
`IMPORT_PROCESSING_MODE=inline`; `make test-e2e` runs them against a locally
running API, and CI uses a dedicated job with Postgres, Redis, migrations, seed,
Uvicorn, and Chromium (D-031, D-062).

CI (`.github/workflows/ci.yml`) runs backend lint/type-check/tests against
`pgvector/pgvector:pg16` and Redis service containers, frontend
lint/type-check/tests/build, and Docker image builds.

## 12. Decisions, status, and handoff

This document describes the resulting design. The **decision log with rationale**,
current milestone status, environment quirks, known risks, and open engineering
questions live in [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md). Workflow rules for
contributors and coding agents are in [`../AGENTS.md`](../AGENTS.md).

When a decision changes the design: append the decision to
`PROJECT_CONTEXT.md` first, then update the relevant section here.
