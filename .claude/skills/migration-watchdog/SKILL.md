---
name: migration-watchdog
description: Autonomous manager agent for large-scale data migrations. Spawns 4-agent monitoring loop (Observer, DB Health, Log Analyst, Metrics), detects anomalies, investigates root causes, proposes RFC/ADR-based remediation via GitHub PRs. READ-ONLY by design — all changes go through PR review.
version: 1.0
triggers:
  - "Set up production monitoring for a data migration"
  - "Launch migration watchdog"
  - "Start continuous migration health monitoring"
  - "Create autonomous migration oversight"
---

# Migration Watchdog

Autonomous manager agent for large-scale data migrations running on Kubernetes + SQL Server.

## When to Use

Use this skill when you have:
- **15B+ record migration** from source → 300+ destination databases
- **Golang supervisor-worker** system on Kubernetes
- **Need for continuous**, non-stop monitoring without human intervention
- **Production risk** that demands proactive anomaly detection and escalation
- **Change governance** requirement (all fixes through PR review, no direct system changes)

## What It Does

Spawns a 4-agent team in continuous control loop:

1. **Observer Agent** — Kubernetes pod health, restarts, resource utilization, pending pods
2. **DB Health Agent** — Source/destination connection pools, query latency, replication lag, deadlocks
3. **Log Analyst Agent** — Error patterns, panic traces, worker failures, supervisor anomalies
4. **Metrics Agent** — Prometheus/Grafana throughput, latency, error rates, queue depth

On anomaly detection:
- **Investigates** via Root Cause Agent (code + logs + metrics deep-dive)
- **Proposes** RFC/ADR document with remediation options
- **Creates stacked GitHub PR** with full context for human review
- **Resumes monitoring** — does not approve its own changes

### Health Thresholds (Investigation Triggers)

| Signal | Warning | Critical |
|---|---|---|
| Worker pod restarts | >2 in 10 min | >5 in 10 min |
| OOMKill events | Any | Any |
| Pending pods | >3 | >10 |
| Throughput drop | >20% below baseline | >50% below baseline |
| Error rate | >1% of records | >5% of records |
| DB connection failures | >3 consecutive | Any total failure |
| Query latency | >2x baseline | >5x baseline |
| Queue depth growth | >10%/min for 5 min | Exponential growth |

## How to Start

```bash
# Option 1: Invoke the skill to launch watchdog for this migration
/migration-watchdog

# Option 2: Configure for auto-resume on deployment
# (Watchdog polls every 5-15 min depending on health state)
```

## What You Get

### Continuous Status Reports
```
## Migration Watchdog Status — [timestamp]
- Records migrated: 2.1B / 15B (14%)
- Current throughput: 47K records/sec
- ETA to completion: 3.2 days
- Active workers: 10 / 10 ✅
- Destination DBs healthy: 298 / 300 ⚠️

### Health Summary
| Signal | Status | Trend |
| Worker health | 🟢 | → |
| Source DB | 🟢 | → |
| Destination DBs | 🟡 | ↓ |
| Throughput | 🟢 | ↑ |
```

### Automated Investigations & PRs
- RCA document (root cause analysis with hypotheses + evidence)
- RFC/ADR proposal (options, risk, reversibility, fitness function)
- Stacked GitHub PR (ready for human review, never auto-merged)

### Proactive Escalations
- Open PR >24h with no review → follow-up summary posted
- Unresolved investigation >2h → escalation with current hypotheses
- Throughput declining → trend analysis + causal hypothesis
- Pre-mortem risk scan during stable periods

## Architecture

### Agent Team (spawned on skill invocation)

**Standing Agents** (loop continuously):
- Observer — Kubernetes state polling
- DB Health — Database health checks
- Log Analyst — Log parsing + error detection
- Metrics Agent — Prometheus/Grafana queries

**On-Demand Agents** (spawned on trigger):
- Root Cause Agent — Investigation
- RFC Drafter Agent — Proposal document
- PR Agent — GitHub PR creation (PR-stacked)
- Research Agent — Pattern/benchmark lookup
- Cost Optimizer Agent — Token usage optimization

### Control Loop (Adaptive Polling)

```
1. Collect reports from all 4 standing agents
2. Synthesize into unified health snapshot
3. Evaluate against thresholds
4. IF anomaly → spawn Root Cause Agent → Investigation Mode
5. IF healthy → generate status report
6. Calculate next poll interval:
   - High activity: 60s
   - Normal ops: 5 min
   - Healthy + low variance: 15 min
   - Healthy + sleeping: resume on alert
7. PAUSE until next interval
REPEAT
```

### Change Governance (Absolute Constraints)

1. **Read-only by default** — no direct system changes
2. **RFC/ADR for all proposals** — structured decision documents
3. **GitHub PR only** — all changes go through review
4. **PR-stacked** — each PR addresses one concern, dependencies tracked
5. **No self-approval** — human engineer reviews all PRs

## Configuration

Watchdog auto-discovers via `kubectl` + `configmap`/`secret` reads:

```bash
# Required environment / kubectl access:
export KUBECONFIG=...              # Kubernetes cluster
export GH_TOKEN=...                 # GitHub PR creation
export CLUSTER_NAMESPACE=prod       # Where migration runs

# Watchdog reads from (read-only):
- kubectl get all --all-namespaces
- ConfigMaps: source DB details, supervisor config
- Secrets: destination DB credentials
- Pod logs via kubectl logs
- Metrics endpoint (Prometheus or equivalent)
```

## Example Output

### Status Report (every 5–15 min)
```
## Migration Watchdog Status — 2026-04-04T14:35:00Z

### Migration Progress
- Records migrated: 10.67M / 69.47M (15.4%)
- Current throughput: 2,292 records/sec
- ETA to completion: 8.2 hours
- Active workers: 10 / 10 ✅
- Destination DBs healthy: 299 / 300

### Health Summary
| Signal | Status | Trend |
| Worker health | 🟢 | ↑ |
| Source DB | 🟢 | → |
| Destination DBs | 🟢 | → |
| Throughput | 🟢 | ↑ |
| Error rate | 🟢 | → |

### Open Investigations
- None

### Open PRs
- [auc-deployment-manifest#15](https://github.com/axos-financial/auc-deployment-manifest/pull/15): fix(scheduler): correct worker label selector — under review
- [auc-conversion#196](https://github.com/axos-financial/auc-conversion/pull/196): db: add covering index on KeyMap_20 — approved, awaiting merge

### Next Check-In
2026-04-04T14:50:00Z (15 min — normal ops)
```

### Investigation Report (on anomaly)
```
## Root Cause Analysis — Memo Table Queue Stall

### Symptom
All 10 workers stuck on Memo table. ETLRowNumber range query takes 2–7.5 sec.

### Root Cause (High confidence)
Clustered PK on KeyMap_20: (DestinationTable, NaturalKey, ETLRowNumber)
Query filtering on ETLRowNumber alone → full table scan + sort.

### Remediation Options
A. Add covering index IX_KeyMap20_DestTable_ETLRow_Cover (LOW RISK, REVERSIBLE)
B. Split UNION ALL in worker code (MED RISK, requires deploy)
C. Reduce page size (HIGH RISK, requires migration restart)

### Recommendation
Option A — covering index with ONLINE=ON. Query time <50ms post-index.

### RFC
[RFC-001-keymap20-index](link)
```

## Related Skills

- `stack-pr` — Create stacked GitHub PRs (integration)
- `bmad-quick-dev` — Development workflow (for post-investigation code changes)
- `autoresearch` — Research agent (for pattern lookups during RCA)

---

**Created for:** auc-conversion production monitoring  
**Team:** 4-agent orchestration with read-only enforcement  
**Change Vector:** GitHub PR-stacked RFC/ADR only  
**Token Governance:** Structured agent outputs, cost-optimized polling
