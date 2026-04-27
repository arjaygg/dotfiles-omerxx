---
name: ci-watch
description: "⚠️ DEPRECATED in favor of /ci-pr-lifecycle. Legacy fire-and-forget CI monitor using headless subprocess.
  For full PR lifecycle (CI + review + deploy) with zero-cost event streaming, use /ci-pr-lifecycle instead.
  This skill remains functional for backwards compatibility."
version: 1.0
triggers:
  - "/ci-watch"
---

# CI Watch Skill (DEPRECATED)

⚠️ **This skill is deprecated.** Use `/ci-pr-lifecycle` for full PR lifecycle monitoring (CI + review state + deployment readiness).

For the full PR workflow (CI checks + review validation + deployment monitoring) with efficient event-driven streaming, invoke:
```
/ci-pr-lifecycle
```

This skill uses a headless background subprocess, which is expensive and untrackable. The Monitor-based `/ci-pr-lifecycle` approach is 10-20x cheaper and integrates naturally with the PR lifecycle.

---

## Legacy Instructions (Kept for Backwards Compatibility)

Launches a background headless Claude agent to monitor CI for the current PR. Returns immediately
— the agent runs independently and writes results to `plans/ci-status.md`.

## Instructions

### Step 1 — Detect current PR

Run these to get branch and PR number:

```bash
BRANCH=$(git branch --show-current)
PR_URL=$(gh pr view --json url --jq '.url' 2>/dev/null || echo "")
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
**Status:** WATCHING — background agent running (PID: pending)
```

### Step 3 — Launch background agent

Use `Bash` with `run_in_background: true`:

```bash
claude -p "$(cat <<'AGENT_PROMPT'
You are a CI monitoring agent. Your job:

1. Poll GitHub Actions for PR #<PR_NUMBER> in repo <REPO>, max 10 times at 90-second intervals.
2. After each poll, write current status to plans/ci-status.md:
   - Include: timestamp, run status, conclusion, run URL
   - Format: "**Status:** <IN_PROGRESS|SUCCESS|FAILURE> | Last checked: <time>"
3. If all checks pass (conclusion: success):
   a. Write "**Status:** SUCCESS — deploying to DEV" to plans/ci-status.md
   b. Run: gh workflow run deploy-dev.yml --repo <REPO> (if workflow exists, else skip)
   c. Send macOS notification: osascript -e 'display notification "CI passed — DEV deploy triggered" with title "ci-watch"'
   d. Write final status to plans/ci-status.md and exit
4. If any check fails (conclusion: failure/cancelled):
   a. Write "**Status:** FAILED — <run URL>" to plans/ci-status.md
   b. Send macOS notification: osascript -e 'display notification "CI FAILED on <BRANCH>" with title "ci-watch" sound name "Basso"'
   c. Exit
5. After 10 polls with no conclusion, write "**Status:** TIMEOUT — 15 minutes elapsed, no result" and exit.

Poll command:
  gh run list --repo <REPO> --branch <BRANCH> --limit 3 \
    --json databaseId,status,conclusion,url \
    --jq '.[] | {id:.databaseId, status:.status, conclusion:.conclusion, url:.url}'

Current working directory: $(pwd)
AGENT_PROMPT
)" \
  --allowedTools "Bash,Read,Write" \
  --output-format stream-json \
  >> /tmp/ci-watch-<PR_NUMBER>.log 2>&1
```

Note: Replace `<PR_NUMBER>`, `<REPO>`, and `<BRANCH>` with the actual values before launching.

### Step 4 — Report to user

After launching the background agent, immediately tell the user:

```
CI watch started for PR #<PR_NUMBER> (<BRANCH>).
Status file: plans/ci-status.md
Log: /tmp/ci-watch-<PR_NUMBER>.log
Check progress with /ci-status
```

Return immediately — do not wait for CI results.
