# notify-svc Goals

Source plan: none (goals bootstrapped directly for the webhook migration).

## Status

| Seq | Status | Goal | Outcome |
|---:|---|---|---|
| 01 | pending | `2026-07-16-01-email-notify-cron-to-webhook.md` | Migrate email-notification delivery from cron polling to a webhook-driven trigger and retire the poller. |

## Global guardrails

- Live code/DB are authoritative; docs are hints only.
- Production access is read-only unless a goal explicitly says otherwise.
- Preserve PII discipline where relevant: aggregate/mask; never export raw identity-bearing values.
- Update `plans/active-context.md`, `plans/progress.md`, and `plans/decisions.md` after each material step.
- Stop and ask before starting any production-touching run, retry, or remediation with wide blast radius.
