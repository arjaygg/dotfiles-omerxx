---
name: ci-watch
description: "Fire-and-forget CI monitor. Uses a background shell poller (zero LLM tokens while running) that watches GitHub Actions and writes status to plans/ci-status.md. Returns within 5 seconds. On green: deploys to DEV and sends a macOS notification. On failure: sends alert. Check status with /ci-status."
version: 2.0
triggers:
  - "/ci-watch"
---

# CI Watch Skill

Launches a background shell polling loop to monitor CI for the current PR. Returns immediately
— the loop runs independently and writes results to `plans/ci-status.md`. No LLM turns are
consumed while CI is running (Monitor fires only on change).

## Instructions

### Step 1 — Detect current PR

```bash
BRANCH=$(git branch --show-current)
PR_NUMBER=$(gh pr view --json number --jq '.number' 2>/dev/null || echo "")
REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null || echo "")
```

If no PR found, tell the user and stop.

### Step 2 — Write initial status

Write to `plans/ci-status.md`:

```
# CI Watch Status

**PR:** #<PR_NUMBER> — <BRANCH>
**Repo:** <REPO>
**Started:** <timestamp>
**Status:** WATCHING — background shell poller running
```

### Step 3 — Launch background shell poller

Use `Bash` with `run_in_background: true`. The poller uses a poll-and-diff loop (zero tokens
while silent; writes to `plans/ci-status.md` only on state change).

```bash
PR_NUM="<set from Step 1>"
REPO_SLUG="<set from Step 1>"
BRANCH_NAME="<set from Step 1>"
STATUS_FILE="$(pwd)/plans/ci-status.md"
LOG_FILE="/tmp/ci-watch-${PR_NUM}.log"
MAX_POLLS=30   # 30 × 30s = 15 min

mkdir -p "$(pwd)/plans"

LAST=""
POLL=0
while [ "$POLL" -lt "$MAX_POLLS" ]; do
  POLL=$(( POLL + 1 ))
  TS=$(date '+%Y-%m-%d %H:%M:%S')

  NOW=$(gh run list \
    --repo "${REPO_SLUG}" \
    --branch "${BRANCH_NAME}" \
    --limit 3 \
    --json databaseId,status,conclusion,url \
    --jq '.[] | "\(.databaseId)|\(.status)|\(.conclusion)|\(.url)"' \
    2>/dev/null || echo "")

  if [ "$NOW" != "$LAST" ] && [ -n "$NOW" ]; then
    LAST="$NOW"

    # Parse first run's conclusion
    FIRST=$(echo "$NOW" | head -1)
    RUN_STATUS=$(echo "$FIRST" | cut -d'|' -f2)
    RUN_CONCLUSION=$(echo "$FIRST" | cut -d'|' -f3)
    RUN_URL=$(echo "$FIRST" | cut -d'|' -f4)

    cat > "$STATUS_FILE" <<STATUSEOF
# CI Watch Status

**PR:** #${PR_NUM} — ${BRANCH_NAME}
**Repo:** ${REPO_SLUG}
**Last checked:** ${TS} (poll ${POLL}/${MAX_POLLS})
**Run status:** ${RUN_STATUS} | ${RUN_CONCLUSION}
**URL:** ${RUN_URL}
STATUSEOF

    if [ "$RUN_CONCLUSION" = "success" ]; then
      echo "${TS} [SUCCESS] ${RUN_URL}" >> "$LOG_FILE"
      # Trigger DEV deploy if workflow exists
      gh workflow run deploy-dev.yml --repo "${REPO_SLUG}" >/dev/null 2>&1 || true
      osascript -e "display notification \"CI passed — DEV deploy triggered\" with title \"ci-watch PR #${PR_NUM}\"" 2>/dev/null || true
      echo "**Status:** SUCCESS" >> "$STATUS_FILE"
      exit 0
    elif [ "$RUN_CONCLUSION" = "failure" ] || [ "$RUN_CONCLUSION" = "cancelled" ]; then
      echo "${TS} [${RUN_CONCLUSION^^}] ${RUN_URL}" >> "$LOG_FILE"
      osascript -e "display notification \"CI ${RUN_CONCLUSION} on ${BRANCH_NAME}\" with title \"ci-watch PR #${PR_NUM}\" sound name \"Basso\"" 2>/dev/null || true
      echo "**Status:** FAILED — see ${RUN_URL}" >> "$STATUS_FILE"
      exit 0
    fi
  fi

  sleep 30
done

# Timeout
TS=$(date '+%Y-%m-%d %H:%M:%S')
echo "**Status:** TIMEOUT — ${MAX_POLLS} polls elapsed with no conclusion. Last: ${LAST}" >> "$STATUS_FILE"
osascript -e "display notification \"CI watch timed out for PR #${PR_NUM}\" with title \"ci-watch\"" 2>/dev/null || true
```

### Step 4 — Optionally set up Monitor for in-session notification

If the user is actively working in this session and wants a notification when CI completes,
start a Monitor watch on `plans/ci-status.md`:

```
Monitor: tail -f plans/ci-status.md | grep --line-buffered -E "(SUCCESS|FAILED|TIMEOUT)"
persistent: false
timeout_ms: 900000
```

This costs zero tokens while silent, and fires a notification in-session when the poller
writes a final status line.

### Step 5 — Report to user

```
CI watch started for PR #<PR_NUMBER> (<BRANCH>).
Status file: plans/ci-status.md
Log: /tmp/ci-watch-<PR_NUMBER>.log
Check anytime with /ci-status
```

Return immediately.

## Related

- `/ci-status` — read current ci-status.md
- `/ci-monitor` — cicd-monitor agent with webhook support (for complex pipelines)
- Monitor patterns: `/monitor-patterns` skill (`ai/skills/monitor-patterns/SKILL.md`)
