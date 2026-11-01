# 15. Testing Strategy

## 15.1 Test pyramid

| Layer        | Tool                                              | Scope                                                                                     | Run                                            |
| ------------ | ------------------------------------------------- | ------------------------------------------------------------------------------------------ | ----------------------------------------------- |
| Unit         | pytest, Vitest                                    | Pure functions: normalisers, scoring, assignment, template rendering, rule conditions      | Every commit                                    |
| Integration | pytest with testcontainers (real Postgres, Redis, MinIO) | Services with database, API endpoints, workers                                      | Every commit                                    |
| Contract    | pytest                                            | Provider adapters against interface                                                        | Every commit (mocks), nightly (real sandboxes)   |
| End-to-end   | Playwright                                        | Browser flows                                                                                | Every merge to main                              |
| AI evaluation | Custom harness in `tests/eval`                  | RAG, intent, signal extraction, MOM                                                         | Nightly and before release                       |
| Security     | pytest, custom scripts, gitleaks, pip-audit       | RBAC matrix, injection, webhooks, secrets                                                  | Every merge                                      |
| Load         | k6                                                | Concurrency and performance                                                                 | Before release                                   |

## 15.2 Critical test gates (release blockers)

1. Cross-counsellor data access is impossible (M1.3).
2. 50 concurrent bookings produce exactly one confirmed appointment (M5.3).
3. Opted-out students receive zero promotional messages (M2.6, M3.3, M7.3).
4. Sensitive-category messages are never sent without an approval record (M3.3, M4.7).
5. Unanswerable knowledge questions are escalated at least 90% of the time (M4.4).
6. Fabricated fee or scholarship figures are blocked by the grounding check (M4.4).
7. AI cannot set lifecycle to Converted (M2.5, M4.6).
8. Audit log cannot be modified by the application role (M7.8).
9. Webhook replays and duplicate events cause no duplicate actions (M3.7, M7.1).
10. Campaign worker restart causes no duplicate sends (M3.6).

## 15.3 Evaluation datasets to create

Create these before the relevant milestone begins. Keep them in `tests/eval/datasets/`.

| Dataset            | Size       | Contents                                                                                             | Used in |
| ------------------ | ---------- | ----------------------------------------------------------------------------------------------------- | ------- |
| Knowledge Q&A      | 40 questions | 25 answerable (with expected chunk and citation), 15 unanswerable or partially answerable          | M4.4    |
| Intent labels      | 60 messages | Balanced across intent classes, includes 10 opt-outs, 5 complaints                                    | M4.5    |
| Signal extraction  | 30 conversation excerpts | Labelled for course interest, intent, timeline, financial fit                          | M6.3    |
| MOM transcripts    | 10 transcripts | Known facts list per transcript, known objections                                                  | M6.7    |
| Import fixtures    | 4 files    | Clean 100 rows; mixed 100 rows with 10 invalid and 5 duplicate; XLSX with merged cells; 10,001-row file | M2.3    |
| Scoring cases      | 25 cases   | Boundary values, missing signals, expected categories                                                 | M6.2    |
| Assignment scenarios | 12 cases | One per rule and combinations                                                                          | M5.4    |

## 15.4 Sample test case (for the coding agent to follow as a pattern)

```python
# tests/integration/test_booking_concurrency.py
import asyncio
import pytest

@pytest.mark.asyncio
async def test_fifty_concurrent_bookings_yield_exactly_one_success(
    db_session_factory, seeded_slot, make_lead, booking_service
):
    leads = [await make_lead(f"student{i}@test.in") for i in range(50)]

    async def attempt(lead):
        async with db_session_factory() as session:
            try:
                return await booking_service.book(session, lead.id, seeded_slot.id)
            except SlotConflict:
                return None

    results = await asyncio.gather(*(attempt(l) for l in leads))

    successes = [r for r in results if r is not None]
    assert len(successes) == 1

    async with db_session_factory() as session:
        count = await session.scalar(
            "SELECT count(*) FROM appointments WHERE slot_id = :s AND status = 'confirmed'",
            {"s": seeded_slot.id},
        )
    assert count == 1
```