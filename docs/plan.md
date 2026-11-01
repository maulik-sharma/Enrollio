# 0. How to use this plan

Give the coding agent this entire section. Ask it to work through milestones in order. Each task has an ID, subtasks, tests, and a "Done when" condition. The agent must not mark a task complete until its tests pass.

## 0.1 Rules of engagement

1. Build milestones in order. Do not begin a milestone until the previous milestone's tests pass.
2. Every task ends with passing tests. Run `make test` after each task. A task is not complete if any test fails.
3. Agents never touch the database directly. LLM and agent code calls typed tools in `app/agents/tools/`. Each tool calls a service function. Services enforce business rules and permissions.
4. All external providers sit behind interfaces. Email, WhatsApp, calendar, storage, transcription, and LLM each have an abstract interface and at least one mock implementation. Tests and the demo use mocks by default. Real providers are enabled by environment variable.
5. No secrets in code. Use environment variables loaded through a settings module. Maintain `.env.example` with placeholder values.
6. Schema changes use Alembic migrations only. Do not edit tables by hand.
7. Every API endpoint declares its required permission. Each endpoint has at least one test confirming that an unauthorised role receives 403.
8. Never log PII. Emails, phone numbers, and recording content must be masked in logs. A test checks this for the import and messaging modules.
9. Do not add features outside the task list. If something seems missing, add it to `OPEN_QUESTIONS.md` and continue.
10. Commit after each task with the task ID in the message (for example, `M2.3: CSV/XLSX import pipeline`).

## 0.2 Repository structure

```text
admission-agent/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/            # config, security, permissions, db session, logging
│   │   ├── api/             # FastAPI routers, one per domain
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── services/        # business logic (the only layer that writes data)
│   │   ├── repositories/    # DB query helpers
│   │   ├── agents/
│   │   │   ├── orchestrator.py
│   │   │   ├── tools/       # typed tools exposed to agents
│   │   │   ├── enquiry.py
│   │   │   ├── knowledge.py
│   │   │   ├── lead_intel.py
│   │   │   ├── communication.py
│   │   │   ├── scheduling.py
│   │   │   ├── conversation.py
│   │   │   └── followup.py
│   │   ├── workflows/       # event handlers and rule engine
│   │   ├── integrations/
│   │   │   ├── email/       # interface, smtp/ses impl, mock impl
│   │   │   ├── whatsapp/    # interface, cloud api impl, mock impl
│   │   │   ├── calendar/    # interface, google impl, internal/mock impl
│   │   │   ├── llm/         # interface, provider impls, mock impl
│   │   │   ├── speech/      # interface, whisper impl, mock impl
│   │   │   └── storage/     # interface, local/S3 impl
│   │   └── workers/         # Celery app and task definitions
│   ├── migrations/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── eval/            # RAG and MOM evaluation datasets and scripts
│   │   └── fixtures/        # sample CSV/XLSX files, documents, audio stubs
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── app/                 # Next.js App Router
│   ├── components/
│   ├── lib/                 # API client, auth, types
│   ├── tests/               # Vitest unit and Playwright e2e
│   └── Dockerfile
├── docker-compose.yml
├── Makefile
├── .env.example
└── docs/
    ├── PRD.md
    ├── OPEN_QUESTIONS.md
    └── ARCHITECTURE.md
```

## 0.3 Definition of done (applies to every task)

- Code implemented and type-checked (mypy or pyright on backend, `tsc --noEmit` on frontend).
- Linter passes (ruff on backend, eslint on frontend).
- Unit and integration tests for the task pass.
- Any new endpoint has an authorisation test.
- Migration created and reversible, if the schema changed.
- Relevant documentation updated in `docs/`.
- Committed with the task ID.

---

# Milestone M0: Foundation (Week 1)

**Goal:** A running skeleton with database, authentication scaffolding, background worker, and CI.

## M0.1 Repository and tooling setup

- Create the repository structure in Section 0.2.
- Initialise backend with Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic, pytest, ruff, mypy.
- Initialise frontend with Next.js 15 (App Router), TypeScript, Tailwind CSS, ESLint, Vitest.
- Create Makefile with targets: `dev`, `test`, `lint`, `migrate`, `seed`.

**Tests:** `make lint` passes on an empty project. A test imports `app.main` and confirms the app object exists.

**Done when:** Both projects build and the Makefile targets run without error.

## M0.2 Docker Compose environment

- Services: api (FastAPI), web (Next.js), db (PostgreSQL 16 with pgvector image), redis, worker (Celery), minio (S3-compatible storage).
- Enable extensions in the first migration: `vector`, `btree_gist`, `pgcrypto`.
- Health endpoints: `/healthz` (process up) and `/readyz` (database and Redis reachable).

**Tests:**

- Integration test: `/readyz` returns 200 when Postgres and Redis are running, and 503 when Postgres is stopped.
- Smoke test: `docker compose up` brings all services to healthy state within 120 seconds.

**Done when:** `docker compose up` runs the full stack locally.

## M0.3 Configuration and secrets

- Implement `core/config.py` using Pydantic Settings. Fields: database URL, Redis URL, JWT secret, LLM provider and key, email provider settings, storage settings, feature flags for each provider (`USE_MOCK_EMAIL=true` by default).
- Write `.env.example` with every key and a comment.
- Fail fast at startup if a required secret is missing in production mode.

**Tests:**

- Unit test: missing JWT secret in `ENV=production` raises a configuration error.
- Unit test: `USE_MOCK_*` flags default to true.

**Done when:** App starts with `.env.example` values copied to `.env`.

## M0.4 Logging and PII masking

- Structured JSON logging with request ID.
- Masking utility for emails (`r***@gmail.com`), phone numbers (`98XXXX1234`), and free text fields marked sensitive.
- Apply the masking filter to all log handlers.

**Tests:**

- Unit test: masking utility outputs expected formats for 10 sample values.
- Integration test: an endpoint that logs a payload containing an email and phone produces log output with neither visible in full.

**Done when:** Logs contain no raw PII in the test scenarios.

## M0.5 CI pipeline

GitHub Actions workflow: lint, type-check, backend tests (with Postgres service container), frontend tests, Docker build.

**Tests:** A deliberately failing test on a branch causes the pipeline to fail. Removing it makes it pass.

**Done when:** A pull request runs the full pipeline.

---

# Milestone M1: Identity and RBAC (Week 1)

**Goal:** Users can log in, and every endpoint enforces role-based permissions.

## M1.1 Data model for users, roles, and permissions

- Tables: `users`, `roles`, `permissions`, `role_permissions`, `user_roles` (a user may hold more than one role).
- Seed roles: System Admin, Admission Manager, Admission Counsellor.
- Seed permissions from Section 4 of the PRD.

**Tests:**

- Migration test: upgrade and downgrade both succeed on an empty database.
- Unit test: seed produces the expected role-permission matrix.

**Done when:** `make seed` creates roles and permissions idempotently (running twice causes no errors and no duplicates).

## M1.2 Authentication

- `POST /api/auth/login` with email and password. Password hashed with Argon2.
- Access token (JWT, 15 minutes) returned in response body. Refresh token (7 days) set as httpOnly, Secure, SameSite=Strict cookie.
- `POST /api/auth/refresh` rotates refresh tokens. Reusing a revoked refresh token revokes the whole session family.
- `POST /api/auth/logout` revokes the refresh token.
- `GET /api/auth/me` returns the current user with roles and permissions.
- Account lockout after 5 failed logins within 15 minutes.

**Tests:**

- Unit test: password hashing and verification.
- Integration tests: valid login returns tokens; wrong password returns 401 without revealing whether the email exists; refresh rotation works; reuse of old refresh token fails and revokes the session; lockout triggers after 5 failures.

**Done when:** All auth tests pass and the login flow works in the frontend.

## M1.3 Permission enforcement

- Implement `require_permission("leads.view_all")` FastAPI dependency.
- Implement scope checks: for counsellors, lead access is limited to leads where `assigned_counsellor_id` equals the current user.
- Create a single helper `can_access_lead(user, lead)` used by all lead-related services.

**Tests:**

- Unit test: permission dependency rejects users without the permission with 403.
- Integration test: counsellor A cannot read a lead assigned to counsellor B (expects 404, not 403, to avoid revealing existence).
- Integration test: Admission Manager can read any lead.

**Done when:** The cross-counsellor access test passes. This is a mandatory security gate.

## M1.4 User and role administration API

- `GET/POST /api/users`, `PATCH /api/users/{id}`, `POST /api/users/{id}/deactivate`.
- `GET /api/roles`, `PUT /api/roles/{id}/permissions`.
- Deactivated users cannot log in and their refresh tokens are revoked.

**Tests:**

- Integration: only System Admin can create users (other roles get 403).
- Integration: deactivated user's existing access token is rejected within one request cycle (check user status on each request).

**Done when:** Admin can create a counsellor, assign a role, and deactivate them.

## M1.5 Frontend authentication shell

- Login page, protected route wrapper, role-aware navigation menu, logout.
- API client attaches access token and refreshes on 401.

**Tests:**

- Vitest: navigation items render only for permitted roles.
- Playwright: login as each seeded role, confirm correct menu items appear, logout works.

**Done when:** Three seeded users can log in and see different menus.

---

# Milestone M2: Lead CRM and Ingestion (Week 2)

**Goal:** Central CRM with bulk import, validation, duplicate detection, lifecycle, consent, and timeline foundation.

## M2.1 Core data model for students, leads, programmes, and campuses

- Tables: `students`, `leads`, `programmes`, `campuses`, `lead_sources`, `consent_records`, `timeline_events`.
- `students`: id, first\_name, last\_name, email\_normalised, phone\_e164, date\_of\_birth (nullable), created\_at.
- `leads`: id, student\_id, programme\_id, campus\_id, source\_id, admission\_cycle, lifecycle\_status, assigned\_counsellor\_id, raw\_import\_row (JSONB), created\_at, updated\_at.
- Unique constraint on (student\_id, programme\_id, admission\_cycle) to prevent duplicate leads.
- `timeline_events`: id, student\_id, lead\_id (nullable), event\_type, actor\_type (user/agent/system), actor\_id, payload (JSONB), created\_at. Index on (student\_id, created\_at).

**Tests:**

- Migration test: upgrade and downgrade.
- Integration test: inserting a second lead with the same student, programme, and cycle fails at the database level.

**Done when:** Schema is migrated and constraint tests pass.

## M2.2 Normalisation utilities

- **Email normaliser:** trim, lowercase, basic format validation (use email-validator library).
- **Phone normaliser:** parse with phonenumbers library using default region IN, output E.164. Reject numbers that fail validation.
- **Name normaliser:** trim, collapse whitespace, preserve case for display.
- **Score normaliser:** accept numeric values between 0 and 100, with or without %; reject others.

**Tests:** Unit tests with at least 20 cases per normaliser, including: `Rahul.Sharma@Gmail.com` → `rahul.sharma@gmail.com`; 98XXXXXXXX variants with and without +91; 85% → 85; abc → error; empty string → error.

**Done when:** All normaliser tests pass with 100% branch coverage.

## M2.3 CSV/XLSX import pipeline

- Endpoint `POST /api/leads/import` accepts file upload. Creates an `import_jobs` record with status uploaded.
- Parsing: use openpyxl for XLSX and pandas/csv module for CSV. Limit: 10,000 rows, 10 MB file size.
- Column detection: read headers, return them to the client for mapping.
- Mapping endpoint `POST /api/imports/{id}/mapping` accepts mapping from source columns to system fields. Save as reusable `mapping_templates` keyed by source name.
- Processing runs as a Celery task. Each row is validated, normalised, and either created, merged, or rejected. Results stored per row in `import_row_results`.
- Required fields: name, and at least one of email or phone. Optional fields: course, score, graduation year, source, campus.
- Rejected rows store the reason (for example: invalid\_phone, missing\_contact, unknown\_programme).
- Error report endpoint `GET /api/imports/{id}/errors.csv`.

**Tests:**

- Unit: row validator with 15 cases.
- Integration: upload a fixture file with 100 valid rows, 10 invalid rows, and 5 duplicates. Expected: 85 created or merged, 10 rejected, 5 flagged duplicates. Counts must match exactly.
- Integration: an XLSX file with merged header cells produces a clear error rather than a crash.
- Integration: a 10,001-row file is rejected with a clear message.
- Integration: error CSV contains the original row number and reason.

**Done when:** The fixture test produces the expected counts and the error report downloads correctly.

## M2.4 Duplicate detection and merge

- Matching logic: exact match on normalised email or phone links to existing Student (FR-02).
- If the matched student has no lead for the incoming programme and cycle, create a new lead.
- Merge policy: fill empty fields on the existing record from the incoming record. Never overwrite non-empty values.
- Name-only matches create a `duplicate_candidates` record for manual review.
- Endpoint `GET /api/duplicates` lists candidates. `POST /api/duplicates/{id}/resolve` accepts merge, keep\_separate, or reject.

**Tests:**

- Unit: matching function covers email-only match, phone-only match, both match, neither match, and conflicting matches (email points to student A, phone points to student B — flag for review, do not merge).
- Integration: importing the same CSV twice creates no new students and no new leads.
- Integration: an existing non-empty email is not overwritten by an import containing a different email for the same phone.

**Done when:** Re-importing a file is idempotent and conflicting matches are flagged.

## M2.5 Lifecycle state machine

- Implement `services/lifecycle.py` with an explicit transition table (the states in FR-03).
- Function `transition(lead_id, to_state, actor, reason)` validates the transition, updates the lead, writes a timeline event, and returns the updated lead.
- Terminal states cannot transition except through an explicit reopen action by an Admission Manager.
- Converted requires a system\_event actor or an Admission Manager with the `admission.mark_converted` permission.

**Tests:**

- Unit: every allowed transition succeeds; every disallowed transition raises an error. Generate the test matrix from the transition table.
- Unit: converting by an AI agent actor is rejected.
- Integration: each transition creates exactly one timeline event.

**Done when:** The transition matrix test covers all combinations of states.

## M2.6 Consent management

- Service `consent.py`: record consent (channel, category, source, method), revoke consent, check consent before send.
- Opt-out handler: stores opt-out, updates lead lifecycle to Opted Out for promotional categories only if the student opts out completely (configurable).
- Endpoint `POST /api/students/{id}/consent` and `DELETE /api/students/{id}/consent/{channel}/{category}`.

**Tests:**

- Unit: `can_send(student, channel, category)` returns false after revocation and true before.
- Integration: opt-out via endpoint blocks subsequent promotional send attempts (tested again in M3).
- Integration: transactional messages are still allowed after a promotional opt-out (where the rule permits).

**Done when:** Consent checks are called from the single messaging entry point (built in M3.3).

## M2.7 Lead CRUD and search APIs

- `GET /api/leads` with pagination (cursor-based), filters (lifecycle, programme, source, campus, assigned counsellor, date range), and sorting.
- `GET /api/leads/{id}` returns student, lead, latest assessments, consent summary.
- `POST /api/leads` manual creation (goes through the same dedupe logic as import).
- `PATCH /api/leads/{id}` updates editable fields (not lifecycle; lifecycle uses M2.5).
- Permission scope applied per M1.3.

**Tests:**

- Integration: pagination returns stable results across pages.
- Integration: filter combinations return correct subsets (test with 5 combinations).
- Integration: manual creation of a duplicate returns the existing lead with a `duplicate_detected` flag.
- Performance test: list endpoint P95 under 500 ms with 10,000 seeded leads (run with k6 or pytest-benchmark).

**Done when:** Performance test passes on the seeded dataset.

## M2.8 Web enquiry form (public endpoint)

- Public `POST /api/public/enquiries` with rate limiting (10 requests per IP per hour) and CAPTCHA token verification (use a mock verifier in tests).
- Stores consent checkboxes as consent records with method `web_form`.
- Runs through the same dedupe and lead creation path as import.

**Tests:**

- Integration: submission creates a lead with source website.
- Integration: exceeding rate limit returns 429.
- Integration: missing consent checkbox still creates the lead but without promotional consent.

**Done when:** Form submission flows into the CRM and appears in the lead list.

## M2.9 Generic API ingestion endpoint

- `POST /api/integrations/leads` authenticated with an API key (stored hashed) scoped to a lead source.
- Accepts JSON array of leads conforming to the canonical schema. Same validation and dedupe as import.
- Webhook signature verification helper, used when partners push events.

**Tests:**

- Integration: request without a valid API key returns 401.
- Integration: request with a valid key but a payload exceeding 1,000 records returns 413.
- Integration: a valid batch returns per-record results.

**Done when:** A test partner script can push 500 leads successfully.

## M2.10 Frontend: lead management

- Import wizard: upload, column mapping (with saved templates), preview, submit, results with error download.
- Lead list with filters, search, pagination.
- Lead detail page: student profile, lead details, lifecycle control (transition buttons respecting permissions), consent panel, timeline (empty state for now).
- Manual lead creation form with validation.

**Tests:**

- Vitest: mapping component produces the correct payload.
- Playwright: complete import flow with the fixture file, verify counts displayed match backend.
- Playwright: counsellor logging in sees only assigned leads in the list.

**Done when:** The import flow works end to end in the browser.

---

# Milestone M3: Communication Core and Campaigns (Week 3–4)

**Goal:** Outbound campaigns, inbound email handling, threaded conversations, provider webhooks, all behind consent checks.

## M3.1 Provider interfaces and mock implementations

- EmailProvider interface: `send(message) -> provider_message_id`, `parse_inbound(webhook_payload) -> InboundMessage`, `verify_webhook(headers, body) -> bool`.
- WhatsAppProvider interface (stub only in M3; implemented in Phase 2).
- Mock email provider: stores messages in a database table and exposes a test helper to simulate inbound replies and delivery events.
- Real SES/SendGrid adapter implemented but disabled by default. Include contract tests that run against mocks.

**Tests:**

- Contract test suite run against both mock and real adapters. Real adapter tests are skipped unless credentials are present.
- Unit: mock provider records sends and returns IDs.

**Done when:** Mock provider is used by all downstream tests.

## M3.2 Message and conversation data model

- Tables: `conversations` (id, lead\_id, channel, status, last\_message\_at), `messages` (id, conversation\_id, direction, channel, content\_text, content\_html, provider\_message\_id unique per provider, status, intent, created\_at, created\_by\_agent\_action\_id nullable).
- `message_events` (id, message\_id, event\_type, provider\_event\_id unique, occurred\_at).
- Idempotency: provider\_event\_id uniqueness prevents double processing of webhook events.

**Tests:**

- Integration: inserting a duplicate provider event ID is rejected and does not create a second status update.

**Done when:** Schema migrated and idempotency test passes.

## M3.3 Single messaging entry point

- Service `messaging.send(lead, channel, category, content, actor)` is the only path to send any message.
- Steps: check consent (M2.6), check frequency cap (default 2 promotional per 7 days), check quiet hours for non-urgent messages (queue until window), check approval requirement (if category is sensitive and no approval record exists, create pending approval), render template, call provider, record message, emit timeline event.
- Every step is logged.

**Tests:**

- Unit: each guard blocks sending independently (consent, cap, quiet hours, approval).
- Integration: a message to an opted-out student is never sent to the mock provider (assert zero provider calls).
- Integration: the 3rd promotional message within 7 days is blocked.
- Integration: sensitive-category message creates an approval item and does not call the provider.

**Done when:** A grep check in CI confirms no module calls the provider adapters directly except messaging.

## M3.4 Template engine

- Templates stored in `message_templates` (id, name, channel, category, subject, body with placeholders, version, status: draft/approved).
- Renderer replaces `{{first_name}}`, `{{programme}}`, `{{campus}}`, `{{deadline}}`, `{{counsellor_name}}`, and so on.
- Missing placeholder values cause rendering to fail with a list of missing fields. Never send partial messages.
- Unsubscribe link automatically appended to promotional emails.

**Tests:**

- Unit: rendering with all fields present produces expected output.
- Unit: missing `{{deadline}}` returns an error listing the field.
- Unit: promotional email contains an unsubscribe link; transactional email does not require one.
- Unit: HTML escaping prevents injection from student name fields (test with `<script>` in name).

**Done when:** Template tests pass with at least 10 cases.

## M3.5 Campaign and segment model and APIs

- Tables: `segments` (id, name, filter\_definition JSONB), `campaigns` (id, name, channel, template\_id, segment\_id, status, scheduled\_at, created\_by, approval\_status), `campaign_recipients` (id, campaign\_id, lead\_id, status, reason, provider\_message\_id).
- Segment evaluator converts filter JSON into a SQL query (use a whitelist of filterable fields to prevent injection).
- Endpoints: `POST /api/segments`, `POST /api/segments/{id}/preview` (returns count and sample), `POST /api/campaigns`, `POST /api/campaigns/{id}/preview` (renders for one recipient), `POST /api/campaigns/{id}/launch`, `GET /api/campaigns/{id}/report`.
- Launch above configurable size (default 500) requires approval.

**Tests:**

- Unit: segment filter JSON produces expected SQL for 10 filter combinations.
- Security: segment filter with a non-whitelisted field returns 400.
- Integration: campaign launch creates recipient rows and enqueues send tasks.
- Integration: recipients missing a required placeholder are recorded as `failed: missing_field` and the rest are sent.

**Done when:** A campaign of 300 fixture students sends to the mock provider and the report matches expected counts.

## M3.6 Campaign execution worker

- Celery task `send_campaign_batch` processes recipients in batches of 50 with rate limiting (configurable messages per second).
- Retries transient failures with exponential backoff (max 5 attempts). Permanent failures are marked and not retried.
- Task is idempotent: a recipient already marked sent is skipped if the task re-runs.

**Tests:**

- Integration: kill the worker midway (simulate by raising an exception after 100 sends) and rerun. Assert no duplicate sends to the mock provider.
- Integration: transient mock failure (fails twice, then succeeds) results in one successful send and two retries logged.
- Integration: permanent failure (invalid address) is not retried.

**Done when:** Idempotency test passes under forced failure.

## M3.7 Provider webhook handling

- `POST /api/webhooks/email` verifies signature, parses event (delivered, bounced, complained, opened, clicked), stores in `message_events`, updates message status.
- Bounces and complaints add the address to a suppression list checked by consent logic.
- Opens and clicks are stored but flagged `not_used_for_scoring`.

**Tests:**

- Integration: invalid signature returns 401 and no state change.
- Integration: bounce event suppresses future sends to that address (assert zero further mock sends).
- Integration: replayed webhook event (same provider event ID) is ignored.

**Done when:** Webhook tests pass with signatures from the mock provider.

## M3.8 Inbound email processing

- Inbound endpoint or mock simulator passes parsed message to `inbound.handle(message)`.
- Thread resolution: reply-token address (`reply+{token}@domain`) maps to conversation. Fallback: match In-Reply-To header against stored provider message IDs. Fallback: match sender email to student (flag as unthreaded if multiple leads).
- Store message with direction inbound, emit timeline event, update lead status from Contacted to Engaged if the reply is substantive (not auto-reply or bounce). Auto-reply detection uses headers such as `Auto-Submitted`.
- Trigger enquiry agent (M4).

**Tests:**

- Unit: thread resolution with each of the three strategies.
- Unit: auto-reply headers do not change lifecycle status.
- Integration: a simulated student reply appears in the correct lead's timeline and changes status to Engaged.
- Integration: unthreaded message with two matching leads is placed in an "unassigned inbound" queue.

**Done when:** Simulated reply tests pass end to end.

## M3.9 Frontend: campaigns and conversations

- Segment builder UI (filters with field whitelist).
- Campaign creation wizard: choose segment, choose template, preview, schedule or launch, approval request if needed.
- Campaign report page with status breakdown.
- Conversation view on lead detail page: threaded messages, direction indicators, status ticks.
- Unassigned inbound queue for Admission Managers.

**Tests:**

- Vitest: segment builder produces valid filter JSON.
- Playwright: create segment, preview, launch campaign to mock, see report counts.

**Done when:** Full campaign flow works in the browser against the mock provider.

---

# Milestone M4: Knowledge Base, RAG, and Enquiry Agent (Week 3–4)

**Goal:** Approved documents power grounded answers with citations. Replies are drafted, classified, and approved before sending where required.

## M4.1 Knowledge document model and upload

- Tables: `knowledge_documents` (id, title, doc\_type, version, status: draft/approved/archived, effective\_from, expires\_at, uploaded\_by, storage\_key, checksum), `document_chunks` (id, document\_id, chunk\_index, section\_title, content, token\_count, embedding vector, metadata JSONB).
- Upload endpoint accepts PDF, DOCX, TXT up to 20 MB. Verify file type from content.
- Store original in object storage. Document status starts as draft.
- Approve endpoint sets status to approved and triggers indexing. Only Admins or Admission Managers can approve.

**Tests:**

- Integration: upload with a mismatched extension (PDF content named .docx) is rejected.
- Integration: a draft document is not returned by retrieval.
- Integration: approving a document makes its chunks retrievable.

**Done when:** Approval gate tests pass.

## M4.2 Document extraction and chunking

- Extract text: pypdf for PDF, python-docx for DOCX, plain read for TXT. Flag scanned PDFs (no text layer) as requiring OCR, and do not index them until OCR is performed (OCR optional in v1).
- Chunking: split by section headings where detectable, otherwise by \~500 tokens with 80 token overlap. Each chunk keeps section title and page number where available.
- Store chunk metadata for citations.

**Tests:**

- Unit: chunker keeps chunks under 600 tokens and produces overlap.
- Unit: heading-based splitting on a fixture document with 5 sections produces 5 chunks with correct titles.
- Integration: a scanned PDF fixture is flagged, not indexed.

**Done when:** Fixture documents chunk correctly.

## M4.3 Embeddings and vector retrieval

- EmbeddingProvider interface. Default implementation: multilingual model (for example, bge-m3 via sentence-transformers locally, or a hosted embedding API). Mock implementation returns deterministic vectors based on text hash for tests.
- Index: HNSW index on `document_chunks.embedding` with cosine distance.
- Retrieval function: `retrieve(query, top_k=8, filters)` filters by status = approved, not expired, and optionally by programme or document type. Returns chunks with similarity scores.

**Tests:**

- Integration: retrieval excludes archived and expired documents (test with fixtures).
- Integration: with mock embeddings tuned for test, the correct chunk ranks first for 10 probe queries.
- Performance: retrieval P95 under 200 ms with 50,000 chunks (benchmark).

**Done when:** Retrieval tests and benchmark pass.

## M4.4 RAG answer generation with grounding checks

- LLMProvider interface: `complete(prompt, schema) -> validated_output`. Implementations: primary hosted LLM, mock with canned responses for tests. Validates output against Pydantic schema; retries once on failure.
- Answer schema: `{answer: str, citations: [chunk_id], confidence: float 0-1, needs_escalation: bool, escalation_reason: str|null, intent: str}`.
- Pipeline: retrieve chunks → if top similarity below threshold (configurable, default 0.45) set needs\_escalation and skip generation → else build prompt with chunks and instructions → generate → validate → grounding check (every citation ID must be in the retrieved set; every fee, amount, date, or percentage in the answer must appear in cited chunks, checked by regex extraction) → if check fails, escalate.
- System prompt instructs: answer only from provided context, cite chunk IDs, say when information is missing, never promise scholarships or admission.

**Tests:**

- Unit: grounding check rejects an answer citing a chunk ID not retrieved.
- Unit: grounding check rejects an answer stating "₹50,000" when cited chunk contains "₹25,000."
- Unit: schema validation failure triggers exactly one retry, then escalation.
- Evaluation: run the 40-question evaluation set (Section 17.3). Requirements: at least 90% of unanswerable questions escalated, at least 90% of answerable questions answered with the correct citation, zero fabricated figures.

**Done when:** Evaluation thresholds are met and recorded in `tests/eval/results/`.

## M4.5 Intent classifier

- Classify inbound message into the intent list (FR-08 AC8.1) with a confidence score. Use LLM with schema, plus keyword fast-path for opt\_out (STOP, UNSUBSCRIBE, REMOVE ME) which bypasses the LLM.
- Sentiment flag: negative sentiment or complaint keywords route to human.

**Tests:**

- Unit: opt-out keywords are detected without calling the LLM (assert mock LLM not called).
- Evaluation: 60 labelled messages, intent accuracy at least 85%, and zero misclassified opt-outs.

**Done when:** Evaluation thresholds are met.

## M4.6 Enquiry agent workflow

Triggered by `inbound.handled` event. Steps:

1. Load lead context: timeline (last 10 events), lifecycle, programme, assessments summary, consent.
2. Classify intent (M4.5).
3. Route by intent and policy: opt\_out → consent revocation, complaint → human task, booking\_request → scheduling tool, FAQ-type intents → knowledge agent.
4. Knowledge agent produces answer (M4.4).
5. Communication agent drafts the reply using the answer and the student's context, without introducing facts not in the answer.
6. Policy decides: auto-send, approval queue, or escalation.
7. Log an agent\_action for each step.

Agents call tools only. Tools: `search_knowledge`, `get_lead_context`, `draft_reply`, `queue_for_approval`, `send_message` (goes through M3.3), `create_followup_task`, `update_lifecycle` (only Contacted → Engaged allowed for agents).

**Tests:**

- Integration: scholarship query creates an approval item with citations and does not send.
- Integration: FAQ query above confidence threshold is auto-sent and logged.
- Integration: complaint creates a human task and sends nothing.
- Integration: an agent attempting to set lifecycle to Converted is rejected by the tool layer.

**Done when:** All four policy routes tested.

## M4.7 Approval queue

- Tables: `approval_items` (id, type, lead\_id, payload, draft\_content, citations, status: pending/approved/rejected/edited, decided\_by, decided\_at, decision\_note).
- Endpoints: `GET /api/approvals` (filtered by permission), `POST /api/approvals/{id}/approve`, `.../reject`, `.../edit-and-approve`.
- Approval triggers `messaging.send` with original actor = agent, approver recorded.

**Tests:**

- Integration: approving sends exactly one message.
- Integration: a counsellor cannot approve items on leads not assigned to them.
- Integration: double approval returns 409 and sends no second message.

**Done when:** Approval tests pass.

## M4.8 Knowledge management UI and enquiry interface

- Admin UI: upload documents, view versions, approve, archive, see indexing status.
- Approval queue UI showing draft, citations (click to view chunk), intent, approve/edit/reject.
- Public enquiry chat widget (website): simple chat that calls the enquiry agent with a session token, shows answers with citations, offers a "talk to a counsellor" button that creates a lead.

**Tests:**

- Playwright: upload, approve, and query a document through the public widget. Answer includes citation.
- Playwright: approval queue flow for one draft.

**Done when:** Both flows pass.

---

# Milestone M5: Scheduling and Counsellor Assignment (Week 5)

**Goal:** Counsellors publish availability, students book slots safely, the system assigns counsellors by rule.

## M5.1 Counsellor profiles and specialisations

- Tables: `counsellor_profiles` (id, user\_id, campus\_id, active, max\_open\_leads, can\_be\_assigned), `counsellor_specialisations` (counsellor\_id, programme\_id).
- Endpoints for admin to manage profiles.

**Tests:**

- Integration: inactive counsellor is never returned by assignment candidates.

**Done when:** Profile CRUD and the inactive-exclusion test pass.

## M5.2 Availability slots

- Table: `availability_slots` (id, counsellor\_id, start\_at timestamptz, end\_at timestamptz, mode: online/in\_person/phone, meeting\_link\_template, status: open/booked/blocked).
- Counsellors create slots directly or via recurring rule (weekly pattern for next 30 days, generated by a Celery task).
- Validation: end after start, no overlap between a counsellor's own slots.
- Store all times in UTC, display in IST.

**Tests:**

- Unit: recurring rule generates expected slots for a 2-week pattern.
- Integration: overlapping slot creation is rejected.
- Unit: timezone conversion for IST display across the date boundary.

**Done when:** Availability tests pass.

## M5.3 Booking with concurrency protection

- Table `appointments` (id, lead\_id, counsellor\_id, slot\_id, start\_at, end\_at, mode, status: confirmed/cancelled/rescheduled/completed/no\_show, meeting\_link, created\_at).
- Exclusion constraint: `EXCLUDE USING gist (counsellor_id WITH =, tstzrange(start_at, end_at) WITH &&) WHERE (status = 'confirmed')` (requires btree\_gist).
- Booking service runs in a transaction, locks the slot row with `SELECT ... FOR UPDATE`, checks status is open, creates appointment, sets slot to booked.

**Tests:**

- Integration (critical): 50 concurrent booking requests for the same slot using `asyncio.gather` against real Postgres (testcontainers). Expected: exactly 1 success, 49 conflict responses (409), zero double bookings in the database.
- Integration: booking an already-booked slot returns 409.
- Integration: booking a slot for a lead who already has a confirmed appointment in the same cycle returns 409 unless rescheduling.

**Done when:** The 50-concurrent-request test passes reliably across 10 consecutive runs.

## M5.4 Assignment engine

- Implement `services/assignment.py` with pure function `choose_counsellor(lead, slot, candidates, workloads, history) -> counsellor_id | reason`.
- Rules from FR-09 applied in order. Each rule's exclusion reason is recorded.
- Workload = count of open leads assigned to counsellor (lifecycle not terminal).
- Tie-break: round-robin pointer stored per campus.
- If no counsellor qualifies, return reason and notify Admission Manager.

**Tests:**

- Unit: 12 scenarios covering each rule, including "no specialisation match falls back to general counsellors," "existing assignment is kept when available," "round-robin rotation over three equal counsellors produces expected order."
- Unit: the function is pure (no DB calls) so the test does not need a database.

**Done when:** All 12 scenarios pass.

## M5.5 Booking flow for students

- Public signed link `GET /api/public/booking/{token}` returns available slots for the student's programme and campus in IST. Token expires in 72 hours and is single-purpose.
- `POST /api/public/booking/{token}/select` books the slot (uses M5.3), calls assignment (M5.4), creates meeting link via calendar provider, sends confirmations via `messaging.send` (transactional category).
- Reschedule and cancel via signed links; each creates history rows in `appointment_history`.

**Tests:**

- Integration: expired token returns 410.
- Integration: token for one student cannot book for another.
- Integration: confirmation emails contain correct IST time, mode, and meeting link.
- Integration: reschedule frees the old slot and books the new one atomically.

**Done when:** End-to-end booking test passes with mock calendar.

## M5.6 Calendar provider

- CalendarProvider interface: `create_meeting(start, end, attendees) -> link`, `cancel_meeting(id)`.
- Mock implementation generates `https://meet.example.test/{uuid}`.
- Google Calendar implementation (optional, behind flag).

**Tests:** Contract tests for mock; Google implementation tested only if credentials exist.

**Done when:** Booking flow uses the calendar interface, not a direct provider call.

## M5.7 Missed appointments and outcomes

- Celery beat task every 15 minutes marks appointments whose end time has passed and status is still confirmed as `no_show_pending`, creating a counsellor task to confirm the outcome.
- Counsellor marks outcome: completed, no\_show, cancelled. Completed triggers `counselling.completed` event. No-show triggers `appointment.missed` event.

**Tests:**

- Integration: appointment past end time becomes `no_show_pending` after beat run.
- Integration: outcome update emits the correct event (assert event payload).

**Done when:** Events are emitted and consumed by follow-up rules in M7 (stub consumers in M5).

## M5.8 Frontend: availability, booking, and counsellor schedule

- Counsellor: availability calendar, create slots, recurring pattern, today's appointments, mark outcome.
- Manager: assign or reassign counsellor with reason, view workload.
- Student (public): booking page with slot selection, confirmation page.

**Tests:**

- Playwright: counsellor creates availability; student books a slot from the public link; counsellor sees the appointment; second student cannot book the same slot.

**Done when:** Full booking journey works in the browser.

---

# Milestone M6: Lead Intelligence and Conversation Intelligence (Week 5–6)

**Goal:** Deterministic scoring with AI signal extraction, independent counsellor assessments, recording upload, transcription, and MOM generation with verification.

## M6.1 Scoring configuration

- Tables: `scoring_weights` (id, version, weights JSONB, created\_by, created\_at, active flag), `scoring_thresholds` (version, high\_min=75, medium\_min=45).
- Only one active version at a time. Changing weights creates a new version.
- Endpoint `PUT /api/scoring/weights` (requires `scoring.configure`). Validates weights sum to 100.

**Tests:**

- Unit: weights not summing to 100 are rejected.
- Integration: a new version becomes active and the previous version remains queryable.

**Done when:** Versioning tests pass.

## M6.2 Deterministic scoring engine

- Implement `services/scoring.py` with a pure function `compute_score(signals, weights, thresholds) -> ScoreResult` where ScoreResult includes total, category, per-factor contributions, missing flags, and confidence.
- Sub-scores normalised to \[0, 1\]. Missing signal uses neutral value (default 0.5) and sets missing=true.
- Engagement sub-score is computed deterministically from data: inbound replies (last 14 days), booking, attended session, days since last inbound (recency decay). Document the formula in the code.
- Eligibility sub-score is computed deterministically: student's academic score vs programme minimum. Full score if at or above minimum, linear reduction to 0 at 10 points below, 0 beneath that.
- Category map: 75–100 high, 45–74 medium, 0–44 low.

**Tests:**

- Unit: 25 cases covering boundary values (74.9, 75, 44.9, 45), missing signals, and the engagement and eligibility formulas.
- Unit: determinism test — same input, 100 runs, identical output.
- Unit: weights version used is recorded in output.

**Done when:** All scoring tests pass with 100% branch coverage on the module.

## M6.3 Signal extraction with the LLM

- Agent `lead_intel.extract_signals(lead_context) -> SignalSet` using LLM with schema. Each signal: `{value: float 0-1 or null, evidence: [message_ids], evidence_quote: str|null}`.
- LLM extracts only: course\_interest, admission\_intent, financial\_fit (if no deterministic budget data), admission\_timeline.
- Verification: any evidence\_quote must appear in the referenced message text (fuzzy match above 90%). Signals failing verification are set to null with reason `unverified_evidence`.
- Results stored in `lead_signals` with extraction run ID.

**Tests:**

- Unit: signal verification rejects an evidence quote not present in messages.
- Evaluation: 30 labelled conversation excerpts. Signal direction (high vs low intent) matches label in at least 85% of cases. Zero unverified quotes accepted.

**Done when:** Evaluation thresholds are met.

## M6.4 AI assessment and counsellor assessment

- `lead_assessments` table: id, lead\_id, assessor\_type (ai/counsellor), assessor\_id, score, category, factors JSONB, explanation, weights\_version, created\_at, superseded\_by (nullable).
- AI assessment flow: extract signals → compute score → save as new assessment. Previous AI assessment is not modified, only marked as superseded by the new one for display.
- Counsellor assessment: manual entry with score and category and mandatory note. Stored as separate row.
- Disagreement check: if categories differ or score gap ≥ 20, create `assessment_disagreement` flag on the lead.
- Override: counsellor can set a category override on the AI assessment with reason, recorded as a new counsellor assessment referencing the AI assessment ID.

**Tests:**

- Integration: AI and counsellor assessments coexist; updating one does not change the other.
- Integration: score gap 20 creates a disagreement flag; gap 19 does not.
- Integration: override requires a reason (empty reason returns 422).

**Done when:** Assessment history tests pass.

## M6.5 Recording upload and storage

- `POST /api/recordings/upload` (multipart, counsellor for own lead or manager). Validate file type by magic bytes, size up to 100 MB, duration up to 120 minutes (checked after probing with ffprobe or mutagen).
- Store in encrypted object storage path `recordings/{lead_id}/{uuid}.{ext}`. Store metadata in `recordings` (id, lead\_id, appointment\_id, storage\_key, duration, status, uploaded\_by, checksum).
- Virus scanning hook (interface, mock implementation in v1).

**Tests:**

- Integration: a file with a .mp3 extension containing text is rejected.
- Integration: a 101 MB file is rejected with 413.
- Integration: a counsellor cannot upload recordings for leads not assigned to them.

**Done when:** Upload tests pass.

## M6.6 Transcription pipeline

- SpeechProvider interface: `transcribe(storage_key) -> Transcript{segments: [{start, end, speaker, text}], language, confidence}`.
- Implementation: faster-whisper (local) or hosted Whisper. Language detection supports Hindi and English. Mock returns a fixture transcript.
- Celery task `transcribe_recording` updates status: queued → transcribing → transcribed / failed. Stores transcript in `transcripts` table.
- Confidence below threshold sets `needs_review` flag.

**Tests:**

- Integration with mock: transcription task moves status through the expected states.
- Integration: failed transcription records error and allows retry from the UI.
- Unit: transcript segment timestamps are monotonically increasing.

**Done when:** Pipeline runs end to end with the mock speech provider.

## M6.7 MOM generation with verification

- `conversation.generate_mom(transcript, lead_context) -> MOMDraft` using LLM with the schema from FR-11.
- Each key quote must include a timestamp. Verification step finds the quote in the transcript (fuzzy match ≥ 90%) and attaches the timestamp. Unverified quotes are removed and flagged.
- Output is saved as `meeting_notes` version 1 with status draft.
- Schema failure: retry once, then status `manual_required`.

**Tests:**

- Unit: quote verifier accepts exact and near-exact matches, rejects fabricated quotes.
- Unit: schema validation enforces required fields.
- Evaluation: 10 fixture transcripts with known facts. Check that the MOM includes each known fact (completeness ≥ 90%) and that no MOM field contradicts the transcript (manual rubric, recorded in results).

**Done when:** Evaluation results recorded and thresholds met.

## M6.8 MOM review and approval

- Counsellor edits fields; each save creates a new version. Approval marks version approved (immutable).
- Approval triggers re-scoring (M6.4) with signals from the approved MOM as additional evidence.
- Endpoints: `GET /api/leads/{id}/mom`, `PATCH /api/mom/{id}` (creates new version), `POST /api/mom/{id}/approve`.

**Tests:**

- Integration: approved version cannot be patched (409).
- Integration: approval triggers a new AI assessment linked to the MOM version.
- Integration: counsellor not assigned to the lead cannot approve (403/404).

**Done when:** Review workflow tests pass.

## M6.9 Frontend: recordings, MOM review, assessments

- Recording upload with progress bar and status display.
- MOM review screen: side-by-side transcript (with timestamps) and editable MOM fields, quote verification badges.
- Assessment panel on lead page: AI score with factor breakdown and evidence links, counsellor score entry, disagreement banner, override form with reason.

**Tests:**

- Vitest: score breakdown component renders all factors and missing-signal warnings.
- Playwright: upload audio fixture, see transcript (mock), edit and approve MOM, see new AI assessment.

**Done when:** Flow works end to end in the browser.

---

# Milestone M7: Follow-up Orchestration, SLAs, and Audit (Week 7)

**Goal:** Event-driven nurturing with rules, SLA escalation, retries, approval gates, and complete audit trail.

## M7.1 Event bus and event store

- Table `domain_events` (id, event\_type, aggregate\_type, aggregate\_id, payload JSONB, occurred\_at, processed\_at, attempts).
- Publishing writes the event in the same transaction as the state change (transactional outbox pattern).
- Celery beat job reads unprocessed events and dispatches to handlers.

**Tests:**

- Integration: if the transaction rolls back, no event is published.
- Integration: a failed handler is retried and marked processed only on success.

**Done when:** Outbox tests pass.

## M7.2 Follow-up rule engine

- Table `followup_rules` (id, name, trigger\_event, conditions JSONB, action\_type, action\_config JSONB, delay\_minutes, max\_attempts, stop\_conditions JSONB, enabled, version).
- Evaluator: on each matching event, checks conditions against current lead state, schedules a `followup_task` (for human) or `scheduled_message` (for automated action) with an idempotency key `rule_id:lead_id:window`.
- Rules evaluated in M7 include all rows from the PRD FR-12 table.
- Admins can enable, disable, or edit delays and limits via API. Changes are versioned.

**Tests:**

- Unit: condition evaluator for 10 condition combinations.
- Integration: each PRD trigger row produces the expected action in a scenario test.
- Integration: duplicate event does not create duplicate scheduled actions (idempotency key).
- Integration: terminal lifecycle state cancels pending scheduled messages.

**Done when:** One scenario test per FR-12 row passes.

## M7.3 Scheduled actions and quiet hours

- Celery beat task every 5 minutes executes due `scheduled_messages`.
- Quiet hours (21:00–09:00 IST): non-urgent actions are rescheduled to 09:00 IST. Urgent categories (appointment confirmations, rescheduling links for same-day slots) are exempt.
- Each execution re-checks consent, frequency cap, and terminal state before sending (state may have changed since scheduling).

**Tests:**

- Unit: quiet-hour rescheduling computes the correct next window across IST midnight.
- Integration: a scheduled message whose lead became "Converted" before execution is cancelled, not sent.
- Integration: a scheduled message exceeding the frequency cap is cancelled with reason.

**Done when:** Scheduling and guard tests pass.

## M7.4 SLA and escalation

- Table `sla_policies` (id, name, applies\_to (e.g. high-potential lead), target\_minutes, escalation\_to\_role).
- Default policy: high-potential lead must receive counsellor contact within 24 hours of assignment. Counsellor contact means a logged call, appointment, or outbound message by the counsellor.
- Beat task checks SLA breaches and creates escalation notifications to the Admission Manager.

**Tests:**

- Integration: high-potential lead with no contact after 24 simulated hours creates one escalation notification (not two on repeat runs).
- Integration: contact logged within SLA cancels the breach.

**Done when:** SLA tests pass with a controllable clock fixture.

## M7.5 Retry and failed-action queue

- Failed scheduled messages retry with exponential backoff (1, 2, 4, 8, 16 minutes) up to max\_attempts.
- Permanent failures move to `failed_actions` with reason. Admin UI lists them with a retry button.

**Tests:**

- Integration: transient failure retries on schedule; permanent failure lands in failed queue after max attempts.
- Integration: admin retry from the UI re-queues the action once.

**Done when:** Retry tests pass.

## M7.6 Next Best Action (rule-based first)

- Service `next_best_action(lead) -> Recommendation{action, reason, priority}` using the table from the PRD (Section 6, FR-12, and the NBA examples).
- Shown on counsellor dashboard for each lead.
- The LLM may rephrase the reason text but never selects the action.

**Tests:**

- Unit: 10 lead states map to expected actions.
- Unit: LLM cannot change the action (test by mocking LLM to return a different action and asserting the rule-based action is kept).

**Done when:** NBA tests pass.

## M7.7 Agent orchestrator

- `orchestrator.handle_event(event)` loads context, selects the agent (enquiry, lead intelligence, conversation, follow-up), and runs it with tool permissions limited to that agent.
- Each run creates an `agent_run` record with steps, tool calls, model version, and outcome.
- Agents cannot call tools outside their allow-list. Enforced in the tool dispatcher.
- Maximum of 5 tool calls per agent run to prevent loops.

**Tests:**

- Unit: tool dispatcher rejects a tool not in the agent's allow-list.
- Unit: the sixth tool call in a run is refused and the run is marked `aborted_loop_guard`.
- Integration: a reply event triggers enquiry agent and produces an `agent_run` record.

**Done when:** Allow-list and loop-guard tests pass.

## M7.8 Audit log

- Table `audit_logs` (id, occurred\_at, actor\_type, actor\_id, action, entity\_type, entity\_id, input\_ref, output\_ref, tool\_name, result, approval\_id, failure\_reason, ip\_address). Append-only: the application database role has INSERT and SELECT only on this table; migration includes the GRANT statements.
- Middleware records every write API call. Services record domain-significant actions explicitly.
- Agent actions include model name, model version, prompt template ID, hash of input context.
- Audit viewer endpoint `GET /api/audit` with filters (requires `audit.view`).

**Tests:**

- Integration: attempting `UPDATE audit_logs` from the application role fails with permission denied.
- Integration: a lead status change, approval, and agent send each produce an audit entry with the correct actor type.
- Integration: audit entries contain no raw PII (masked per M0.4).

**Done when:** All three audit tests pass.

## M7.9 Frontend: follow-up configuration and approvals

- Rule editor for admins (enable or disable, edit delay and cap). Show rule version history.
- Tasks inbox for counsellors (follow-up tasks with due dates, overdue highlighting).
- Failed actions queue for admins.
- Audit log viewer with filters.

**Tests:**

- Playwright: edit a rule delay, verify a new scenario uses the new delay.
- Playwright: counsellor completes a task and it disappears from the overdue list.

**Done when:** Flows pass in the browser.

---

# Milestone M8: Dashboards, Hardening, Deployment, and Demo (Week 8)

**Goal:** Dashboards complete, security and load tested, deployed, demo ready.

## M8.1 Analytics queries and API

- Endpoints under `/api/analytics`: funnel counts by lifecycle stage, leads by source, leads by programme, score distribution, campaign performance, counsellor workload, SLA breaches, conversion rates by source.
- Queries use indexed columns and materialised views refreshed every 10 minutes for heavy aggregations.
- Date range and programme filters on all endpoints.

**Tests:**

- Integration: each endpoint returns correct totals on a seeded dataset (assert exact numbers from a fixture with known counts).
- Performance: all analytics endpoints P95 under 1 second at 10,000 leads.

**Done when:** Fixture numbers match and performance targets are met.

## M8.2 Manager dashboard UI

- Cards: total leads, new this week, high/medium/low distribution, SLA breaches, overdue follow-ups.
- Charts: funnel, leads by source, leads by programme, campaign performance, counsellor workload.
- Disagreement queue panel.

**Tests:**

- Playwright: dashboard loads under 3 seconds with seeded 10,000-lead dataset (measure with Playwright timing).
- Vitest: chart components render with empty data without errors.

**Done when:** Performance and empty-state tests pass.

## M8.3 Counsellor dashboard UI

- Priority-sorted leads list with category badges and NBA reason.
- Today's appointments, pending follow-ups, recent conversations, MOM drafts awaiting review, personal metrics (contacts made, bookings, completions).

**Tests:**

- Playwright: counsellor sees only own leads and tasks.

**Done when:** Test passes.

## M8.4 Security testing

Automated checks:

- RBAC matrix test: for every endpoint, call with each role and compare to expected matrix (generated from a YAML file in `tests/security/rbac_matrix.yaml`).
- Cross-tenant and cross-counsellor access tests for leads, recordings, MOMs, appointments, timeline.
- File upload fuzzing: malformed PDFs, oversized archives, polyglot files.
- Webhook signature tests for all endpoints.
- SQL injection tests on segment filters and search parameters.
- Rate limit tests on login and public endpoints.
- Secret scanning in CI (gitleaks).
- Dependency scanning (pip-audit, npm audit) in CI.

**Tests:** All automated security tests pass. Any failure blocks release.

**Done when:** Security suite is green in CI.

## M8.5 Load and concurrency testing

- k6 scripts: 200 concurrent users browsing lead lists and dashboards; 500 inbound webhook events per minute; 50 concurrent booking attempts per slot across 20 slots.
- Chaos checks: restart worker during campaign send, verify no duplicates; restart database during booking, verify no partial appointment.

**Tests:** Targets from NFR-02, NFR-04, NFR-06 are met. Results saved to `docs/test-results/`.

**Done when:** Load report documents targets met or lists exceptions with mitigations.

## M8.6 AI evaluation and regression harness

- Consolidate evaluation datasets from M4.4, M4.5, M6.3, M6.7 into `tests/eval/`.
- Runner script `make eval` produces a report with metrics, failures, and comparison to the previous run.
- Add evaluation to CI as a non-blocking job that posts results to the pull request, and as a blocking job before release.

**Tests:** Running `make eval` on the current build produces a report and meets thresholds.

**Done when:** Report is generated and thresholds met.

## M8.7 Deployment

- Backend and workers: container deployment (Render, Railway, or AWS ECS). Managed Postgres with pgvector enabled. Managed Redis. S3 bucket with encryption and lifecycle rules.
- Frontend: Vercel or the same container platform.
- Production configuration: real providers enabled via flags, secrets in the platform's secret manager, HTTPS enforced, CORS restricted to frontend origin.
- Backups: daily database snapshot with 14-day retention. Tested restore once.

**Tests:**

- Smoke test script runs against staging: login, import sample file, send test email to a sandbox address, book slot, check health endpoints.
- Restore drill: restore latest backup into a scratch database and run the migration check.

**Done when:** Staging smoke test passes and restore drill is documented.

## M8.8 Demo dataset and scenario script

- Seed script `make seed-demo` creates: 3 roles and users, 10,000 synthetic leads (for performance demo) and a 50-lead realistic set (for narrative), 3 programmes, 2 campuses, 6 counsellors with availability, knowledge documents (brochure, fee structure, scholarship policy, eligibility, FAQ), 2 email templates, 1 campaign, 1 recording fixture with transcript.
- Scenario script (Section 22 of the earlier document, Rahul Sharma journey) saved as `docs/demo-script.md` with exact steps and expected screens.

**Tests:** Running `make seed-demo` on a fresh database and then the demo script end to end succeeds without manual intervention.

**Done when:** A person unfamiliar with the project can run the demo from the script.

## M8.9 Documentation

- `docs/ARCHITECTURE.md` with component diagram and agent flow.
- `docs/API.md` generated from OpenAPI plus workflow notes.
- `docs/RUNBOOK.md` covering deployment, restore, failed-action handling, provider credential rotation.
- `docs/EVALUATION.md` with methodology and results.
- `docs/SECURITY.md` with controls and known limitations.
- `README.md` with local setup in under 15 minutes.

**Tests:** A fresh machine follows README and reaches a running app, verified by a colleague or a clean VM run.

**Done when:** Documentation review checklist complete.

---

# Post-MVP milestones

## Phase 2 (WhatsApp, advanced automation)

- **P2.1** WhatsApp Cloud API or BSP adapter behind the existing WhatsAppProvider interface.
- **P2.2** Template submission and approval status tracking.
- **P2.3** Two-way conversation with 24-hour session window handling (outside the window, only approved templates).
- **P2.4** Parent as secondary contact with separate consent.
- **P2.5** Next-best-action extended with learned preferences (still rule-based for decisions).
- **P2.6** A/B testing for templates with statistical reporting.

## Phase 3 (voice and prediction)

- **P3.1** Retell AI adapter: outbound call trigger, call events, recording and transcript ingestion into M6 pipeline.
- **P3.2** Consent and calling-hour enforcement for voice.
- **P3.3** Historical outcome import and calibration of scoring weights.
- **P3.4** Conversion probability model, labelled as such only after validation.
- **P3.5** ERP or external CRM sync (Salesforce sandbox adapter first).

---

# Suggested team allocation (three developers)


| Developer               | Milestones                                               | Primary tasks                                                                     |
| ----------------------- | -------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Dev 1 (Frontend)        | M1.5, M2.10, M3.9, M4.8, M5.8, M6.9, M7.9, M8.2, M8.3    | All UI, Playwright suites, public widget and booking page                         |
| Dev 2 (Backend and CRM) | M0, M1, M2, M3, M5.1–5.3, M5.5–5.7, M7.1, M7.3–7.5, M7.8 | Auth, data model, ingestion, messaging, scheduling core, audit, workers           |
| Dev 3 (AI)              | M4, M6, M7.2, M7.6, M7.7, M8.6                           | RAG, enquiry agent, scoring, transcription, MOM, orchestrator, evaluation harness |


**Shared:** M5.4 (assignment rules, pair-programmed), M8.4 and M8.5 (security and load), M8.7 and M8.8 (deployment and demo).

**Before parallel work starts:** Agree on the API contract (OpenAPI spec for M1–M3), the event names and payloads (M7.1), and the tool interface signatures (M4.6, M7.7). Freeze these in `docs/` before the second week.