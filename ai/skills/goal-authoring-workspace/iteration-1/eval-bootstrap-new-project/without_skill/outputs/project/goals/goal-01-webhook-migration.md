---
id: 01
title: Migrate email notifications from cron polling to webhook triggers
status: proposed
owner: unassigned
created: 2026-07-16
updated: 2026-07-16
---

# Goal 01 — Migrate email notifications from cron polling to webhook triggers

## Context

`notify-svc` currently sends email notifications on a cron schedule. A periodic
job wakes up, polls the source of truth for events that need notifying, and
sends any pending emails.

This polling model has two problems:

- **Latency:** Notifications are delayed by up to one polling interval, because
  nothing is sent until the next scheduled run.
- **Wasted work:** Most polls find nothing new, so the service spends cycles (and
  DB queries) checking for work that isn't there.

The upstream system that produces these events can instead call us directly when
an event occurs. Moving to a webhook-driven trigger would make notifications
near-real-time and eliminate empty polls.

## Objective

Replace the cron-based polling loop with an inbound webhook endpoint that
triggers email notifications the moment an upstream event arrives, while
preserving at-least-once delivery.

## Success Criteria

- [ ] An authenticated inbound webhook endpoint exists and enqueues a
      notification for each valid event payload.
- [ ] A notification is sent within seconds of the triggering webhook (no
      dependence on a polling interval).
- [ ] The cron polling job is removed (or disabled behind a flag) with no
      regression in delivery.
- [ ] Duplicate/retried webhooks do not produce duplicate emails (idempotent by
      event id).
- [ ] Webhook auth is verified (shared secret or signature) and unauthenticated
      requests are rejected.
- [ ] Rollback path is documented: polling can be re-enabled if webhooks fail.

## Milestones

- [ ] **M1 — Design & contract.** Agree the webhook payload schema, auth method,
      and idempotency key with the upstream team.
- [ ] **M2 — Endpoint.** Implement the webhook receiver: validate auth, parse
      payload, enqueue the notification.
- [ ] **M3 — Idempotency & retries.** Dedupe by event id; handle upstream retries
      safely.
- [ ] **M4 — Dual-run.** Run webhooks and cron polling in parallel; compare that
      both produce the same notifications (shadow/verify).
- [ ] **M5 — Cutover.** Disable the cron job; webhooks become the sole trigger.
- [ ] **M6 — Cleanup.** Remove polling code and its schedule once stable.

## Risks

- **Missed events if the webhook fails.** Upstream must retry on non-2xx, and we
  keep the polling job as a fallback (behind a flag) until M6 proves stable.
- **Duplicate emails from retried webhooks.** Mitigated by idempotency keying on
  event id (M3).
- **Auth/spoofing on a public endpoint.** Require a shared secret or signature;
  reject anything unverified.
- **Upstream can't (yet) send webhooks.** Confirm feasibility in M1 before
  committing to cutover; the dual-run phase (M4) de-risks the switch.
