---
name: watchdog-cron-setup
description: "One-time setup: initialize watchdog state file and register a durable CronCreate job
  that runs /migration-watchdog-auto every 15 minutes. Use /watchdog-cron-teardown to stop it.
  Job auto-expires after 7 days — re-run this skill to renew. Requires active Claude session."
version: 1.0
disable-model-invocation: true
triggers:
  - "/watchdog-cron-setup"
---

# Watchdog Cron Setup

One-time setup skill. Run once to activate autonomous migration monitoring. Re-run to renew
the 7-day window.

## Important constraints

- **Session-scoped:** The cron fires only while this Claude session is active/idle. If the
  session ends, the job pauses until Claude restarts (if `durable: true`, it resumes).
- **7-day auto-expiry:** CronCreate jobs auto-delete after 7 days. Re-run `/watchdog-cron-setup`
  weekly to keep monitoring active.
- **kubectl access required:** The watchdog needs live cluster access. Run `kubectl config
  get-contexts` to confirm the right context is active before setting up.

## Step 1 — Verify prerequisites

```bash
# Confirm kubectl points to the right cluster
kubectl config current-context
kubectl auth can-i get pods -n auc-conversion --request-timeout=5s

# Confirm state dir exists
mkdir -p "$HOME/.claude/watchdog"
```

If kubectl auth fails → stop and tell user: "Fix kubectl context first. Run:
`kubectl config use-context <context-name>`"

## Step 2 — Initialize state file

Write initial state to `~/.claude/watchdog/auc-conversion.json` if not already present:

```bash
STATE_FILE="$HOME/.claude/watchdog/auc-conversion.json"
if [[ ! -f "$STATE_FILE" ]]; then
  cat > "$STATE_FILE" <<'EOF'
{
  "last_run": null,
  "release": "unknown",
  "overall": "UNKNOWN",
  "k8s":     { "status": "UNKNOWN", "summary": "not yet checked" },
  "db":      { "status": "UNKNOWN", "migration_tier": null, "summary": "not yet checked" },
  "logs":    { "status": "UNKNOWN", "anomalies": [] },
  "metrics": { "status": "UNKNOWN", "summary": "not yet checked" },
  "remediation_applied": null,
  "escalated": false,
  "consecutive_failures": 0
}
EOF
  echo "State file initialized at $STATE_FILE"
else
  echo "State file already exists — preserving prior state"
  cat "$STATE_FILE" | jq '{overall:.overall, last_run:.last_run, failures:.consecutive_failures}'
fi
```

## Step 3 — Register the cron job

Use `CronCreate` with these exact parameters:

```
CronCreate(
  cron: "7,22,37,52 * * * *",   # every 15 min, offset to avoid :00/:30 crowding
  prompt: "/migration-watchdog-auto",
  recurring: true,
  durable: true                  # survives Claude restarts
)
```

Capture the returned job ID and report it to the user.

## Step 4 — Run an immediate first tick

After registering the cron, run the watchdog once immediately to confirm it works:

```
Invoke /migration-watchdog-auto now (first manual tick to verify setup).
```

## Step 5 — Report to user

```
✅ Autonomous watchdog active

Schedule:    every 15 min (7, 22, 37, 52 past the hour)
State file:  ~/.claude/watchdog/auc-conversion.json
Incidents:   plans/watchdog-incidents.md (created on first DEGRADED/FAILURE)
Cron job ID: <id from CronCreate>
Auto-expires: 7 days from now — re-run /watchdog-cron-setup to renew

Behaviour:
  HEALTHY  → silent (no notification)
  DEGRADED → PushNotification + incident log entry
  FAILURE  → auto-remediate (if known cause) OR PushNotification + escalate

To stop: CronDelete(<job-id>)
To check state: cat ~/.claude/watchdog/auc-conversion.json | jq .
```

---

## Teardown

To stop the watchdog:

1. Run `CronList` to find the job ID (look for prompt containing "migration-watchdog-auto")
2. Run `CronDelete(<job-id>)`
3. Optionally archive state: `cp ~/.claude/watchdog/auc-conversion.json ~/.claude/watchdog/auc-conversion-$(date +%Y%m%d).json`
