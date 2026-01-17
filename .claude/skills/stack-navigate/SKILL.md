---
name: stack-navigate
description: Navigate between stacked branches using Charcoal (gt up/down). Use when user wants to move to parent or child branch in their PR stack.
---

# Stack Navigate

Navigate between branches in a PR stack using Charcoal's `gt up` and `gt down` commands.

## When to Use

Use this skill when the user wants to:
- "Go up" to the parent branch
- "Go down" to a child branch
- Traverse the PR stack
- Switch context to a dependency

## Instructions

1. Determine direction (up/down) from user request.

2. Execute the navigation command:
   ```bash
   .claude/scripts/stack up    # Go to parent
   .claude/scripts/stack down  # Go to child
   ```

   Note: These commands require Charcoal to be installed and initialized.

3. If command fails (Charcoal not installed), fall back to git:
   - Find parent/child branch name from `.git/pr-stack-info`
   - `git checkout <branch>`

## Examples

User: "Go to the parent branch"
Action: `.claude/scripts/stack up`

User: "Switch to the next PR in the stack"
Action: `.claude/scripts/stack down`
