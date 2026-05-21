---
name: watchdog-remediate
description: "Execute a pre-approved watchdog remediation playbook against auc-conversion. Takes
  a playbook type as argument: circuit-breaker | timeout-extend | stale-pods | db-locks.
  Records action taken and verifies outcome. Called by migration-watchdog-auto on FAILURE."
version: 1.0
triggers:
  - "/watchdog-remediate"
---

# Watchdog Remediate

Executes one of four pre-approved remediation playbooks. Each playbook verifies preconditions,
applies the fix, and confirms the result. Never applies without checking preconditions first.

## Usage

```
/watchdog-remediate <type>
```

Where `<type>` is one of: `circuit-breaker`, `timeout-extend`, `stale-pods`, `db-locks`

If called without an argument, print the available playbooks and their trigger conditions.

---

## Playbook: circuit-breaker

**Trigger condition:** App logs show circuit breaker open OR CrashLoopBackOff with connection errors.

**Preconditions (check before acting):**
```bash
# 1. Confirm circuit breaker is actually open (not a transient log line)
kubectl logs -n auc-conversion deploy/auc-conversion --since=5m 2>/dev/null \
  | grep -i "circuit breaker" | tail -5

# 2. Confirm deployment exists and is not already being rolled
kubectl rollout status deploy/auc-conversion -n auc-conversion --timeout=5s 2>/dev/null
```

If circuit breaker log is NOT present or rollout is in progress → abort, escalate to user.

**Action:**
```bash
# Restart the deployment (triggers pod recreation, clears in-memory circuit breaker state)
kubectl rollout restart deploy/auc-conversion -n auc-conversion

# Wait for rollout to complete (max 3 min)
kubectl rollout status deploy/auc-conversion -n auc-conversion --timeout=180s
```

**Verification:**
```bash
# Check pods are Running and logs show no circuit breaker errors for 60s
sleep 60
kubectl get pods -n auc-conversion
kubectl logs -n auc-conversion deploy/auc-conversion --since=1m 2>/dev/null \
  | grep -i "circuit breaker" | wc -l
# Expect: 0 circuit breaker errors
```

**Report:**
```
REMEDIATION: circuit-breaker
APPLIED: kubectl rollout restart deploy/auc-conversion
RESULT: OK|FAILED
NOTES: <rollout output, pod count after, error count>
```

---

## Playbook: timeout-extend

**Trigger condition:** Migration job shows timeout error or job is approaching its deadline.

**Preconditions:**
```bash
# Find the active job and its current timeout
JOB=$(kubectl get jobs -n auc-conversion --field-selector=status.active=1 \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
CURRENT_DEADLINE=$(kubectl get job "$JOB" -n auc-conversion \
  -o jsonpath='{.spec.activeDeadlineSeconds}' 2>/dev/null)
echo "Job: $JOB, deadline: ${CURRENT_DEADLINE}s"
```

If no active job found → abort, escalate.
If deadline is already >7200s (2hr) → abort, escalate (manual investigation needed).

**Action:**
```bash
# Patch job to extend deadline by 3600s (1 hour)
NEW_DEADLINE=$((CURRENT_DEADLINE + 3600))
kubectl patch job "$JOB" -n auc-conversion \
  --type='merge' \
  -p "{\"spec\":{\"activeDeadlineSeconds\":${NEW_DEADLINE}}}"
```

**Verification:**
```bash
kubectl get job "$JOB" -n auc-conversion \
  -o jsonpath='{.spec.activeDeadlineSeconds}'
# Expect: NEW_DEADLINE
```

**Report:**
```
REMEDIATION: timeout-extend
JOB: <job-name>
PRIOR_DEADLINE: <seconds>
NEW_DEADLINE: <seconds>
RESULT: OK|FAILED
```

---

## Playbook: stale-pods

**Trigger condition:** Pods in Error or CrashLoopBackOff state — typically after a failed init
container or OOM kill that left stale pod objects.

**Preconditions:**
```bash
# List stale pods — only target Error and CrashLoopBackOff, NOT Running/Pending
STALE=$(kubectl get pods -n auc-conversion \
  --field-selector='status.phase=Failed' \
  -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)
CRASHLOOP=$(kubectl get pods -n auc-conversion \
  -o jsonpath='{range .items[?(@.status.containerStatuses[0].state.waiting.reason=="CrashLoopBackOff")]}{.metadata.name}{" "}{end}' 2>/dev/null)
echo "Stale: $STALE | CrashLoop: $CRASHLOOP"
```

If no stale pods → abort (false alarm, state may have changed).
If stale pod count > 5 → escalate (unusual — may indicate systemic issue).

**Action:**
```bash
# Delete only the stale pods — Running pods are untouched
for pod in $STALE $CRASHLOOP; do
  kubectl delete pod "$pod" -n auc-conversion --grace-period=30 2>/dev/null || true
done
```

**Verification:**
```bash
sleep 30
kubectl get pods -n auc-conversion
# Expect: no pods in Error/CrashLoopBackOff
```

**Report:**
```
REMEDIATION: stale-pods
DELETED: <pod names>
RESULT: OK|FAILED
NOTES: <pod count before/after>
```

---

## Playbook: db-locks

**Trigger condition:** DB agent detected blocking lock chain >10min with idle holder.

**Preconditions (strict — DB writes are risky):**
```bash
# Identify the blocking query — must be idle and >10min
# Run via whatever DB access method is available (psql, kubectl exec into DB pod, etc.)
SELECT pid, state, wait_event_type, query_start,
       now() - query_start AS duration, left(query, 100) AS query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND now() - query_start > interval '10 minutes'
ORDER BY duration DESC;
```

**ONLY proceed if:**
1. The holder process is `idle in transaction` (not actively running)
2. Duration is >10 minutes (not a transient lock)
3. There is a confirmed blocking chain (not just a slow query)

If any condition fails → abort, escalate.

**Action:**
```bash
# Terminate only the idle holder (pg_terminate_backend, not pg_cancel_backend)
# pg_terminate_backend sends SIGTERM — the transaction rolls back cleanly
SELECT pg_terminate_backend(<pid>);
```

**Verification:**
```bash
# Confirm blocking chain is cleared
SELECT COUNT(*) FROM pg_locks WHERE NOT granted;
# Expect: 0 or significantly reduced
```

**Report:**
```
REMEDIATION: db-locks
TERMINATED_PID: <pid>
BLOCKER_DURATION: <duration>
BLOCKER_QUERY: <first 100 chars>
RESULT: OK|FAILED
NOTES: <lock count before/after>
```

---

## Escalation

If any playbook's precondition check fails, or if the action fails, or if verification shows
the problem persists after remediation:

1. Do NOT retry the same playbook
2. Send `PushNotification`: "🚨 watchdog-remediate/<type> FAILED — manual intervention required. <reason>"
3. Write failure details to `plans/watchdog-incidents.md`
4. Exit

Never apply a playbook more than once per incident (the `consecutive_failures` counter in state
prevents repeated auto-remediation on the same failure).
