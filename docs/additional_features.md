# Future Enhancements

These are beyond the PRD's core scope. They are ordered by value to the college relative to effort.

## High value, moderate effort

- **Eligibility self-check.** A short form on the website that tells a student whether they meet the programme's criteria, using the same deterministic rules as scoring. Produces qualified leads without counsellor time.
- **Fee and scholarship estimator.** A calculator driven by approved fee tables and scholarship formulas. It only shows figures from approved documents.
- **Document checklist and application tracker.** A student-facing checklist (marksheets, ID, photo) with completion status. Reduces back-and-forth and gives the follow-up agent a concrete "application incomplete" signal.
- **Reactivation campaigns for cold leads.** Segment leads that have been inactive for 90 days, and generate campaign content that references their previous interest and concern (for example, "you asked about hostel options last year").
- **Deadline reminder engine.** Admission calendar driven, sending reminders to students who have not completed steps before a published deadline.
- **Counsellor coaching insights.** From approved MOMs, show talk-to-listen ratio, objection frequency, and missed next-steps. Helps counsellor training.
- **Lead source quality report.** Cost per enquiry and cost per admission by partner or fair, once cost data is entered. Helps the college decide where to spend on lead acquisition.

## High value, higher effort

- **Human handoff mid-conversation.** A counsellor can take over an AI-driven thread with one click. The agent pauses for that thread and shows the counsellor a summary of what was said.
- **Hindi and Hinglish support.** Reply drafts and templates in Hindi, with language detection on inbound messages. Test with real student messages before enabling.
- **Website chat widget with embeddable script.** Reuses the enquiry agent, with a counsellor-booking CTA. Needs strict rate limiting and abuse controls.
- **Parent communication track.** Separate consent, separate contact, and parent-friendly content. Triggered by the "parent involvement" field in MOMs.
- **Student data quality dashboard.** Shows missing fields by source, invalid phone rates, and duplicate rates, so partners can be given feedback.
- **Bulk reassignment and workload balancing.** When a counsellor goes on leave, reassign their leads by the same rules, with a preview before applying.

## Advanced (Phase 3)

- **Conversion forecasting.** Trained on historical admission outcomes. Only after data exists and only with validated accuracy reporting.
- **ERP and admission portal sync.** Push admitted students to the college ERP and pull application status back.
- **Counsellor mobile app (PWA).** Offline access to lead cards and quick MOM entry after calls.
- **Waitlist and seat-matrix awareness.** Agent can tell students whether seats are available, based on a live seat-count integration.
- **Explainability view for agent decisions.** For any message sent, show the exact intent, retrieved chunks, grounding result, and approver. Valuable for audit and for defending the system to the college.

## Things I would deliberately not build yet

- Fully autonomous fee or scholarship commitments.
- A custom vector database.
- Multi-agent free-form chat between agents. Keep orchestration explicit and tool-based.
- Auto-generated marketing content without human review.
- Voice calling before the email and scheduling loop is stable.