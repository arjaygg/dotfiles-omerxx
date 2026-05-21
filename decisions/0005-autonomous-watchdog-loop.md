# 0005 — Autonomous Migration Watchdog Loop

**Date:** 2026-05-21
**Status:** Planned (not yet implemented)
**Derived from:** 28-day Claude Code insights report analysis

## Context

The migration-watchdog skill (codified 2026-05-21) is currently invoked manually per session.
Over 28 days, it was used ~18 sessions — the highest-frequency skill in the production monitoring
category. Each session recreated the 4-subagent pattern (K8s, DB, logs, metrics) from context.

The report identified this as one step away from becoming autonomous:
> "Your watchdog skill is one step away from becoming a continuous autonomous loop — running on a
> schedule, maintaining state across invocations, proposing remediation PRs from pre-approved
> playbooks, and only escalating when confidence drops."

## Decision

Upgrade `/migration-watchdog` to a `CronCreate`-based autonomous loop that:

1. **Runs on a schedule** (every 15 minutes during active migration windows)
2. **Maintains state across invocations** (writes status to a versioned state file, compares against prior run to detect regressions)
3. **Proposes remediation PRs** from pre-approved playbooks when anomalies are detected
4. **Only escalates** to the user when confidence in autonomous remediation drops below threshold

## Architecture

```
CronCreate(interval=15min, skill="migration-watchdog-autonomous")
  → migration-watchdog-autonomous skill:
      1. Read prior state from .claude/watchdog-state.json
      2. Dispatch 4 parallel subagents (K8s, DB, logs, metrics)
      3. Synthesize unified status
      4. Classify: HEALTHY | DEGRADED | FAILURE
         - HEALTHY: write state, exit silently
         - DEGRADED: write state + append to plans/watchdog-incidents.md
         - FAILURE: apply remediation playbook if confidence > 0.8, else PushNotification to user
      5. If remediation applied: spawn stack-auto-pr-merge to create and merge playbook PR
```

## Remediation Playbooks (pre-approved)

- **circuit-breaker-reset:** Restart auc-conversion deployment; verify pod health; wait 5m; re-check
- **migration-timeout-extend:** Patch job spec to extend timeout; kubectl apply; monitor
- **stale-pod-cleanup:** Delete pods in Error/CrashLoopBackOff state to force restart
- **db-lock-release:** Kill specific blocking queries (only if idle >5min and no user transaction)

## State Schema

```json
{
  "last_run": "ISO8601",
  "release": "v1.0.XXX",
  "overall": "HEALTHY|DEGRADED|FAILURE",
  "k8s": {"status": "OK", "summary": "..."},
  "db": {"status": "OK", "migration_tier": N, "summary": "..."},
  "logs": {"status": "OK", "anomalies": []},
  "metrics": {"status": "OK", "summary": "..."},
  "remediation_applied": null | "playbook-name",
  "escalated": false
}
```

## Why

- Eliminates 18 manual sessions per 28 days — recovers ~2-3 hours of interactive time
- Anomalies caught earlier (15min vs user-triggered)
- Remediations from playbooks are safer than ad-hoc fixes

## Alternatives Rejected

- **Manual forever:** High friction, context overhead per session
- **Monitor tool:** Better for event-based watching within a session; no cross-session state; no autonomous remediation
- **Pure cron (no LLM):** Can detect anomalies but can't synthesize multi-source RCAs or propose PRs

## Implementation Plan

1. Extract migration-watchdog 4-subagent pattern into a standalone skill variant
2. Define state schema and write/read helpers
3. Implement remediation playbooks as separate skills
4. Wire CronCreate invocation with RemoteTrigger
5. Gate on migration window detection (only run cron when active migration exists)

## Self-Driving PR Pipeline (Related)

The second horizon item — a self-driving PR pipeline that takes Hawk findings and admin-merges — is
a separate initiative. It would extend `stack-auto-pr-merge` to:
1. Accept a Hawk/Bugbot finding as input
2. Iterate the fix against tests until green
3. Address review comments autonomously
4. Admin-merge when all gates pass

This requires `/hawk` + `/stack-auto-pr-merge` + `/ci-watch` composition.
Tracked separately once the autonomous watchdog loop is stable.
