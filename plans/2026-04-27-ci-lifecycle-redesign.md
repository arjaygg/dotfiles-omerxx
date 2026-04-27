# CI/CD Lifecycle Redesign Plan

**Date:** 2026-04-27
**Branch:** fixcicdskills

---

## Context

The existing CI skills exist in isolation — they are manually invoked islands with no connecting thread.
`/ci-watch` uses an expensive headless `claude -p` subprocess. `/ci-monitor` is hardcoded to `axos-financial/auc-conversion`.
Neither skill fires automatically after a PR is created or merged.
Review state, concern resolution, and post-merge deployment are completely unmonitored.

The goal: turn CI from a manual "remember to run /ci-watch" ceremony into a **self-propelling lifecycle** that
naturally advances through PR → checks → review → merge → deploy with zero user friction.

---

## What Changes and Why

### Gap → Fix Summary

| Gap | Fix |
|-----|-----|
| PR created → no CI monitoring | New `PostToolUse(Bash)` hook auto-starts lifecycle |
| ci-monitor hardcoded to auc-conversion | Parameterize repo detection from git remote |
| No review state tracking | ci-pr-lifecycle adds a second Monitor stream for reviewDecision |
| No concern tracking | Status surface adds "open_comments" count from PR thread |
| No post-merge deploy watch | New ci-deploy-watch skill + hook after gh pr merge |
| ci-status only works with ci-watch | Rewrite ci-status to read unified plans/ci-status.md |
| ci-watch uses blocking background subprocess | Deprecate in favor of Monitor-based approach |
| Serena CI memory files don't exist | ci-pr-lifecycle bootstraps them on first run |

---

## Auto-trigger Strategy: Skill-Level Chaining + Hook Advisory

**Primary mechanism — skill chaining:**
The `stack-pr` skill explicitly ends with "after PR creation, invoke `/ci-pr-lifecycle`."
The `stack-merge` skill explicitly ends with "after merge completes, invoke `/ci-deploy-watch`."
Claude follows skill instructions naturally — this is what skills are designed for.

**Secondary mechanism — hook as in-session advisory:**
A `PostToolUse(Bash)` hook fires whenever `gh pr create` or `gh pr merge` succeeds.
The hook prints a structured advisory line to the session output that Claude can see:
```
[CI LIFECYCLE] PR #N created — /ci-pr-lifecycle will start automated monitoring
```
This gives Claude awareness even if the user invoked `gh pr create` directly (not via stack-pr).
The hook does NOT spawn a subprocess — it advises, skill instructions execute.

**Why not a background subprocess:** That's the exact pattern deprecated in `ci-watch` v1 (expensive, untrackable). Skill chaining is the correct primitive.

---

## Target Architecture

```
stack-pr invoked (or gh pr create directly)
  ├─→ [skill instruction] → /ci-pr-lifecycle
  └─→ [hook advisory on PostToolUse] → Claude sees advisory, invokes ci-pr-lifecycle

/ci-pr-lifecycle running
  └─→ Monitor(single combined loop: CI + review state)
        ├─→ CI_COMPLETE run_id=X conclusion=success → write ci-status.md, notify
        ├─→ CI_COMPLETE run_id=X conclusion=failure → classify → Agent(cicd-auto-retry/cicd-review)
        ├─→ REVIEW_CHANGED state=APPROVED unresolved=0 → check CI gate → "All gates passed — safe to merge"
        ├─→ REVIEW_CHANGED state=CHANGES_REQUESTED → notify + show unresolved thread count
        └─→ CI green + REVIEW approved → print actionable merge prompt

stack-merge invoked (or gh pr merge directly)
  ├─→ [skill instruction] → /ci-deploy-watch
  └─→ [hook advisory on PostToolUse] → Claude sees advisory, invokes ci-deploy-watch

/ci-deploy-watch running
  └─→ Monitor(deploy workflow stream on main)
        ├─→ DEPLOY_COMPLETE conclusion=success → notify + SendMessage(cicd-audit, deployment_success)
        └─→ DEPLOY_COMPLETE conclusion=failure → Agent(cicd-auto-retry) + notify
```

---

## Single Monitor Stream Design (Combined CI + Review)

A single `Monitor` call runs one shell loop that polls **both** CI runs and review state every 30s.
This avoids the limitation of spinning up two persistent Monitor tasks per skill invocation.

```bash
PR=$PR_NUMBER
REPO=$(git remote get-url origin | sed 's|.*github\.com[/:]||;s|\.git$||')
ACTED_FILE="$(git rev-parse --show-toplevel)/.serena/memories/cicd-acted-runs.md"
LAST_RUNS="" LAST_REVIEW=""

while true; do
  # Stream A — CI runs
  RUNS=$(gh run list --repo "$REPO" --branch "$BRANCH" --limit 5 \
    --json databaseId,status,conclusion --jq '.[] | "\(.databaseId)|\(.status)|\(.conclusion)"' \
    2>/dev/null || echo "")
  if [ "$RUNS" != "$LAST_RUNS" ] && [ -n "$RUNS" ]; then
    diff <(echo "$LAST_RUNS") <(echo "$RUNS") | grep "^>" | sed 's/^> //' \
      | grep --line-buffered "completed" \
      | while IFS='|' read -r id status conclusion; do
          grep -q "$id" "$ACTED_FILE" 2>/dev/null && continue
          echo "CI_COMPLETE run_id=$id conclusion=$conclusion"
        done
    LAST_RUNS="$RUNS"
  fi

  # Stream B — Review state (unresolved threads + decision)
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

Events emitted: `CI_COMPLETE run_id=X conclusion=Y` and `REVIEW_CHANGED state=X required=N approved=M unresolved=K`

---

## Implementation Steps

### Step 1 — Create `ci-pr-lifecycle` skill (NEW)
**File:** `ai/skills/ci-pr-lifecycle/SKILL.md`
**Purpose:** Full lifecycle orchestrator. Invoked after PR creation (manually or via hook).

**Key instructions in the skill:**
1. Detect current PR number, branch, and repo from `git remote`/`gh pr view`
2. Bootstrap missing Serena memory files if absent (cicd-acted-runs, cicd-events, cicd-incidents, etc.)
3. Start Monitor stream A — CI checks:
   ```bash
   # Poll-and-diff on gh run list --repo $REPO --branch $BRANCH
   # Emit: RUN_COMPLETE run_id=X branch=Y conclusion=Z
   # Dedup against cicd-acted-runs.md
   ```
4. Start Monitor stream B — Review state:
   ```bash
   # Poll gh pr view $PR --json reviewDecision,comments
   # Emit: REVIEW_CHANGED state=APPROVED|CHANGES_REQUESTED open_comments=N
   ```
5. React to events:
   - CI SUCCESS + REVIEW APPROVED → print "All gates passed — run /stack-merge to land"
   - CI FAILURE → classify (LogSage/RFM) → Agent(cicd-auto-retry) or Agent(cicd-review)
   - CHANGES_REQUESTED → notify user + show open comment count
   - All PR comments resolved → update ci-status.md
6. Write status to `plans/ci-status.md` after each event

**Triggers:** `/ci-pr-lifecycle`, text "watch PR", "monitor PR", "track PR"

---

### Step 2 — Create `ci-deploy-watch` skill (NEW)
**File:** `ai/skills/ci-deploy-watch/SKILL.md`
**Purpose:** Post-merge deployment health monitor. Invoked after merge.

**Key instructions in the skill:**
1. Detect repo from git remote. Target branch = main.
2. Start Monitor stream — deployment workflows on main:
   ```bash
   # Poll gh run list --repo $REPO --branch main --limit 5
   # Filter for deploy-* or release-* workflow names
   # Emit: DEPLOY_COMPLETE workflow=X run_id=Y conclusion=Z
   ```
3. React:
   - SUCCESS → macOS notification "Deployed: $WORKFLOW" + SendMessage(cicd-audit, deployment_success)
   - FAILURE → Agent(cicd-auto-retry) + macOS notification + write ci-status.md
4. Timeout after 30 minutes, write final status.

**Triggers:** `/ci-deploy-watch`, "watch deploy", "monitor deploy"

---

### Step 3 — Update `ci-monitor` skill (v4.0)
**File:** `ai/skills/ci-monitor/SKILL.md`
**Changes:**
- Remove hardcoded `axos-financial/auc-conversion` — detect from `git remote get-url origin | sed 's|.*github.com[/:]||;s|\.git$||'`
- Remove hardcoded `ACTED_FILE` path — use `$(git rev-parse --show-toplevel)/.serena/memories/cicd-acted-runs.md`
- Add `--repo $REPO` to the `gh run list` command
- Add inline bootstrap: create `cicd-acted-runs.md` if absent before Monitor starts
- Clarify Monitor event handler steps as structured pseudocode, not ambiguous LLM prose
- Add version bump to 4.0

---

### Step 4 — Update `ci-status` skill (v2.0)
**File:** `ai/skills/ci-status/SKILL.md`
**Changes:**
- Read `plans/ci-status.md` if present (works for both ci-watch and ci-pr-lifecycle)
- If file absent: check if a Monitor task is running (`gh run list` for current branch)
- Display: PR number, CI status, review state, open concerns count, deploy status
- Stop saying "Run /ci-watch" — instead suggest `/ci-pr-lifecycle`

---

### Step 5 — Create post-PR-create hook
**File:** `.claude/hooks/post-pr-lifecycle-trigger.sh`
**Purpose:** Auto-start `ci-pr-lifecycle` after every successful `gh pr create`.

**Logic:**
```bash
#!/usr/bin/env bash
# Fires on PostToolUse(Bash). Checks if a gh pr create succeeded.
INPUT=$(cat)  # JSON from PostToolUse hook
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
TOOL_OUTPUT=$(echo "$INPUT" | jq -r '.tool_response.output // ""')

# Only act on successful gh pr create
if echo "$TOOL_INPUT" | grep -q "gh pr create" && echo "$TOOL_OUTPUT" | grep -q "https://github.com"; then
  PR_URL=$(echo "$TOOL_OUTPUT" | grep -o 'https://github.com[^ ]*')
  PR_NUMBER=$(echo "$PR_URL" | grep -o '[0-9]*$')
  echo "auto-ci: PR #$PR_NUMBER created — starting lifecycle monitor"
  # Write trigger file that ci-pr-lifecycle reads at startup
  echo "$PR_NUMBER" > /tmp/ci-lifecycle-trigger.txt
fi
```

**Register in `settings.json`:** Under `hooks.PostToolUse` for `Bash`.

---

### Step 6 — Create post-merge deploy hook
**File:** `.claude/hooks/post-merge-deploy-trigger.sh`
**Purpose:** Auto-start `ci-deploy-watch` after successful `gh pr merge`.

**Logic:** Same pattern as Step 5 — detect `gh pr merge` in tool_input, detect success in output, write trigger file.

**Register in `settings.json`:** Under `hooks.PostToolUse` for `Bash`.

---

### Step 7 — Deprecate `ci-watch` v1
**File:** `ai/skills/ci-watch/SKILL.md`
**Changes:**
- Add deprecation header: `⚠️ DEPRECATED in favor of /ci-pr-lifecycle`
- Keep instructions but add redirect: "For the full PR lifecycle (CI + review + deploy), use `/ci-pr-lifecycle` instead."
- Do NOT delete — existing users who invoke `/ci-watch` directly still get a working experience

---

## Files Modified

| File | Action | Why |
|------|--------|-----|
| `ai/skills/ci-pr-lifecycle/SKILL.md` | **CREATE** | Core orchestrator — the missing link |
| `ai/skills/ci-deploy-watch/SKILL.md` | **CREATE** | Post-merge deployment monitoring |
| `ai/skills/ci-monitor/SKILL.md` | **UPDATE** | Remove hardcoded repo, fix event handler prose |
| `ai/skills/ci-status/SKILL.md` | **UPDATE** | Unified status — works with both old and new |
| `ai/skills/ci-watch/SKILL.md` | **UPDATE** | Deprecation notice + redirect |
| `.claude/hooks/post-pr-lifecycle-trigger.sh` | **CREATE** | Auto-trigger after gh pr create |
| `.claude/hooks/post-merge-deploy-trigger.sh` | **CREATE** | Auto-trigger after gh pr merge |
| `.claude/settings.json` | **UPDATE** | Register two new PostToolUse hooks |

---

## Verification

1. **ci-pr-lifecycle triggered manually:** Run `/ci-pr-lifecycle` on a branch with an open PR. Verify Monitor starts, events appear, `plans/ci-status.md` is written.

2. **Auto-trigger after stack-pr:** Create a PR using `stack pr` or `gh pr create`. Verify post-pr-lifecycle-trigger.sh fires and `ci-pr-lifecycle` begins without explicit invocation.

3. **Review state detection:** Add a reviewer to the PR. Approve it. Verify REVIEW_CHANGED event appears in session.

4. **Deploy watch after merge:** Merge a PR. Verify post-merge-deploy-trigger.sh fires and deploy workflow is being watched.

5. **ci-status unified:** After starting `/ci-pr-lifecycle`, run `/ci-status` — verify it shows CI status + review state.

6. **ci-monitor repo detection:** In any GitHub repo, run `/ci-monitor` — verify REPO is detected from git remote, not hardcoded.

---

## Deferred (Out of Scope for This PR)

- Full RFM implementation (currently placeholder R=1, F=1 in cicd-monitor.md)
- DORA metrics rollup cadence (cicd-audit.md describes hourly rollup but has no CronCreate)
- Concern resolution tracking via PR comment thread analysis (requires gh pr comments API)
- Teams webhook fallback if `$SI_TEAMS_WEBHOOK_URL` is unset in cicd-review.md
- Orphaned `monitor-cicd-build.sh` hook — needs separate PR to register or consolidate
