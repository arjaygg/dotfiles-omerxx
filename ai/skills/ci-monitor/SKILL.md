---
name: ci-monitor
description: "Self-healing CI/CD monitor. Spawns cicd-monitor agent in poll mode — checks GitHub Actions, classifies failures, auto-retries HIGH, escalates CRITICAL. Use this whenever you want autonomous pipeline healing in your session. Invoke via /ci-monitor or schedule via /loop."
version: 2.1
triggers:
  - "/ci-monitor"
  - "/monitor-ci"
---

# CI Monitor Skill

Thin wrapper — spawns the `cicd-monitor` agent in **poll mode** (foreground, visible, interruptible).

## Instructions

Spawn the `cicd-monitor` agent using the Agent tool with these parameters:

- **subagent_type:** `cicd-monitor`
- **mode:** foreground (user can see output and interrupt)
- **context:** tell the agent to use **Mode A (poll)** — do NOT start an HTTP server

Pass this context to the agent:

```
Run in Mode A (poll mode):
- Poll GitHub Actions: gh run list --repo axos-financial/auc-conversion --limit 10 --json databaseId,name,status,conclusion,createdAt,headBranch
- Check .serena/memories/cicd-acted-runs.md for already-acted run IDs (skip those)
- For new failures: classify with LogSage/RFM, act (retry HIGH, escalate CRITICAL, log MEDIUM)
- Append acted run IDs to .serena/memories/cicd-acted-runs.md
- Report findings here
```

## Stopping

Cancel the scheduled loop: `CronDelete("5b32626f")`

## Related

- `/loop 5m /ci-monitor` — re-schedule if cron expired
- cicd-monitor agent: `~/.dotfiles/.claude/agents/cicd-monitor.md`
