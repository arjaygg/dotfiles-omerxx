# 0008 — Cloud Routines Access Boundary

**Date:** 2026-06-16
**Status:** Active

## Decision

Cloud Routines are scoped to the personal arjaygg GitHub account only. They are the right primitive for nightly/hourly tasks that need to run without a terminal open, but only for repos reachable from that account.

## Context

Claude Code cloud Routines (v2.1.x) schedule remote Claude sessions. They support:
- `cron_expression` (minimum 1-hour interval)
- `run_once_at` (one-shot UTC timestamp)

No GitHub-event triggers, no HTTP triggers — cron/once only on this account.

The user's cloud environment binds to the personal arjaygg GitHub account with zero configured connectors.

## Access Boundary

| Target | Reachable? | Notes |
|--------|-----------|-------|
| arjaygg personal repos (github.com) | ✅ Yes | Verified primary use case |
| axos-financial (EMU org) | ❓ Unverified | EMU accounts may block cross-identity access |
| Azure DevOps (dev.azure.com/bofaz) | ❌ No | ADO network unreachable from cloud sandboxes |
| StrongDM / kubectl / databases | ❌ No | Requires VPN + cluster context; cloud-only sessions lack both |
| axos-financial GitHub (EMU) | ❓ Assume No | Until proven otherwise per security caution |

## Identity Risk

Routines act as the arjaygg GitHub identity without per-action prompts. This means:
- Commits, PRs, issues created by Routines are attributed to arjaygg
- Do NOT use Routines for axos-financial work — arjaygg is the personal account, not the EMU account
- The feedback memory "always use arjaygg (not EMU) for gh CLI ops in this repo" applies here too

## Alternatives Rejected

- **Local CronCreate:** Correct for watchdog/K8s/DB work that needs StrongDM/kubectl access. Session-scoped; pauses when Claude session ends. Not an alternative for "runs without a terminal."
- **GitHub Actions:** Correct for CI/CD. Runs in the axos-financial org context. Better for EMU-scoped work.

## How to Apply

- Before setting up a Routine, check `decisions/0008-cloud-routines-scope.md` to confirm the target is reachable.
- Use `/routines-setup` skill for the setup flow.
- Use `/watchdog-cron-setup` for local K8s/DB monitoring (session-scoped, not cloud).
