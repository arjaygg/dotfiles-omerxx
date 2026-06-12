---
name: migration-watchdog-auto
description: "Autonomous per-tick execution of the migration watchdog. Reads prior state, gates on
  active migration, dispatches 4 parallel subagents (K8s/DB/logs/metrics), classifies result, and
  routes: HEALTHY=silent, DEGRADED=notify, FAILURE=remediate or escalate. Designed to be invoked by
  CronCreate every 15 minutes. Do NOT call manually — use /migration-watchdog for on-demand checks."
version: 1.0
disable-model-invocation: true
triggers:
  - "/migration-watchdog-auto"
---

# Migration Watchdog — Autonomous Tick

This skill runs each CronCreate tick. It is stateful — reads prior state, compares, and writes
updated state. Silent when everything is healthy.

## State File

State lives at `~/.claude/watchdog/auc-conversion.json`. Create it on first run if absent.

Schema:
```json
{
  "last_run": "ISO8601",
  "release": "v1.0.XXX or unknown",
  "overall": "HEALTHY|DEGRADED|FAILURE|UNKNOWN",
  "k8s":     { "status": "OK|WARN|FAIL", "summary": "..." },
  "db":      { "status": "OK|WARN|FAIL", "migration_tier": 0, "summary": "..." },
  "logs":    { "status": "OK|WARN|FAIL", "anomalies": [] },
  "metrics": { "status": "OK|WARN|FAIL", "summary": "..." },
  "remediation_applied": null,
  "escalated": false,
  "consecutive_failures": 0
}
```

## Step 1 — Read prior state

```bash
STATE_FILE="$HOME/.claude/watchdog/auc-conversion.json"
mkdir -p "$HOME/.claude/watchdog"
if [[ -f "$STATE_FILE" ]]; then
  PRIOR=$(cat "$STATE_FILE")
  PRIOR_OVERALL=$(echo "$PRIOR" | jq -r '.overall // "UNKNOWN"')
  PRIOR_FAILURES=$(echo "$PRIOR" | jq -r '.consecutive_failures // 0')
else
  PRIOR_OVERALL="UNKNOWN"
  PRIOR_FAILURES=0
fi
```

## Step 2 — Migration window gate

Only run full watchdog if a migration job is actively running. Exit silently otherwise to avoid
noisy polling when idle.

```bash
ACTIVE_JOBS=$(kubectl get jobs -n auc-conversion \
  --field-selector=status.active=1 \
  -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")

if [[ -z "$ACTIVE_JOBS" ]]; then
  # No active migration — check if pods are healthy (brief check)
  UNHEALTHY=$(kubectl get pods -n auc-conversion \
    --field-selector='status.phase!=Running,status.phase!=Succeeded' \
    -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
  if [[ -z "$UNHEALTHY" ]]; then
    # All quiet — update state timestamp, exit silently
    echo "$PRIOR" | jq --arg t "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      '.last_run = $t | .overall = "HEALTHY"' > "$STATE_FILE" 2>/dev/null || true
    exit 0
  fi
fi
```

## Step 3 — Dispatch 4 parallel subagents

Launch all four with `Bash(run_in_background: true)`. Write each result to a temp file, then read
all four after they complete.

**K8s agent** → writes to `/tmp/wdog-k8s.json`:
```
Check K8s health for auc-conversion namespace and write JSON to /tmp/wdog-k8s.json:
{
  "status": "OK|WARN|FAIL",
  "summary": "<one line>",
  "details": "<pod list, recent events, rollout status>",
  "anomalies": ["<list of specific problems found, empty array if none>"]
}

Commands to run:
  kubectl get pods -n auc-conversion -o wide
  kubectl get events -n auc-conversion --sort-by=.lastTimestamp | tail -20
  kubectl get jobs -n auc-conversion | grep -v Completed
  kubectl rollout status deploy -n auc-conversion --timeout=10s

Rules:
- FAIL if any pod is CrashLoopBackOff, OOMKilled, or Error
- WARN if any pod is Pending >2min or Init:Error
- OK otherwise
```

**DB agent** → writes to `/tmp/wdog-db.json`:
```
Check auc-conversion DB migration state and write JSON to /tmp/wdog-db.json:
{
  "status": "OK|WARN|FAIL",
  "migration_tier": <integer or null>,
  "summary": "<one line>",
  "details": "<migration state, row counts, lock info>",
  "anomalies": ["<list>"]
}

Check:
- Current migration tier/version from migrations tracking table
- pg_stat_activity for long-running queries (>5min) or CREATE INDEX
- pg_locks for blocking chains
- Any DEADLOCK in recent pg_log entries if accessible

Rules:
- FAIL if blocking lock chain >10min or deadlock detected
- WARN if CREATE INDEX running >90min or query >10min
- OK otherwise
```

**Logs agent** → writes to `/tmp/wdog-logs.json`:
```
Stream recent auc-conversion app logs and write JSON to /tmp/wdog-logs.json:
{
  "status": "OK|WARN|FAIL",
  "summary": "<one line>",
  "anomalies": ["<up to 5 significant lines>"],
  "error_count": <integer>,
  "panic_count": <integer>
}

Commands:
  kubectl logs -n auc-conversion deploy/auc-conversion --since=20m --tail=300 2>/dev/null

Filter for: ERROR, FATAL, panic, circuit breaker, PK violation, INT overflow,
            timeout, failed, OOM, connection refused

Rules:
- FAIL if panic or circuit breaker open or >10 ERRORs in window
- WARN if 1-10 ERRORs or repeated timeouts
- OK otherwise
```

**Metrics agent** → writes to `/tmp/wdog-metrics.json`:
```
Check auc-conversion resource usage and write JSON to /tmp/wdog-metrics.json:
{
  "status": "OK|WARN|FAIL",
  "summary": "<one line>",
  "details": "<CPU, memory, throughput if available>",
  "anomalies": ["<list>"]
}

Commands:
  kubectl top pods -n auc-conversion 2>/dev/null
  kubectl top nodes 2>/dev/null | head -5

Rules:
- FAIL if any pod >95% memory limit (OOM risk)
- WARN if any pod >80% memory or CPU throttling detected
- OK otherwise
```

Wait for all 4 to complete (poll `/tmp/wdog-*.json` existence, timeout 120s), then read results.

## Step 4 — Synthesize and classify

```bash
K8S=$(cat /tmp/wdog-k8s.json 2>/dev/null || echo '{"status":"FAIL","summary":"agent timeout"}')
DB=$(cat /tmp/wdog-db.json 2>/dev/null || echo '{"status":"FAIL","summary":"agent timeout"}')
LOGS=$(cat /tmp/wdog-logs.json 2>/dev/null || echo '{"status":"FAIL","summary":"agent timeout"}')
METRICS=$(cat /tmp/wdog-metrics.json 2>/dev/null || echo '{"status":"FAIL","summary":"agent timeout"}')

K8S_STATUS=$(echo "$K8S" | jq -r '.status')
DB_STATUS=$(echo "$DB" | jq -r '.status')
LOG_STATUS=$(echo "$LOGS" | jq -r '.status')
MET_STATUS=$(echo "$METRICS" | jq -r '.status')

# Overall classification
if [[ "$K8S_STATUS" == "FAIL" || "$DB_STATUS" == "FAIL" || "$LOG_STATUS" == "FAIL" ]]; then
  OVERALL="FAILURE"
elif [[ "$K8S_STATUS" == "WARN" || "$DB_STATUS" == "WARN" || "$LOG_STATUS" == "WARN" || "$MET_STATUS" == "WARN" ]]; then
  OVERALL="DEGRADED"
else
  OVERALL="HEALTHY"
fi

NEW_FAILURES=0
[[ "$OVERALL" == "FAILURE" ]] && NEW_FAILURES=$((PRIOR_FAILURES + 1))
```

## Step 5 — Route by classification

**HEALTHY:**
- Write state with `overall: HEALTHY`, `consecutive_failures: 0`
- Exit silently — no notification, no output

**DEGRADED:**
- Write state with `overall: DEGRADED`
- Append entry to `plans/watchdog-incidents.md`
- Send `PushNotification`: "⚠️ auc-conversion DEGRADED — <summary>"
- Do NOT attempt remediation

**FAILURE (consecutive_failures < 2):**
- Write state
- Determine remediation type from anomalies:
  - Pod CrashLoop/Error → `circuit-breaker` playbook via `/watchdog-remediate circuit-breaker`
  - DB lock chain → `db-locks` playbook
  - OOM risk → `stale-pods` playbook
  - Job timeout → `timeout-extend` playbook
  - Unknown/multi-cause → skip to escalation
- Invoke remediation skill: `Agent(subagent_type: null, prompt: "/watchdog-remediate <type>")`
- Record `remediation_applied` in state

**FAILURE (consecutive_failures >= 2 OR unknown cause):**
- Write state with `escalated: true`
- Send `PushNotification`: "🚨 auc-conversion FAILURE (${NEW_FAILURES}× consecutive) — <summary> — manual intervention required"
- Write detailed incident to `plans/watchdog-incidents.md`

## Step 6 — Write state

```bash
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
RELEASE=$(kubectl get deploy -n auc-conversion \
  -o jsonpath='{.items[0].spec.template.spec.containers[0].image}' 2>/dev/null \
  | sed 's/.*://') || RELEASE="unknown"

jq -n \
  --arg ts "$NOW" \
  --arg rel "$RELEASE" \
  --arg overall "$OVERALL" \
  --argjson k8s "$K8S" \
  --argjson db "$DB" \
  --argjson logs "$LOGS" \
  --argjson metrics "$METRICS" \
  --argjson failures "$NEW_FAILURES" \
  '{
    last_run: $ts,
    release: $rel,
    overall: $overall,
    k8s: $k8s,
    db: $db,
    logs: $logs,
    metrics: $metrics,
    remediation_applied: null,
    escalated: false,
    consecutive_failures: $failures
  }' > "$STATE_FILE"

# Clean up temp files
rm -f /tmp/wdog-k8s.json /tmp/wdog-db.json /tmp/wdog-logs.json /tmp/wdog-metrics.json
```

## Incident Log Format

Append to `plans/watchdog-incidents.md` (create if absent):

```markdown
## <ISO8601 timestamp> — <OVERALL>

**Release:** <version>
**Signals:**
| Source  | Status | Finding |
|---------|--------|---------|
| K8s     | <status> | <summary> |
| DB      | <status> | <summary> |
| Logs    | <status> | <summary> |
| Metrics | <status> | <summary> |

**Remediation:** <applied playbook or "escalated to user">
**Consecutive failures:** <N>
```
