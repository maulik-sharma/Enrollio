## Task

- Task ID (from `docs/plan.md`): `M_.__`
- Summary:

## Definition of done

- [ ] `make lint` passes
- [ ] `make typecheck` passes
- [ ] `make test` passes (no new skips without a recorded reason)
- [ ] `make smoke` passes if Docker, migrations, or readiness changed
- [ ] Migration created **and reversible** if the schema changed
- [ ] Every new endpoint declares a permission and has an unauthorised-role test
- [ ] New configuration added to `.env.example` with a comment
- [ ] No PII in logs; masking tests updated if new log shapes were added
- [ ] No secrets, `.env`, recordings, or student data committed
- [ ] `docs/ARCHITECTURE.md` updated if the design changed
- [ ] `docs/PROJECT_CONTEXT.md` updated (status, verification, decisions, risks)
- [ ] Commit message starts with the task ID
