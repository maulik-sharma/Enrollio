# Open Questions and Next Steps

## Decisions to lock before coding begins

1. **Email provider:** SES or SendGrid for campaigns, and whether conversation threads use the same domain. Recommend a dedicated sending subdomain (for example, `mail.college.ac.in`) to protect the main domain's reputation.
2. **LLM provider:** Pick one primary provider and one fallback. Confirm data processing terms cover student data.
3. **Transcription location:** Local Whisper or hosted API. Local is preferable for recordings.
4. **Assessment labels:** Confirm the UI and reports always say "lead potential score" until historical validation exists.
5. **Auto-send policy:** Confirm which intents may be auto-sent. The default is FAQ only, with everything financial or admission-related requiring approval.
6. **Scoring weights and thresholds:** Get sign-off from the admissions team, since they are operational choices.

## Data needed from the college

- Sample enquiry export from a real partner (anonymised).
- Approved brochures, fee structures, scholarship policies, eligibility rules, deadlines.
- Counsellor list with specialisations, campuses, and typical availability.
- Historical admissions outcomes, if available, for calibration in Phase 3.
- Current contact channels and volumes.

## Immediate next steps

1. Confirm the open questions in Section 11 of the PRD with the college.
2. Create the repository and run M0.1 through M0.5 with the coding agent.
3. Collect the knowledge documents and begin the evaluation dataset in parallel (this is the slowest dependency).
4. Set up the email sandbox domain and LLM account so M3 and M4 are not blocked.
5. Review the first demo checkpoint at the end of M2: a working CRM with import, dedupe, lifecycle, and consent.