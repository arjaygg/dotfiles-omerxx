---
name: ci-watch
description: "Fire-and-forget CI monitor. Uses a background shell poller (zero LLM tokens while running) that watches GitHub Actions and writes status to plans/ci-status.md. Returns within 5 seconds. On completion: sends a macOS notification. Check status with /ci-status."
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
HEAD_SHA=$(git rev-parse HEAD)
```

If no PR found, tell the user and stop.

`HEAD_SHA` is the commit the poller must track — CI runs are filtered to this SHA in Step 3 so
a stale run from an earlier push on the same branch can never produce the verdict.

### Step 2 — Write initial status

Write to `plans/ci-status.md`:

```
# CI Watch Status

**PR:** #<PR_NUMBER> — <BRANCH>
**Repo:** <REPO>
**SHA:** <HEAD_SHA>
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
HEAD_SHA="<set from Step 1>"
STATUS_FILE="$(pwd)/plans/ci-status.md"
LOG_FILE="/tmp/ci-watch-${PR_NUM}.log"
MAX_POLLS=30   # 30 × 30s = 15 min

mkdir -p "$(pwd)/plans"

LAST=""
POLL=0
while [ "$POLL" -lt "$MAX_POLLS" ]; do
  POLL=$(( POLL + 1 ))
  TS=$(date '+%Y-%m-%d %H:%M:%S')

  # Filtering to HEAD_SHA is load-bearing: without it, a stale run from an earlier
  # push on the same branch can outrank the real run and produce a false verdict.
  #
  # `gh`'s built-in --jq takes an expression only — it has NO --arg flag — so the
  # SHA is bound by piping gh's JSON into real jq. Passing `--arg` to gh fails with
  # `unknown command "sha" for "gh run list"`.
  RAW=$(gh run list \
    --repo "${REPO_SLUG}" \
    --branch "${BRANCH_NAME}" \
    --limit 5 \
    --json databaseId,status,conclusion,url,headSha 2>>"$LOG_FILE")
  GH_RC=$?

  if [ "$GH_RC" -ne 0 ]; then
    # A failed query must not be indistinguishable from "no run yet" — otherwise a
    # broken command spins for the full MAX_POLLS and reports a bare timeout with
    # no cause. Record it and keep polling in case it is transient.
    echo "${TS} [gh-error rc=${GH_RC}] poll ${POLL}; see stderr above" >> "$LOG_FILE"
    sleep 30
    continue
  fi

  NOW=$(printf '%s' "$RAW" | jq -r --arg sha "${HEAD_SHA}" \
    '.[] | select(.headSha == $sha) | "\(.databaseId)|\(.status)|\(.conclusion)|\(.url)"' \
    2>>"$LOG_FILE")

  if [ -z "$NOW" ]; then
    # No run for this exact commit yet (queued or not created) — keep polling
    # rather than verdicting on another commit's run.
    sleep 30
    continue
  fi

  if [ "$NOW" != "$LAST" ]; then
    LAST="$NOW"

    # Parse this commit's run (only one run should match HEAD_SHA per workflow)
    FIRST=$(echo "$NOW" | head -1)
    RUN_STATUS=$(echo "$FIRST" | cut -d'|' -f2)
    RUN_CONCLUSION=$(echo "$FIRST" | cut -d'|' -f3)
    RUN_URL=$(echo "$FIRST" | cut -d'|' -f4)

    cat > "$STATUS_FILE" <<STATUSEOF
# CI Watch Status

**PR:** #${PR_NUM} — ${BRANCH_NAME}
**Repo:** ${REPO_SLUG}
**SHA:** ${HEAD_SHA}
**Last checked:** ${TS} (poll ${POLL}/${MAX_POLLS})
**Run status:** ${RUN_STATUS} | ${RUN_CONCLUSION}
**URL:** ${RUN_URL}
STATUSEOF

    if [ "$RUN_CONCLUSION" = "success" ]; then
      echo "${TS} [SUCCESS] ${RUN_URL}" >> "$LOG_FILE"
      osascript -e "display notification \"CI passed\" with title \"ci-watch PR #${PR_NUM}\"" 2>/dev/null || true
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
- Monitor patterns: `ai/skills/monitor-patterns/SKILL.md` (read directly — the `/monitor-patterns`
  skill is currently disabled via `skillOverrides`)


## Polling Budget & Escalation

**Rule:** never poll CI synchronously from the main session. Polling belongs in a background
watcher (this skill's poller, or `Monitor`), never in a foreground `sleep`/`gh run list` loop —
each foreground check costs ~200 tokens and blocks the session.

| Context | Cadence |
|---|---|
| Background poller (this skill) | 30s (default `POLL_INTERVAL`) — cheap, no LLM turn per tick |
| Manual/foreground check, if unavoidable | at most once per 60s |
| Manual checks with no state change | stop after 3 consecutive unchanged polls and report status — there is no new information to gain |

These are not in conflict: the 30s cadence is the background shell loop, the 60s floor and the
3-strike stop apply only to checks that consume an LLM turn.

**Retry/escalation:**
1. Transient failures (runner lost, network) → the poller retries within `MAX_POLLS`.
2. Real failure → notify once with the failing job name; do not re-run automatically unless asked.
3. `MAX_POLLS` exhausted → report "still running, watcher timed out", do not silently drop it.

**Workflow rule:** after pushing a branch, invoke `/ci-watch <PR_NUMBER>` and immediately continue
to the next task. Do not enter a polling loop; do not call `gh run list` in a sleep loop.
