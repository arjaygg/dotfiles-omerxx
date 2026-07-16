# <Project> Goals

Source plan: `plans/YYYY-MM-DD-<context>.md` (optional — link back to the session that spawned these goals, if any).

## Status

| Seq | Status | Goal | Outcome |
|---:|---|---|---|
| 01 | pending | `YYYY-MM-DD-01-slug.md` | One-line outcome/summary. |

## Global guardrails

- Live code/DB are authoritative; docs are hints only.
- Production access is read-only unless a goal explicitly says otherwise.
- Preserve PII discipline where relevant: aggregate/mask; never export raw identity-bearing values.
- Update `plans/active-context.md`, `plans/progress.md`, and `plans/decisions.md` after each material step.
- Stop and ask before starting any production-touching run, retry, or remediation with wide blast radius.
