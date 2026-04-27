---
name: ci-deploy-watch
description: "Post-merge deployment monitor. Watches GitHub Actions workflows on main branch for build/deploy completion. Fires notifications on success/failure. Auto-routes failures to cicd-auto-retry or cicd-review."
version: 1.0
triggers:
  - "/ci-deploy-watch"
  - "watch deploy"
  - "monitor deploy"
---

# CI Deploy Watch Skill

Deployed-state monitor triggered after PR merge. Watches for build and deployment workflows on main branch.

## Instructions

### Step 1 — Detect repo

```bash
REPO=$(git remote get-url origin | sed 's|.*github\.com[/:]||;s|\.git$||')
```

### Step 2 — Write initial status

Write to `plans/ci-status.md`:

```markdown
# Deployment Monitor

**Repo:** <REPO>
**Target:** main
**Started:** <timestamp>
**Status:** MONITORING — watching for deploy workflows
```

### Step 3 — Start Monitor for deployment workflows

Call the `Monitor` tool with these parameters:

**description:** `"Deploy workflows on <REPO>/main"`

**persistent:** `true`

**timeout_ms:** `1800000` (30 minutes)

**command:**
```bash
REPO="<REPO>"
LAST_SNAPSHOT=""

while true; do
  SNAPSHOT=$(gh run list --repo "$REPO" --branch main --limit 10 \
    --json databaseId,name,status,conclusion \
    --jq '.[] | select(.name | test("deploy|release|publish"; "i")) | "\(.databaseId)|\(.name)|\(.status)|\(.conclusion)"' \
    2>/dev/null || echo "")

  if [ "$SNAPSHOT" != "$LAST_SNAPSHOT" ] && [ -n "$SNAPSHOT" ]; then
    NEW=$(diff <(echo "$LAST_SNAPSHOT") <(echo "$SNAPSHOT") 2>/dev/null \
      | grep "^>" | sed 's/^> //' || true)

    echo "$NEW" | grep --line-buffered "completed" | while IFS='|' read -r id name status conclusion; do
      echo "DEPLOY_COMPLETE workflow=$name run_id=$id conclusion=$conclusion"
    done
    LAST_SNAPSHOT="$SNAPSHOT"
  fi

  sleep 30
done
```

### Step 4 — React to Monitor events

#### On `DEPLOY_COMPLETE` event:
- Parse: `workflow`, `run_id`, `conclusion`
- If `conclusion == success`:
  - Send macOS notification: `osascript -e 'display notification "✅ Deployed: ${workflow}" with title "ci-deploy-watch"'`
  - Write to `plans/ci-status.md`: `**Deploy Status:** ✅ SUCCESS — ${workflow} completed`
  - Send message to `cicd-audit` agent with deployment success event
- If `conclusion == failure` or `conclusion == cancelled`:
  - Send macOS notification: `osascript -e 'display notification "❌ Deploy failed: ${workflow}" with title "ci-deploy-watch" sound name "Basso"'`
  - Write to `plans/ci-status.md`: `**Deploy Status:** ❌ FAILED — ${workflow}`
  - Fetch job details: `gh run view $run_id --repo $REPO --json jobs`
  - Classify and route: spawn `Agent(cicd-auto-retry)` for transient, `Agent(cicd-review)` for systemic
  - Send message to `cicd-audit` agent with failure event

### Step 5 — On Monitor timeout

Write final deployment status to `plans/ci-status.md`. Print summary to user.

## Related

- `/ci-pr-lifecycle` — watches PR creation through merge
- `/ci-status` — unified status view
- `stack-merge` skill — chains to `/ci-deploy-watch` after merge
