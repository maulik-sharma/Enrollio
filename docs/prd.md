# 1. Overview

The **Intelligent Admission Enquiry and Lead Nurturing Agent** is an admission CRM for colleges and universities. It manages each prospective student from first enquiry through to admission, using AI for answering questions, qualifying leads, drafting communication, analysing counselling conversations, and deciding the next follow-up. Counsellors and admission managers stay in control of decisions that carry institutional risk.

**Product positioning:** Autonomous enquiry-to-admission lifecycle management with human-in-the-loop counselling.

# 2. Problem

During admission season, colleges receive large volumes of enquiries across websites, email, WhatsApp, education fairs, and coaching partners. Typical problems:

- Slow first responses, so prospective students go to competitors.
- Inconsistent or outdated answers about fees, scholarships, and eligibility.
- Follow-ups missed because nobody owns them.
- Counselling notes stored in personal notebooks or not at all.
- No reliable way to tell which leads deserve counsellor time first.
- Spreadsheets and disconnected tools that make the funnel invisible.

# 3. Goals and Non-Goals

## Goals


| ID  | Goal                                                    | Measure                                            |
| --- | ------------------------------------------------------- | -------------------------------------------------- |
| G1  | Respond to enquiries quickly and consistently           | Median first-response time                         |
| G2  | Answer admission questions only from approved documents | Groundedness rate in evaluation set                |
| G3  | Prioritise counsellor effort                            | Share of high-potential leads contacted within SLA |
| G4  | Reduce missed follow-ups                                | Follow-up compliance rate                          |
| G5  | Make counselling outcomes structured and searchable     | % of counselling sessions with approved MOM        |
| G6  | Give admissions leadership a clear funnel view          | Dashboard coverage of funnel stages                |


## Non-Goals (for v1)

- Replacing the institution's admission portal or application form system.
- Fully autonomous admission decisions or fee commitments.
- Predictive conversion modelling (requires historical outcome data, see Section 11).
- Voice calling via Retell AI (Phase 3).
- Multi-tenant SaaS billing. v1 serves one institution, though the data model should allow multiple campuses.

# 4. Users and Roles


| Role                 | Responsibilities                                           | Key permissions                                                                                                                           |
| -------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| System Admin         | Platform setup, users, roles, integrations, knowledge base | `users.manage`, `roles.manage`, `knowledge.manage`, `integrations.manage`, `audit.view`                                                   |
| Admission Manager    | Oversees funnel, campaigns, assignment, policy             | `leads.view_all`, `leads.assign`, `campaigns.manage`, `scoring.configure`, `followup_policy.manage`, `dashboard.manager`                  |
| Admission Counsellor | Works assigned leads, runs sessions, reviews MOMs          | `leads.view_assigned`, `appointments.manage_own`, `recordings.upload_own`, `mom.review_own`, `assessment.create_own`, `messages.send_own` |
| Prospective Student  | Enquires, books slots, opts out                            | Accessed through public channels and signed booking links only. No login in v1.                                                           |


**RBAC rule:** Counsellors can see only their assigned leads unless an Admission Manager reassigns or shares them. Every role check is enforced in the backend, not in the UI.

# 5. Core User Journeys

**J1. Import and launch.** An Admission Manager imports a CSV from a coaching partner, maps columns, reviews duplicate and error reports, and creates a campaign for "B.Tech CSE, score ≥ 80%."

**J2. Enquiry and scholarship question.** A student replies to an email asking about scholarships. The system identifies the intent, retrieves the scholarship policy, drafts a reply with citations, and sends it automatically if it is a general FAQ or queues it for counsellor approval if it involves money.

**J3. Counselling booking.** The student is offered three slots, selects one, and receives a confirmation with a meeting link or the counsellor's phone number. The counsellor receives a notification.

**J4. Post-counselling.** The counsellor uploads a recording. The system produces a transcript and a draft MOM. The counsellor edits and approves it. The AI and counsellor each have a lead assessment, and the system flags any large disagreement.

**J5. Adaptive nurturing.** A high-potential student who has not applied within 48 hours receives a reminder. The counsellor gets a priority task. If the SLA is missed, the Admission Manager is notified.

**J6. Opt-out.** A student replies "STOP" or clicks unsubscribe. All promotional communication stops immediately and the opt-out is logged.

# 6. Scope

## MVP (Phase 1)

- Authentication and RBAC
- Lead import (CSV/XLSX), manual entry, web enquiry form, and a generic API ingestion endpoint
- Validation, duplicate detection, import history, error reports
- Student and lead model with lifecycle tracking
- Consent and communication preferences
- Knowledge base with RAG and citations
- Email campaigns, inbound email handling, threading, and AI reply suggestions with approval
- Counsellor availability, assignment engine, booking, confirmations, reschedule and cancel
- AI and counsellor lead assessments with the deterministic scoring engine
- Basic follow-up rules with escalation
- Unified communication timeline
- Counsellor and manager dashboards
- Audit log and approval queue

## Phase 2

- WhatsApp Business integration (templates, two-way conversation)
- Audio upload, Whisper transcription, MOM generation and review
- Advanced follow-up automation and next-best-action engine
- Campaign analytics and A/B template testing
- Parent as secondary contact

## Phase 3

- Retell AI outbound and inbound voice calls, with automatic recording ingestion
- Conversion prediction trained on historical admissions data
- Multi-campus administration
- ERP and external CRM integration (Salesforce, etc.)

# 7. Functional Requirements

Each requirement lists its priority (**P0** must have, **P1** should have, **P2** nice to have), its description, and its acceptance criteria.

## FR-01: Lead Ingestion (P0)

**Description:** Leads enter the system through four routes: CSV/XLSX import, a generic API endpoint, manual creation by staff, and a public enquiry form.

**Acceptance criteria:**

- **AC1.1:** CSV and XLSX files up to 10,000 rows import successfully.
- **AC1.2:** The user maps source columns to system fields. The mapping can be saved and reused for the same source.
- **AC1.3:** Each row is validated. Invalid rows are rejected with a row number and reason, and the rest of the file still imports.
- **AC1.4:** The import produces a downloadable error report.
- **AC1.5:** Every lead stores its source, import job ID, and original raw row.
- **AC1.6:** Import history is viewable with counts for total, created, merged, and rejected rows.

## FR-02: Duplicate Detection (P0)

**Description:** The system identifies when an incoming record refers to a student already in the system.

**Acceptance criteria:**

- **AC2.1:** Email is normalised to lowercase and trimmed. Phone is normalised to E.164 format.
- **AC2.2:** An exact match on normalised email or phone links the record to the existing Student.
- **AC2.3:** A matching student with a different course or admission cycle creates a new Lead linked to the same Student.
- **AC2.4:** When a match is found, empty fields on the existing record can be filled from the incoming record. Existing non-empty values are never overwritten automatically.
- **AC2.5:** Possible duplicates that match only on name are flagged for manual review, not merged.

## FR-03: Student, Lead, and Lifecycle Model (P0)

**Description:** Students hold identity and contact details. Leads hold enquiry-specific data, lifecycle status, and ownership.

**Lifecycle states:**

`New Enquiry → Contacted → Engaged → Qualified → Counselling Scheduled → Counselling Completed → Application Started → Application Submitted → Admission Offered → Converted`

**Terminal states:** `Lost`, `Disqualified`, `Unresponsive`, `Opted Out`.

**Acceptance criteria:**

- **AC3.1:** Only allowed transitions can occur. Invalid transitions are rejected and logged.
- **AC3.2:** Every transition writes a timeline event with actor, timestamp, and reason.
- **AC3.3:** Lifecycle status and lead score are stored in separate fields and never derived from each other.
- **AC3.4:** "Converted" can be set only by an approved system event (such as an ERP update or an authorised manager action), never by an AI agent.

## FR-04: Consent and Communication Preferences (P0)

**Description:** The system records consent and preferences for each channel and message category.

**Categories:** **Transactional** (confirmations, reminders about booked slots) and **Promotional** (campaigns, nudges).

**Acceptance criteria:**

- **AC4.1:** Every outbound message checks the recipient's consent for its channel and category before sending.
- **AC4.2:** Every promotional email includes a working unsubscribe link.
- **AC4.3:** Opt-out via unsubscribe, WhatsApp "STOP," or staff entry takes effect within one minute and stops all promotional sends.
- **AC4.4:** Consent records store source, timestamp, and method (for example, "web form checkbox" or "imported with partner consent confirmation").

## FR-05: Campaigns and Segmentation (P0)

**Description:** Staff create campaigns targeting segments and send personalised messages.

**Acceptance criteria:**

- **AC5.1:** Segments can be defined with filters on course, score range, source, lifecycle status, campus, and last-contact date.
- **AC5.2:** Templates support placeholders such as `{{first_name}}`, `{{course}}`, `{{deadline}}`. Missing placeholder values block sending for that recipient and are reported.
- **AC5.3:** A preview shows rendered output for a sample recipient before launch.
- **AC5.4:** Campaigns can be scheduled. Sends run asynchronously and respect frequency caps (default: maximum two promotional messages per student per seven days).
- **AC5.5:** Each recipient has a status: Queued, Sent, Delivered (if the provider supports it), Failed, Replied, Opted Out.
- **AC5.6:** Opens are recorded if available but are not used in lead scoring.

## FR-06: Email Communication (P0)

**Description:** Outbound campaign email and inbound replies handled as threaded conversations.

**Acceptance criteria:**

- **AC6.1:** Outbound email is sent through a transactional email provider (Amazon SES or SendGrid recommended for volume).
- **AC6.2:** Replies are linked to the correct lead using a reply-token address or a message-ID thread reference.
- **AC6.3:** Provider webhooks (delivered, bounced, complained) update message status. Bounces and complaints suppress future sends to that address.
- **AC6.4:** Each inbound message appears in the lead's timeline within 30 seconds under normal load.

## FR-07: Knowledge-Grounded Admission Assistant (P0)

**Description:** The assistant answers student questions using approved institutional documents and cites them. It escalates when the knowledge base does not support an answer.

**Knowledge sources:** Brochures, fee structures, scholarship policies, eligibility criteria, hostel and transport information, placement reports, admission deadlines, FAQs.

**Acceptance criteria:**

- **AC7.1:** Administrators can upload PDF, DOCX, and TXT documents, and mark them with an effective date, expiry date, and status (draft, approved, archived).
- **AC7.2:** Only approved, unexpired documents are used for answers.
- **AC7.3:** Each generated answer includes citations to document name, version, and section.
- **AC7.4:** When retrieval confidence is below threshold, or the answer would require information not in the knowledge base, the response is escalated to a counsellor and the student receives a holding message. The system does not guess.
- **AC7.5:** The system never states a fee amount, scholarship amount, eligibility outcome, or admission guarantee unless the figure appears in a cited approved document.
- **AC7.6:** On a 40-question evaluation set (defined in Section 17), at least 90% of unanswerable questions are escalated, and at least 90% of answerable questions are answered with the correct citation.

## FR-08: Inbound Enquiry Handling and Reply Approval (P0)

**Description:** Inbound messages are classified, answered by the knowledge agent, and either sent automatically or queued for approval, depending on category and policy.

**Auto-send policy (configurable):**

- General FAQ with confidence above threshold: auto-send allowed.
- Scholarship, fee, eligibility determination, admission offer, deadline exceptions: always requires approval.
- Complaints, legal or refund questions, and messages with negative sentiment: escalate to a human, no draft sent.

**Acceptance criteria:**

- **AC8.1:** Each inbound message receives an intent label from a defined list (for example: `course_info`, `fee_query`, `scholarship_query`, `eligibility_query`, `booking_request`, `opt_out`, `complaint`, `other`).
- **AC8.2:** Drafts awaiting approval appear in an approval queue with the source citations and the classified intent.
- **AC8.3:** An approver can approve, edit then approve, or reject. Every decision is logged.
- **AC8.4:** Auto-sent messages are logged with the same citation data.

## FR-09: Counsellor Scheduling and Assignment (P0)

**Description:** Counsellors define availability. Students select slots. The system assigns a counsellor and creates the appointment.

**Assignment rules (evaluated in order):**

1. Counsellor is active, has the `counselling.conduct` permission, and is available for the slot.
2. Counsellor specialisation matches the lead's course (if specialisations are configured).
3. Counsellor campus matches the lead's preferred campus (if configured).
4. If the lead already has an assigned counsellor, keep that counsellor when they are available.
5. Otherwise choose the counsellor with the fewest open leads. Ties are broken by round-robin.

**Acceptance criteria:**

- **AC9.1:** Students see only available slots, presented in their local time zone (IST by default).
- **AC9.2:** Two appointments cannot overlap for the same counsellor. This holds under concurrent requests.
- **AC9.3:** Confirmation is sent to the student and the counsellor. Each includes date, time, mode, and meeting link or phone number.
- **AC9.4:** A student can reschedule or cancel through a signed link. Each change creates a history record.
- **AC9.5:** An appointment that passes its end time without an outcome is marked No-show or Completed by the counsellor. Missed appointments trigger the follow-up workflow.
- **AC9.6:** Admission Managers can reassign a lead manually, and the reason is recorded.

## FR-10: Lead Assessment and Scoring (P0)

**Description:** The system produces two independent assessments per lead: AI and counsellor. The AI assessment is generated from extracted signals and a deterministic scoring engine.

**Scoring parameters (initial, configurable):**


| Parameter                   | Weight | Source of signal                                                      |
| --------------------------- | ------ | --------------------------------------------------------------------- |
| Course interest             | 20     | LLM extraction from conversations, with evidence quote                |
| Admission intent            | 25     | LLM extraction, with evidence quote                                   |
| Engagement level            | 15     | Deterministic: replies, bookings, attended sessions, recency          |
| Eligibility                 | 15     | Deterministic: student's score compared against course minimum        |
| Financial fit / scholarship | 15     | Deterministic where budget band is captured; otherwise LLM extraction |
| Admission timeline          | 10     | LLM extraction or captured date field                                 |


Sub-scores are normalised to 0–1. The final score is the sum of weight × sub-score, which gives a value from 0 to 100.

**Categories:** 75–100 High, 45–74 Medium, 0–44 Low.

**Missing data:** When a signal cannot be determined, it defaults to a neutral value of 0.5 (configurable) and the assessment is flagged "low confidence: missing signal X."

**Acceptance criteria:**

- **AC10.1:** Every assessment stores total score, category, each factor's sub-score, evidence references, missing-signal flags, weights version, and timestamp.
- **AC10.2:** Given the same signals and the same weights version, the scoring engine returns the same score every time.
- **AC10.3:** Previous assessments are retained and viewable.
- **AC10.4:** Counsellors can create their own assessment (score and category) with a mandatory note.
- **AC10.5:** When the AI and counsellor categories differ, or the score gap is 20 or more points, the lead is flagged "assessment disagreement" for Admission Manager review.
- **AC10.6:** Counsellors can override an AI category with a required reason. The override is recorded and the AI assessment is not overwritten.
- **AC10.7:** Scoring weights can be changed only by users with `scoring.configure`. Each change creates a new weights version.
- **AC10.8:** The UI displays the score as "lead potential score," not "conversion probability."

## FR-11: Conversation Intelligence and MOM (P1)

**Description:** Counsellors upload recordings. The system transcribes them and produces a structured Meeting Outcome Note (MOM).

**MOM fields:** Student interest, discussion summary, student requirements, financial concerns, admission intent, objections, parent involvement, next action, follow-up date, key quotes (with transcript timestamps).

**Acceptance criteria:**

- **AC11.1:** Accepted formats are MP3, WAV, M4A, and MP4 audio, up to 100 MB. The file type is verified from content, not extension.
- **AC11.2:** Transcription returns timestamped text and speaker labels where the provider supports them.
- **AC11.3:** The MOM is produced in the defined JSON schema. Output that fails schema validation is retried once, then flagged for manual entry.
- **AC11.4:** Every key quote in the MOM must appear in the transcript (fuzzy match above 90% similarity). Quotes that fail this check are marked unverified.
- **AC11.5:** Counsellors can edit and approve the MOM. Approved MOM versions are immutable. Edits create a new version.
- **AC11.6:** After approval, the AI lead assessment can be re-run using the new evidence. The counsellor reviews the result.

## FR-12: Follow-up and Nurturing Workflows (P1)

**Description:** A rules engine determines the next action for each lead based on events and current state.

**Example rules:**


| Trigger                    | Conditions                           | Action                                         | Delay                              |
| -------------------------- | ------------------------------------ | ---------------------------------------------- | ---------------------------------- |
| Initial email, no reply    | Status Contacted, no reply           | Send reminder (max 2)                          | 3 days, then 5 days                |
| Asked about scholarship    | Intent = scholarship\_query          | Share verified scholarship info, offer booking | Immediate                          |
| Interested, not booked     | Engaged, no appointment              | Offer available slots                          | 24 hours                           |
| Counselling completed      | MOM approved                         | Send next-step summary                         | 2 hours after approval             |
| High potential, no contact | Category High, no counsellor contact | Notify counsellor                              | Immediate; escalate after 24 hours |
| Appointment missed         | Status No-show                       | Send rescheduling link                         | Immediate                          |
| Application incomplete     | Application Started, not submitted   | Send completion reminder                       | 48 hours                           |
| Opt-out                    | Unsubscribe or STOP                  | Stop promotional sends                         | Immediate                          |
| Converted or Lost          | Terminal status                      | Stop all nurturing                             | Immediate                          |


**Controls:**

- **Quiet hours** (default 21:00–09:00 IST): non-urgent messages are queued until the next allowed window.
- **Frequency cap:** two promotional messages per seven days per student.
- Each rule has a maximum attempt count and a stop condition.

**Acceptance criteria:**

- **AC12.1:** Rules are configurable by Admission Managers without code changes.
- **AC12.2:** A follow-up task is created for every action that needs a human.
- **AC12.3:** No duplicate message is sent for the same rule instance (idempotency key per rule, lead, and window).
- **AC12.4:** Failed sends are retried with exponential backoff up to a configured limit, then moved to a failed-actions queue visible to admins.
- **AC12.5:** SLA breaches generate escalation notifications to the Admission Manager.

## FR-13: Unified Communication Timeline (P1)

**Description:** Every student has a single timeline containing all interactions and system events.

**Timeline includes:** Emails (in and out), WhatsApp messages, AI-drafted and approved replies, counsellor messages, calls and recordings, appointments, assessments, MOM versions, follow-up tasks, lifecycle transitions, consent changes.

**Acceptance criteria:**

- **AC13.1:** Timeline entries are ordered by time and filterable by type.
- **AC13.2:** AI-generated entries are labelled as such and link to the agent action record.
- **AC13.3:** The timeline is available to any user permitted to see the lead.

## FR-14: Dashboards and Reporting (P1)

**Admission Manager dashboard:** Total leads, new enquiries (today and this week), high/medium/low distribution, leads by source, leads by programme, funnel by lifecycle stage, upcoming appointments, overdue follow-ups, SLA breaches, campaign performance (sent, failed, replied, opted out), counsellor workload, disagreement queue.

**Counsellor dashboard:** Assigned leads sorted by priority, today's appointments, pending follow-ups, recent conversations, MOM drafts awaiting review, personal activity metrics.

**Acceptance criteria:**

- **AC14.1:** Dashboards load within 3 seconds at 10,000 leads (NFR-02).
- **AC14.2:** Every chart can be filtered by date range and programme.
- **AC14.3:** Reports can be exported as CSV.

## FR-15: Audit Logging and Approvals (P0)

**Description:** Every significant action is logged. Certain actions require human approval.

**Audit record includes:** Actor (user or agent), action, entity type and ID, timestamp, input and output references, tool name, result, approval status, failure reason.

**Approval-required actions:** Scholarship or fee communication, admission offer communication, MOM approval, assessment override, bulk campaign launch above a configured size, consent overrides.

**Acceptance criteria:**

- **AC15.1:** Audit records cannot be edited or deleted through the application. The database role used by the application has insert and select permission only on the audit table.
- **AC15.2:** Agent actions record the model name and version, prompt template ID, a hash of input context, and the validated output.
- **AC15.3:** Audit logs are searchable by lead, user, action, and date.

## FR-16: Administration and Configuration (P1)

**Acceptance criteria:**

- **AC16.1:** Admins can create users, assign roles, deactivate users, and view login history.
- **AC16.2:** Admins can configure programmes, eligibility criteria, counsellor specialisations, campuses, and campaign templates.
- **AC16.3:** Admins can configure integration credentials through environment or secret store, not through the UI in plain text.

# 8. Non-Functional Requirements


| ID     | Category        | Requirement                                                                                             |
| ------ | --------------- | ------------------------------------------------------------------------------------------------------- |
| NFR-01 | Security        | All traffic over HTTPS. Passwords hashed with Argon2 or bcrypt. JWT access tokens expire in 15 minutes. |
| NFR-02 | Performance     | CRM API P95 under 500 ms for database operations. Dashboard load under 3 seconds at 10,000 leads.       |
| NFR-03 | RAG latency     | Knowledge answers under 8 seconds at P95, excluding human approval wait time.                           |
| NFR-04 | Scalability     | Support 50,000 leads and 200 concurrent users in v1 without architectural change.                       |
| NFR-05 | Reliability     | Background jobs retry with bounded exponential backoff. No message is lost on worker restart.           |
| NFR-06 | Concurrency     | No double-booked slot under 50 simultaneous booking attempts.                                           |
| NFR-07 | Availability    | 99% uptime during the admission season window.                                                          |
| NFR-08 | Privacy         | Student PII is masked in application logs. Recordings are encrypted at rest.                            |
| NFR-09 | Retention       | Configurable retention periods. Deletion requests are processed and logged.                             |
| NFR-10 | Maintainability | Modular backend with service boundaries. Test coverage target of 80% on business logic.                 |
| NFR-11 | Explainability  | Every score, citation, and agent action can be traced from the UI.                                      |
| NFR-12 | Accessibility   | UI meets WCAG 2.1 AA for core workflows.                                                                |
| NFR-13 | Localisation    | Dates in IST. Support English interface and Hindi/English message templates.                            |


# 9. Business Rules Summary

1. Never send a promotional message without an active promotional consent record.
2. Never send a fee, scholarship, or admission-offer message without an approval record.
3. Never answer from memory when the knowledge base does not contain the answer. Escalate.
4. Never overwrite an AI assessment. Create a new version.
5. Never book a slot that is not in the counsellor's availability.
6. Never assign a lead to a counsellor who lacks permission for that lead's campus or programme.
7. Never mark a lead as Converted from AI output alone.
8. Never send more than the configured number of promotional messages in a rolling window.

# 10. Success Metrics


| Metric                      | Definition                                          | Baseline needed |
| --------------------------- | --------------------------------------------------- | --------------- |
| First response time         | Median time from enquiry to first reply             | Yes             |
| Lead contact rate           | Leads contacted / total leads                       | Yes             |
| Engagement rate             | Leads replying / leads contacted                    | Yes             |
| Counselling booking rate    | Leads booked / engaged leads                        | Yes             |
| Counselling completion rate | Completed / booked sessions                         | Yes             |
| Follow-up compliance        | Follow-ups within SLA / total follow-ups            | No (new metric) |
| Lead-to-application rate    | Applications / eligible leads                       | Yes             |
| Admission conversion rate   | Admissions / qualified leads                        | Yes             |
| AI reply acceptance rate    | Drafts approved without edit / drafts reviewed      | No              |
| Assessment agreement        | AI and counsellor category matches / total assessed | No              |


> **Important:** Collect baselines from the institution's current process before the pilot. Do not claim conversion improvement without a comparison period or control group.

# 11. Assumptions, Dependencies, and Open Questions

## Assumptions

- The institution can provide approved versions of its admission documents.
- At least one communication channel (email) is available with a domain the college controls.
- Counsellors can enter availability through the system.
- Lead data from partners includes at least name plus email or phone.

## Dependencies

- LLM provider account with API access.
- Transactional email provider account with a verified sending domain.
- WhatsApp Business Platform access (Phase 2).
- Calendar or video-meeting account for generating meeting links.

## Open questions to resolve with the college

1. Which channels do students use most: email, WhatsApp, website form, phone?
2. Does the college have historical admission records (lead → admission outcomes) for future model training?
3. What are the exact eligibility and fee rules per programme, and who signs off on them?
4. Are scholarships discretionary or formula-based? This determines what the AI may say.
5. Who owns data protection responsibility under DPDP Act obligations?
6. Are there existing admission portal or ERP systems that need integration?
7. What counsellor availability and specialisation data exists today?
8. Which meeting tool does the institution use (Google Meet, Zoom, Teams, none)?

## Legal note

> Outbound promotional communication in India is subject to consent rules under the DPDP Act 2023 and to telecom regulations (TRAI) for SMS and calls. WhatsApp Business Platform requires opt-in and pre-approved templates for business-initiated messages. Confirm the exact obligations with the institution's legal counsel before launching outbound campaigns.

# 12. Risks


| Risk                                               | Impact | Mitigation                                                                              |
| -------------------------------------------------- | ------ | --------------------------------------------------------------------------------------- |
| LLM gives incorrect fee or scholarship information | High   | Approval gate for sensitive intents, citation requirement, escalation on low confidence |
| Lead scores are wrongly trusted as predictions     | High   | Label as potential score, show factors, collect outcomes for calibration                |
| Duplicate or spam outbound messages                | High   | Idempotency keys, frequency caps, consent checks                                        |
| Double booking                                     | Medium | Database-level exclusion constraint                                                     |
| Poor transcription quality for accented speech     | Medium | Transcript review step, confidence markers, allow manual upload of transcript           |
| Partner data quality is poor                       | Medium | Validation report, mapping templates, rejection with reasons                            |
| Scope overrun from integrations                    | High   | Milestone gates, mock providers, Phase 2 and 3 separation                               |
| Personal data leak                                 | High   | RBAC, encryption, masked logs, audit trail                                              |


# 13. MVP Acceptance Scenario

The MVP is complete when this end-to-end scenario runs successfully on the demo environment:

1. Admin creates users with roles.
2. Admission manager imports 200 leads from a CSV containing 10 duplicates and 5 invalid rows. The error report lists the 5 invalid rows.
3. Admin uploads the approved B.Tech CSE brochure and scholarship policy.
4. Manager creates an email campaign for B.Tech CSE leads with score ≥ 80.
5. Rahul Sharma receives the email and replies asking about scholarships.
6. The reply is classified as `scholarship_query`. The draft cites the scholarship policy and is queued for approval.
7. The approver edits and approves the draft. Rahul receives it.
8. Rahul selects a slot. The system assigns a counsellor by the FR-09 rules and sends confirmations.
9. The counsellor marks the session complete and uploads a recording (or a transcript, if audio is not yet supported).
10. A draft MOM is produced. The counsellor approves it.
11. AI and counsellor assessments are both recorded. The disagreement flag is shown if applicable.
12. A follow-up task and a reminder are created.
13. Rahul's application status is set to Submitted by an authorised user.
14. The timeline shows the full history, and the audit log records each significant action.