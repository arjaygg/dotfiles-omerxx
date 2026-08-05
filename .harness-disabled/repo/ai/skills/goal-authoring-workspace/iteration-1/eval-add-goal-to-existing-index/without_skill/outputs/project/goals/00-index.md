# api-gateway Goals

## Status

| Seq | Status | Goal | Outcome |
|---:|---|---|---|
| 01 | pending | `2026-06-01-01-add-request-logging.md` | Not started. |
| 02 | active | `2026-07-16-02-add-rate-limiting.md` | In progress. |

## Global guardrails

- Never touch production config directly — all changes go through the deploy pipeline.
- Update `plans/active-context.md` whenever a goal becomes active.
- Stop and ask before touching auth middleware.
