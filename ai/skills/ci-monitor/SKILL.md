---
name: ci-monitor
description: "Self-healing CI/CD monitor. Uses the Monitor tool to stream GitHub Actions events
  in real-time — zero tokens when silent, notifications only on status changes. Classifies
  failures with LogSage/RFM, auto-retries HIGH, escalates CRITICAL. 10-20x cheaper than
  poll-agent approach. Invoke via /ci-monitor."
version: 3.0
triggers:
  - "/ci-monitor"
  - "/monitor-ci"
---

# CI Monitor Skill

Event-driven CI watcher. Uses the `Monitor` tool to stream GitHub Actions status changes
directly into your session — no background agent required for observation.

## Instructions

Call the `Monitor` tool with these parameters:

**description:** `"GitHub Actions status on axos-financial/auc-conversion"`

**persistent:** `true`

**command:**
```bash
REPO="axos-financial/auc-conversion"
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

When a `RUN_COMPLETE` notification arrives, classify and route inline:

1. **Parse:** extract `run_id`, `branch`, `conclusion` from the event line
2. **Classify** with LogSage/RFM:
   - Fetch jobs: `gh run view $run_id --repo axos-financial/auc-conversion --json jobs`
   - Check for secrets/CVE jobs → CRITICAL
   - Calculate RFM score from `.serena/memories/cicd-events.md`
   - Map to: CRITICAL / HIGH_RETRY (RFM<4) / HIGH_ESCALATE (RFM≥4) / MEDIUM / SUCCESS
3. **Route:**
   - CRITICAL → `Agent(cicd-review)` + `SendMessage(cicd-audit)`
   - HIGH_RETRY → `Agent(cicd-auto-retry)` + `SendMessage(cicd-audit)`
   - HIGH_ESCALATE → `Agent(cicd-review)` + `SendMessage(cicd-audit)`
   - MEDIUM → `SendMessage(cicd-audit)` only
   - SUCCESS → `SendMessage(cicd-audit)` for DORA metrics
4. **Record** `run_id` in `.serena/memories/cicd-acted-runs.md`

## Stopping

Call `TaskStop` on the Monitor's task ID, or stop the persistent monitor via `/task stop`.

## Related

- cicd-monitor agent: `~/.dotfiles/.claude/agents/cicd-monitor.md` (webhook Mode B only)
- Monitor patterns: `ai/rules/monitor-patterns.md`
