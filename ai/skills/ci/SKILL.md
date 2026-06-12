---
name: ci
description: "CI router. Routes to ci-watch (fire-and-forget background monitor for current PR), ci-status (read cached plans/ci-status.md), or ci-monitor (webhook-based pipeline monitor). Use for: 'watch CI', 'CI passed?', 'monitor the pipeline', 'notify me when CI finishes', 'check build status'."
triggers:
  - "/ci"
disable-model-invocation: false
---

# CI Router

Dispatches to the right CI skill based on user intent:

| Intent | Skill |
|--------|-------|
| "Watch CI for current PR" / "notify me when CI finishes" | `/ci-watch` — background shell poller, returns in <5s |
| "Is CI passing?" / "what's the CI status?" | `/ci-status` — reads cached `plans/ci-status.md` |
| "Monitor pipeline failures" / webhook mode | `/ci-monitor` — cicd-monitor agent, persistent webhook |

## Quick Dispatch

- **`/ci-watch`** — Launch background poller for current PR. Returns immediately. Writes to `plans/ci-status.md` on state change. Sends macOS notification on completion.
- **`/ci-status`** — Read `plans/ci-status.md`. Report run ID, status, conclusion, URL. If no file: suggest `/ci-watch`.
- **`/ci-monitor`** — Full monitoring agent with LogSage/RFM classification. Use for complex pipelines or when ci-watch is insufficient.

## Routing Logic

1. If the request includes "watch", "notify", "when CI" → `/ci-watch`
2. If the request includes "status", "is it passing", "check" → `/ci-status`
3. If the request includes "monitor", "webhook", "pipeline failures" → `/ci-monitor`
4. If ambiguous and in an active PR session → `/ci-watch` (default)
