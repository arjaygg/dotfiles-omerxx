---
name: auc-prod-db-monitor
description: "Fire-and-forget 8-year autonomous AUC PROD DB smart monitor. Launches a headless background Claude Code agent that progressively polls the PROD DB for missing index bottlenecks, auto-fixes them safely, and creates GH Issues/PRs."
version: 1.0
triggers:
  - "/auc-prod-db-monitor"
  - "continue to monitor the auc prod db"
  - "start db monitor"
---

# AUC PROD DB Smart Monitor

Launches a background headless Claude Code agent to progressively monitor the AUC PROD DB over an 8-year lifecycle. Returns immediately — the agent runs independently and writes status to `plans/db-monitor-status.md`.

## Instructions

### Step 1 — Verify Environment

Ensure the user is in the correct working directory (`auc-deployment-manifest`) and the `gh` CLI is authenticated, as the background agent will need to create issues and pull requests.

### Step 2 — Launch the Background Agent

Use `Bash` to execute the native `start-db-monitor.sh` launcher script in the background. If the script doesn't exist, create it.

```bash
cat << 'EOF' > scripts/start-db-monitor.sh
#!/usr/bin/env bash

# AUC PROD DB Smart Monitor - Native Claude Code Background Primitive
set -euo pipefail

LOG_FILE="/tmp/auc-prod-db-monitor.log"
STATUS_FILE="$(pwd)/plans/db-monitor-status.md"

echo "Starting native Claude Code DB monitor (8-Year Strategy)..." > "$LOG_FILE"
echo "PID: $$" >> "$LOG_FILE"
mkdir -p plans/db-bottlenecks

cat << 'STAT' > "$STATUS_FILE"
# AUC PROD DB Smart Monitor Status
**Started:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
**Status:** WATCHING — background agent loop running
**Next Check:** Imminent
STAT

(
  # 8 years in seconds = 8 * 365 * 24 * 3600 = 252288000
  END_TIME=$(( $(date +%s) + 252288000 ))
  CHECK_INTERVAL=3600 # 1 hour
  
  while [ $(date +%s) -lt $END_TIME ]; do
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Launching Claude Code agent for DB bottleneck check..." >> "$LOG_FILE"
    
    # Launch fresh headless Claude Code primitive
    claude -p "You are an autonomous DB Admin agent tasked with progressive monitoring of the AUC PROD DB.
    
    INSTRUCTIONS:
    1. Query the PROD SQL Server database using 'sqlcmd' to find missing index bottlenecks. 
       Query condition: sys.dm_db_missing_index_group_stats where avg_user_impact >= 80 and user_seeks >= 1000.
    2. If a bottleneck is found:
       - Execute the index creation query on PROD safely. ONLY 'WITH (ONLINE = ON)' index creations are allowed. NO OTHER DB OPERATIONS ARE ALLOWED (strict rule).
       - Use 'gh issue create' to create a GitHub issue.
       - Use 'gh pr create' to document the bottleneck comprehensively in a fork/branch of GH PR.
    3. If no bottlenecks are found, report DB healthy.
    4. Update 'plans/db-monitor-status.md' with the outcome.
    
    Act autonomously and exit.
    " --allowedTools "Bash,Read,Write" >> "$LOG_FILE" 2>&1 || true
    
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Claude agent check complete. Sleeping for $CHECK_INTERVAL seconds." >> "$LOG_FILE"
    
    sleep $CHECK_INTERVAL
  done
  
  echo "8-Year monitoring period complete." >> "$LOG_FILE"
) &

echo "Headless Claude Code DB monitor started in the background (PID: $!)."
echo "Check progress in plans/db-monitor-status.md and /tmp/auc-prod-db-monitor.log"
EOF

chmod +x scripts/start-db-monitor.sh
./scripts/start-db-monitor.sh
```

### Step 3 — Report to User

After launching, immediately tell the user:

```
DB Smart Monitor started (8-Year loop).
Status file: plans/db-monitor-status.md
Log: /tmp/auc-prod-db-monitor.log
```
Return immediately — do not wait. The Claude primitive handles it all autonomously.
