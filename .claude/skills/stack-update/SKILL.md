---
name: stack-update
description: Updates the PR stack after a base branch is merged. USE THIS SKILL when user says "restack", "update stack", "rebase stack", "sync stack", "refresh stack", "update after merge", or needs to rebase dependent branches after a merge.
triggers:
  - restack
  - update stack
  - rebase stack
  - sync stack
  - refresh stack
  - update after merge
  - rebase branches
  - sync with main
  - update dependencies
  - rebase all
  - stack rebase
---

# Stack Update

Updates (rebases) the PR stack to ensure all branches are current.

## When to Use

Use this skill when:
- A base PR was merged
- `main` has updated and stack needs syncing
- User wants to "restack" or "rebase" their changes

## Instructions

1. Execute the update/restack command:
   ```bash
   .claude/scripts/stack restack
   ```
   OR if updating specific branch after merge:
   ```bash
   .claude/scripts/stack update [merged-branch]
   ```

2. This will:
   - Fetch latest changes
   - Rebase branches in order
   - Force push (safely) to update PRs

3. Report any conflicts that require manual intervention.

## Examples

User: "Restack my branches"
Action: `.claude/scripts/stack restack`

User: "Update the stack after feature/base merged"
Action: `.claude/scripts/stack update feature/base`
