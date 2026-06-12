---
name: ci-watch
description: "Fire-and-forget CI monitor. Launches a headless background agent that polls GitHub Actions
  and writes status to plans/ci-status.md. Returns within 5 seconds. On green: deploys to DEV and
  sends a macOS notification. Check status with /ci-status."
version: 1.0
triggers:
  - "/ci-watch"
---

# CI Watch Skill

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

Use `Bash` with `run_in_background: true`. Build the prompt with shell variables so
placeholders are substituted by the shell — do NOT hand-edit `<PR_NUMBER>`-style
placeholders inside a quoted heredoc (a quoted delimiter suppresses expansion, and
unsubstituted placeholders have silently broken past runs). Avoid zsh reserved
variable names (`status`, `path`, `options`) in this script.

```bash
PR_NUM="<set from Step 1>"        # e.g. 877
REPO_SLUG="<set from Step 1>"     # e.g. axos-financial/auc-conversion
BRANCH_NAME="<set from Step 1>"   # e.g. chore/my-branch

AGENT_PROMPT=$(cat <<EOF
You are a CI monitoring agent. Your job:

1. Poll GitHub Actions for PR #${PR_NUM} in repo ${REPO_SLUG}, max 10 times at 90-second intervals.
2. After each poll, write current status to plans/ci-status.md:
   - Include: timestamp, run status, conclusion, run URL
   - Format: "**Status:** <IN_PROGRESS|SUCCESS|FAILURE> | Last checked: <time>"
3. If all checks pass (conclusion: success):
   a. Write "**Status:** SUCCESS — deploying to DEV" to plans/ci-status.md
   b. Run: gh workflow run deploy-dev.yml --repo ${REPO_SLUG} (if workflow exists, else skip)
   c. Send macOS notification: osascript -e 'display notification "CI passed — DEV deploy triggered" with title "ci-watch"'
   d. Write final status to plans/ci-status.md and exit
4. If any check fails (conclusion: failure/cancelled):
   a. Write "**Status:** FAILED — <run URL>" to plans/ci-status.md
   b. Send macOS notification: osascript -e 'display notification "CI FAILED on ${BRANCH_NAME}" with title "ci-watch" sound name "Basso"'
   c. Exit
5. After 10 polls with no conclusion, write "**Status:** TIMEOUT — 15 minutes elapsed, no result" and exit.

Poll command:
  gh run list --repo ${REPO_SLUG} --branch ${BRANCH_NAME} --limit 3 \
    --json databaseId,status,conclusion,url \
    --jq '.[] | {id:.databaseId, status:.status, conclusion:.conclusion, url:.url}'

Current working directory: $(pwd)
EOF
)

# Guard: refuse to launch if any placeholder survived substitution
case "$AGENT_PROMPT" in
  *'<PR_NUMBER>'*|*'<REPO>'*|*'<BRANCH>'*|*'<set from Step 1>'*)
    echo "ci-watch: unsubstituted placeholder in agent prompt — aborting" >&2
    exit 1;;
esac

claude -p "$AGENT_PROMPT" \
  --allowedTools "Bash,Read,Write" \
  --output-format stream-json \
  >> "/tmp/ci-watch-${PR_NUM}.log" 2>&1
```

Note: the `<IN_PROGRESS|...>`, `<time>`, and `<run URL>` tokens are intentional — they
are instructions TO the agent, not shell placeholders; the guard only checks the three
launch parameters.

### Step 4 — Report to user

After launching the background agent, immediately tell the user:

```
CI watch started for PR #<PR_NUMBER> (<BRANCH>).
Status file: plans/ci-status.md
Log: /tmp/ci-watch-<PR_NUMBER>.log
Check progress with /ci-status
```

Return immediately — do not wait for CI results.
