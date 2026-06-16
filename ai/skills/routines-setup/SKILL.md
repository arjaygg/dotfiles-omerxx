---
name: routines-setup
description: |
  Set up a cloud Routine (nightly cron) on the personal arjaygg GitHub account.
  Routines run as scheduled remote Claude sessions — use only for work that can
  reach public GitHub repos (axos-financial/EMU org access unverified).
  See decisions/0008-cloud-routines-scope.md for access boundary.
  Trigger: /routines-setup
version: "1.0"
triggers:
  - /routines-setup
  - setup routine
  - cloud routine
  - nightly routine
---

# Routines Setup

One-time setup for a cloud Routine. A Routine is a scheduled remote Claude session
— not a local CronCreate. Runs even when your terminal is closed.

## Access boundary (read before proceeding)

**Can reach:** public GitHub repos on the arjaygg personal account.
**Cannot reach:** Azure DevOps (ADO), axos-financial EMU org (unverified), StrongDM, kubectl, databases.
**Identity:** Routines act as your GitHub identity without per-action prompts — arjaygg only, not EMU.

See `decisions/0008-cloud-routines-scope.md` for full scope and rationale.

## Prerequisites

- Verify the target repo is reachable: `gh repo view <repo>` should succeed under arjaygg identity.
- Run `gh auth switch --user arjaygg` first.
- Target repo must be on the personal account, not axos-financial.

## Step 1 — Verify access

```bash
gh auth switch --user arjaygg
gh repo view arjaygg/<target-repo>
```

If this fails, abort — do not create a Routine for an unreachable repo.

## Step 2 — Create the Routine

Use the Claude Code UI or API:

```
Schedule: cron_expression (minimum interval: 1 hour)
OR
run_once_at: <ISO8601 UTC timestamp>
```

No GitHub-event triggers are available on this account. No HTTP triggers either.

Prompt should be self-contained (no session state persists between ticks).

## Step 3 — Verify the pilot tick

After the first scheduled tick completes, confirm:
- The routine ran (check Claude routines dashboard or API)
- The output was correct
- No unintended side effects on the target repo

## What NOT to schedule as a cloud Routine

- Anything requiring ADO CLI (`az repos`, `az devops`) — network unreachable
- axos-financial org repos — EMU access unverified
- StrongDM / kubectl / database operations — not reachable from cloud sandbox
- Destructive or write operations until read-only is verified first

Use local `CronCreate` for watchdog/K8s/DB work instead — see `/watchdog-cron-setup`.
