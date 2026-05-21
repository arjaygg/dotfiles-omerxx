---
name: migration-watchdog
description: "Parallel 4-subagent health check for auc-conversion migrations. Dispatches K8s, DB,
  app-logs, and metrics agents concurrently, synthesizes a unified status report, and performs RCA
  when anomalies are detected. Use after deploying a release or when a migration is running."
version: 1.0
triggers:
  - "/migration-watchdog"
---

# Migration Watchdog Skill

Dispatches four parallel subagents to gather migration health signals, then synthesizes a unified
status report. When anomalies are found, performs root-cause analysis using all four signal streams
before concluding.

## When to Use

- After deploying an auc-conversion release (e.g., v1.0.XXX)
- When a migration job is actively running and you want a health snapshot
- When users report migration anomalies (circuit breaker trips, PK violations, INT overflow)
- When asked to "resume" a migration — always run watchdog first to check existing state

## Instructions

### Step 1 — Gather context

Before dispatching agents, determine:

```bash
# Current release in K8s
kubectl get deploy -n auc-conversion -o jsonpath='{.items[*].spec.template.spec.containers[*].image}' 2>/dev/null | tr ' ' '\n' | grep auc-conversion | head -5

# Active migration jobs
kubectl get jobs -n auc-conversion --sort-by=.metadata.creationTimestamp 2>/dev/null | tail -10

# Most recent pods
kubectl get pods -n auc-conversion --sort-by=.metadata.creationTimestamp 2>/dev/null | tail -15
```

### Step 2 — Dispatch 4 parallel subagents

Launch all four as background agents simultaneously using `Bash(run_in_background: true)`:

**Agent 1 — K8s Health:**
```
Check K8s pod health for auc-conversion namespace:
- All pods Running/Completed (no CrashLoopBackOff, Error, OOMKilled, Pending)
- Recent events: kubectl get events -n auc-conversion --sort-by=.lastTimestamp | tail -20
- Deployment rollout status: kubectl rollout status deploy -n auc-conversion
- Any init container failures
Output: single structured block: POD_STATUS=OK|WARN|FAIL, EVENTS=<summary>, ROLLOUT=<status>
```

**Agent 2 — DB State:**
```
Check auc-conversion database migration state:
- Current migration version/tier (query migrations table or config)
- Row counts for recently migrated tables vs expected
- Any index creation in progress (pg_stat_activity for CREATE INDEX)
- Lock contention: pg_locks joined to pg_stat_activity for blocking queries
- Circuit breaker state if accessible
Output: single structured block: DB_STATE=OK|WARN|FAIL, MIGRATION_TIER=<N>, ROW_COUNTS=<summary>, LOCKS=<none|details>
```

**Agent 3 — App Logs:**
```
Stream recent auc-conversion app logs for anomalies:
- kubectl logs -n auc-conversion deploy/auc-conversion --since=30m --tail=200
- Filter for: ERROR, FATAL, panic, circuit breaker, PK violation, INT overflow, timeout, failed
- Note any patterns (repeated errors, escalating frequency)
Output: single structured block: LOG_STATUS=OK|WARN|FAIL, ANOMALIES=<list or "none">, SAMPLE=<3 most significant lines>
```

**Agent 4 — Metrics:**
```
Check auc-conversion performance metrics:
- Pod CPU/memory: kubectl top pods -n auc-conversion
- If Prometheus/Grafana accessible: error rate, p99 latency, throughput
- Job duration vs baseline (index creation should be <2hr for typical tables)
Output: single structured block: METRICS_STATUS=OK|WARN|FAIL, CPU=<summary>, MEMORY=<summary>, THROUGHPUT=<if available>
```

### Step 3 — Synthesize report

After all four agents complete, produce this report structure:

```
## Migration Watchdog Report — <timestamp>

**Release:** <version>
**Overall:** ✅ HEALTHY | ⚠️ DEGRADED | ❌ FAILURE

### Signal Summary
| Source | Status | Key Finding |
|--------|--------|-------------|
| K8s    | OK/WARN/FAIL | <one line> |
| DB     | OK/WARN/FAIL | <one line> |
| Logs   | OK/WARN/FAIL | <one line> |
| Metrics| OK/WARN/FAIL | <one line> |

### Details
<expand any WARN or FAIL rows with full agent output>

### Checked
- [x] K8s pod health + events
- [x] DB migration state + row counts
- [x] App logs (last 30m)
- [x] CPU/memory metrics

### Not Checked
- [ ] <anything not accessible — be explicit>

### Recommendation
<lead with action: "No action needed", "Investigate X", "Roll back to vY.Z", etc.>
<supporting evidence follows>
```

### Step 4 — RCA if anomalies found

If any agent reports WARN or FAIL:

1. Do NOT conclude root cause from a single signal source.
2. Cross-reference: does the DB lock timing match the log ERROR timestamps? Does CPU spike match K8s restart?
3. State hypothesis explicitly: "Hypothesis: X caused by Y, evidenced by [Log line] + [DB state]"
4. List what additional checks would confirm or refute the hypothesis.
5. Never recommend "resume" without first verifying no migration is already running (check DB migration state + active K8s jobs).

### Step 5 — Migration resume check

If user asks to "resume" a migration:

```bash
# ALWAYS check first:
# 1. Is a migration job currently running?
kubectl get jobs -n auc-conversion | grep -E "(Running|Pending)"

# 2. What is the current migration state in DB?
# (query depends on project schema — check migrations table)

# 3. What was the last successfully completed tier/batch?
```

Only if no active migration is found AND DB state confirms incomplete: proceed with resume.
Never start a new migration without completing this check.
