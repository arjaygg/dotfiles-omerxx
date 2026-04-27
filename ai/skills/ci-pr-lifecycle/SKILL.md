---
name: ci-pr-lifecycle
description: "Full PR lifecycle monitor. Starts after PR creation and orchestrates CI checks + review state tracking + deployment readiness gates. Uses Monitor for event streaming (zero cost when silent). Emits: 'All gates passed — run /stack-merge to land' when CI succeeds + PR approved + concerns resolved."
version: 1.0
triggers:
  - "/ci-pr-lifecycle"
  - "watch PR"
  - "monitor PR"
  - "track PR"
---

# CI PR Lifecycle Skill

Unified orchestrator for the full PR workflow: CI checks, review state, and merge readiness.
Invoked automatically after `/stack-pr` or `/ci-pr-merge` creates a PR. Can be invoked manually to restart monitoring.

## Instructions

### Step 1 — Detect PR, branch, and repo

Run these commands to gather context:

```bash
BRANCH=$(git branch --show-current)
PR_NUMBER=$(gh pr view --json number --jq '.number' 2>/dev/null || echo "")
REPO=$(git remote get-url origin | sed 's|.*github\.com[/:]||;s|\.git$||')
```

If `PR_NUMBER` is empty, tell the user "No open PR found on this branch" and stop.

### Step 2 — Bootstrap Serena memory files if absent

Create `.serena/memories/` and these files if they don't exist:

**`~/.dotfiles/.serena/memories/cicd-acted-runs.md`** — tracks run IDs already handled (deduplication)
```markdown
# CICD Acted Runs

> Last updated: <timestamp>

Tracks CI runs that have been processed to avoid duplicate handling.
Format: `run_id | timestamp | action_taken`

---

## Processed Runs

(none yet)
```

**`~/.dotfiles/.serena/memories/cicd-events.md`** — event log for RFM scoring
```markdown
# CICD Event Log

Recency × Frequency × Magnitude scoring history.

---

## Events

(none yet)
```

**`~/.dotfiles/.serena/memories/cicd-incidents.md`** — incident tracking
```markdown
# CICD Incidents

Critical failures requiring manual intervention.

---

## Active Incidents

(none yet)
```

### Step 3 — Write initial status

Write to `plans/ci-status.md`:

```markdown
# CI Lifecycle Status

**PR:** #<PR_NUMBER> — <BRANCH>
**Repo:** <REPO>
**Started:** <timestamp>
**Status:** MONITORING — polling CI and review state every 30s
```

### Step 4 — Start Monitor with combined CI + review polling loop

Call the `Monitor` tool with these parameters:

**description:** `"CI + Review lifecycle for PR #<PR_NUMBER> in <REPO>"`

**persistent:** `true`

**timeout_ms:** `1800000` (30 minutes)

**command:**
```bash
PR="<PR_NUMBER>"
REPO="<REPO>"
BRANCH="<BRANCH>"
ACTED_FILE="${HOME}/.dotfiles/.serena/memories/cicd-acted-runs.md"
LAST_RUNS=""
LAST_REVIEW=""

while true; do
  # ===== Stream A: CI Runs =====
  RUNS=$(gh run list --repo "$REPO" --branch "$BRANCH" --limit 5 \
    --json databaseId,status,conclusion --jq '.[] | "\(.databaseId)|\(.status)|\(.conclusion)"' \
    2>/dev/null || echo "")

  if [ "$RUNS" != "$LAST_RUNS" ] && [ -n "$RUNS" ]; then
    NEW_RUNS=$(diff <(echo "$LAST_RUNS") <(echo "$RUNS") 2>/dev/null \
      | grep "^>" | sed 's/^> //' || true)

    echo "$NEW_RUNS" | grep --line-buffered "completed" | while IFS='|' read -r id status conclusion; do
      if grep -q "$id" "$ACTED_FILE" 2>/dev/null; then
        continue
      fi
      echo "CI_COMPLETE run_id=$id conclusion=$conclusion"
    done
    LAST_RUNS="$RUNS"
  fi

  # ===== Stream B: Review State =====
  REVIEW=$(gh pr view "$PR" --repo "$REPO" \
    --json reviewDecision,reviewRequests,latestReviews,reviewThreads \
    --jq '"state=\(.reviewDecision // "PENDING") required=\(.reviewRequests | length) approved=\([.latestReviews[] | select(.state=="APPROVED")] | length) unresolved=\([.reviewThreads[] | select(.isResolved==false)] | length)"' \
    2>/dev/null || echo "")

  if [ "$REVIEW" != "$LAST_REVIEW" ] && [ -n "$REVIEW" ]; then
    echo "REVIEW_CHANGED $REVIEW"
    LAST_REVIEW="$REVIEW"
  fi

  sleep 30
done
```

### Step 5 — React to Monitor events

As Monitor emits events, parse and handle them inline in the session:

#### On `CI_COMPLETE` event:
- Parse: `run_id`, `conclusion`
- If `conclusion == success`:
  - Write to `cicd-acted-runs.md`: `run_id | <timestamp> | success`
  - Write to `plans/ci-status.md`: `**CI Status:** ✅ PASSED`
  - Check if review is also approved (see REVIEW_CHANGED handler below) → if yes, print merge prompt
- If `conclusion == failure` or `conclusion == cancelled`:
  - Write to `cicd-acted-runs.md`: `run_id | <timestamp> | failure`
  - Write to `plans/ci-status.md`: `**CI Status:** ❌ FAILED`
  - Classify failure (fetch `gh run view $run_id --repo $REPO --json jobs` and check job logs for RFM pattern)
  - Route: If HIGH/CRITICAL → `Agent(cicd-auto-retry)` or `Agent(cicd-review)`, else `SendMessage(cicd-audit, ...)`

#### On `REVIEW_CHANGED` event:
- Parse: `state`, `required`, `approved`, `unresolved`
- If `state == APPROVED` AND `unresolved == 0`:
  - Check if CI is also green (read last line of `plans/ci-status.md`)
  - If CI green: print **"✅ All gates passed — run `/stack-merge` to land this PR"**
  - Write to `plans/ci-status.md`: `**Review Status:** ✅ APPROVED (all concerns resolved)`
- If `state == CHANGES_REQUESTED`:
  - Write to `plans/ci-status.md`: `**Review Status:** ⚠️ CHANGES REQUESTED (${unresolved} unresolved concerns)`
  - Notify user with concern count
- If `state == PENDING` and `required > 0`:
  - Write to `plans/ci-status.md`: `**Review Status:** ⏳ PENDING (${required} reviewers, ${unresolved} unresolved)`

### Step 6 — Handle Monitor timeout (30 minutes)

When Monitor stops (timeout or manual exit):
- Write final status to `plans/ci-status.md`
- If CI is green + review approved: print merge prompt
- Else: print current gate status

Tell the user:
> Lifecycle monitoring completed. Check `/ci-status` for current state. To resume, run `/ci-pr-lifecycle` again.

## Related

- `/ci-deploy-watch` — watches deployment after merge
- `/ci-status` — reads unified status file
- `stack-pr` skill — chains to `/ci-pr-lifecycle` after PR creation
