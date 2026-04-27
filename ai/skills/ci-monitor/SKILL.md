---
name: ci-monitor
description: "Self-healing CI/CD monitor for any GitHub repo. Uses the Monitor tool to stream GitHub Actions events
  in real-time — zero tokens when silent, notifications only on status changes. Classifies
  failures with LogSage/RFM, auto-retries HIGH, escalates CRITICAL. Repo auto-detected from git remote.
  10-20x cheaper than poll-agent approach. Invoke via /ci-monitor."
version: 4.0
triggers:
  - "/ci-monitor"
  - "/monitor-ci"
---

# CI Monitor Skill

Event-driven CI watcher for any GitHub repository. Uses the `Monitor` tool to stream GitHub Actions status changes
directly into your session — no background agent required for observation.

Auto-detects repo from `git remote`; no hardcoding required.

## Instructions

### Step 1 — Detect repo and bootstrap memory file

```bash
REPO=$(git remote get-url origin | sed 's|.*github\.com[/:]||;s|\.git$||')
ACTED_FILE="${HOME}/.dotfiles/.serena/memories/cicd-acted-runs.md"

# Create memory file if absent
mkdir -p "$(dirname "$ACTED_FILE")"
if [ ! -f "$ACTED_FILE" ]; then
  cat > "$ACTED_FILE" <<'EOF'
# CICD Acted Runs

Tracks CI runs that have been processed to avoid duplicate handling.

---

(none yet)
EOF
fi
```

### Step 2 — Call Monitor tool

**description:** `"GitHub Actions on <REPO>"`

**persistent:** `true`

**command:**
```bash
REPO="<REPO>"
ACTED_FILE="${HOME}/.dotfiles/.serena/memories/cicd-acted-runs.md"
LAST_SNAPSHOT=""

while true; do
  SNAPSHOT=$(gh run list \
    --repo "$REPO" \
    --limit 10 \
    --json databaseId,name,status,conclusion,headBranch \
    --jq '.[] | "\(.databaseId)|\(.headBranch)|\(.status)|\(.conclusion)"' \
    2>/dev/null || echo "")

  if [ "$SNAPSHOT" != "$LAST_SNAPSHOT" ] && [ -n "$SNAPSHOT" ]; then
    NEW_EVENTS=$(diff <(echo "$LAST_SNAPSHOT") <(echo "$SNAPSHOT") 2>/dev/null \
      | grep "^>" | sed 's/^> //' \
      | grep --line-buffered "completed" || true)

    if [ -n "$NEW_EVENTS" ]; then
      echo "$NEW_EVENTS" | while IFS='|' read -r run_id branch run_status conclusion; do
        if grep -q "$run_id" "$ACTED_FILE" 2>/dev/null; then
          continue
        fi
        echo "RUN_COMPLETE run_id=$run_id branch=$branch conclusion=$conclusion"
      done
    fi
    LAST_SNAPSHOT="$SNAPSHOT"
  fi
  sleep 30
done
```

## Reacting to Monitor Events

When a `RUN_COMPLETE` notification arrives:

### Parse
Extract `run_id`, `branch`, `conclusion` from the event line.

### Classify
Use LogSage/RFM scoring:
1. Fetch jobs: `gh run view $run_id --repo $REPO --json jobs`
2. Check job names for patterns (secrets, security, integration, database):
   - Security/secrets failures → CRITICAL
   - Database/migration failures → CRITICAL
   - Integration test failures → HIGH_RETRY (RFM recent)
   - Flaky unit tests → HIGH_RETRY
3. Calculate RFM (Recency × Frequency × Magnitude) from `.serena/memories/cicd-events.md`
4. Map to severity class: CRITICAL / HIGH_RETRY / HIGH_ESCALATE / MEDIUM / SUCCESS

### Route
- **CRITICAL** (security, secrets, migration) → `Agent(cicd-review)` + `SendMessage(cicd-audit)`
- **HIGH_RETRY** (RFM < 4, transient patterns) → `Agent(cicd-auto-retry)` + `SendMessage(cicd-audit)`
- **HIGH_ESCALATE** (RFM ≥ 4, recurring) → `Agent(cicd-review)` + `SendMessage(cicd-audit)`
- **MEDIUM** (flaky, unrelated) → `SendMessage(cicd-audit)` only
- **SUCCESS** → `SendMessage(cicd-audit)` for DORA metrics

### Record
Write `run_id | branch | timestamp | action` to `.serena/memories/cicd-acted-runs.md` to dedup.

## Stopping

Call `TaskStop` on the Monitor's task ID, or stop the persistent monitor via `/task stop`.

## Related

- cicd-monitor agent: `~/.dotfiles/.claude/agents/cicd-monitor.md` (webhook integration, Mode B)
- Monitor patterns: `ai/rules/monitor-patterns.md`
