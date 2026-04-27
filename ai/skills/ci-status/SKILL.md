---
name: ci-status
description: "Unified CI status view. Reads plans/ci-status.md written by /ci-pr-lifecycle or /ci-monitor.
  Displays PR number, CI status, review state, concerns count, and deployment status.
  Works with both new Monitor-based lifecycle and legacy ci-watch."
version: 2.0
triggers:
  - "/ci-status"
---

# CI Status Skill

Unified status display for the current PR's CI/CD lifecycle.
Works with both `/ci-pr-lifecycle` (new) and legacy `/ci-watch`.

## Instructions

Read `plans/ci-status.md` if present and display its contents to the user.

### If file exists
Display it as-is. The status file is kept current by:
- `/ci-pr-lifecycle` Monitor loop
- `/ci-monitor` Monitor loop
- `/ci-watch` background agent (legacy)

### If file does not exist
Check if an active Monitor task is running by polling:
```bash
BRANCH=$(git branch --show-current)
REPO=$(git remote get-url origin | sed 's|.*github\.com[/:]||;s|\.git$||')
PR=$(gh pr view --json number --jq '.number' 2>/dev/null || echo "")

if [ -z "$PR" ]; then
  echo "No open PR on $(git branch --show-current). Start monitoring with /ci-pr-lifecycle."
else
  RUNS=$(gh run list --repo "$REPO" --branch "$BRANCH" --limit 1 --json databaseId,status,conclusion)
  echo "No status file yet. Run /ci-pr-lifecycle on this branch to start monitoring."
fi
```

Then suggest:
> No active CI watch found. Run `/ci-pr-lifecycle` on a branch with an open PR to start unified monitoring (CI + review state + deployment).
>
> Or for legacy behavior: run `/ci-monitor` for a repo-wide CI watcher, or `/ci-watch` for this PR only.

