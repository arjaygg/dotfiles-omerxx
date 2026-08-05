# Goal 01 — Migrate email-notification service from cron polling to webhook triggers

## Objective

Replace notify-svc's cron-based polling loop with a webhook-driven trigger so email
notifications are sent in direct response to an upstream event, and fully retire the
scheduled poller once the webhook path is proven in production.

## Why

notify-svc currently wakes on a fixed cron schedule, queries for pending
notifications, and sends whatever it finds. This adds latency equal to (up to) one
polling interval on every notification, wastes work on empty polls, and makes delivery
timing coarse and unpredictable. A webhook trigger lets the upstream system notify us
the moment a notification is due, cutting delivery latency to near-real-time and
removing idle polling load.

## Current state

- notify-svc is a small internal service (see repo `README.md`) that sends email
  notifications on a cron schedule.
- Delivery is driven entirely by the scheduled poll; there is no inbound HTTP trigger
  path today.
- The upstream event source, exact cron interval, email transport, and where the
  service is deployed are not yet documented in this repo and must be confirmed before
  implementation (see "Stop and ask if").
- No webhook endpoint, request authentication, or idempotency handling exists yet.

## Non-goals

- Changing the content, formatting, templating, or recipients of the emails themselves.
- Migrating or re-platforming the email transport/provider.
- Adding new notification types or event sources beyond the one that currently drives
  the cron poll.
- Building a general-purpose event bus — this goal delivers exactly one webhook trigger
  path replacing exactly one poll loop.

## Steps

1. Document the current behaviour: identify the cron entrypoint, the polling interval,
   the query it runs for pending notifications, and the send path it invokes. Record
   findings in `plans/decisions.md`.
2. Identify and confirm the upstream event source that should call the webhook, and the
   event shape/payload it can send. Confirm auth mechanism available (shared secret,
   HMAC signature, mTLS).
3. Design the webhook endpoint: route, request authentication/verification, payload
   validation, idempotency key handling (so a retried/duplicate webhook does not send a
   duplicate email), and the response contract (2xx on accepted, 4xx on bad payload).
4. Implement the webhook handler that maps a verified inbound event to the existing send
   path, reusing the current email-send code rather than duplicating it.
5. Add tests: unit tests for auth/validation/idempotency, and an end-to-end test that a
   valid webhook results in exactly one email send and a duplicate webhook results in
   zero additional sends.
6. Run cron poller and webhook path in parallel (dual-run) in a non-production
   environment; verify webhook-triggered sends match what the poller would have sent,
   with no duplicates and no misses.
7. After explicit user go-ahead, enable the webhook path in production while the cron
   poller is still running as a safety net; monitor for duplicate/missed sends.
8. Once the webhook path is confirmed healthy in production over an agreed observation
   window, disable and remove the cron poller and its scheduling config.

## Acceptance criteria

- A documented, authenticated webhook endpoint exists and, on a valid verified event,
  triggers exactly one email send.
- A duplicate/retried webhook for the same event triggers zero additional sends
  (idempotency proven by an automated test).
- Automated tests (unit + end-to-end) covering auth, validation, idempotency, and
  single-send behaviour pass in CI.
- Dual-run in a non-production environment shows webhook-triggered output matches the
  cron poller's output for the same events (no duplicates, no misses) — evidence
  captured in `plans/progress.md`.
- The cron poller and its schedule are removed from the codebase and deployment config,
  and the repo `README.md` no longer describes notify-svc as cron-scheduled.
- Explicit user sign-off recorded before production enablement and before poller
  removal.

## Evidence to update

- `plans/decisions.md` — current-behaviour findings, webhook design decisions
  (auth mechanism, idempotency strategy), and the production cutover decision.
- `plans/progress.md` — step-by-step progress, dual-run comparison results.
- `plans/active-context.md` — current focus while this goal is active.
- Repo `README.md` — updated service description once the cron poller is removed.
- The test suite covering the webhook handler (path recorded once created).

## Stop and ask if

- The upstream event source, its payload shape, or the available webhook auth mechanism
  cannot be confirmed — do not guess and build against an assumed contract.
- Before enabling the webhook path in production, and again before disabling/removing the
  cron poller — both are production-touching cutover actions requiring explicit user
  go-ahead.
- Dual-run reveals any duplicate or missed sends — stop and reconcile before proceeding
  to production.
- The migration would require changing email content, recipients, or transport (out of
  scope for this goal per Non-goals).
