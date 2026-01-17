---
name: stack-merge
description: Completes a PR merge in Azure DevOps and updates the entire stack. Use when user wants to merge a PR and automatically update all dependent branches.
---

# Stack Merge

Merges a Pull Request and rebases dependent branches in the stack.

## When to Use

Use this skill when the user wants to:
- Merge a specific PR
- "Ship" a feature in the stack
- Update the stack after a PR has been approved and completed

## Instructions

1. Identify the PR ID from the user's request.

2. Execute the merge command:
   ```bash
   .claude/scripts/stack merge <pr-id>
   ```

   This will:
   - Complete the PR in Azure DevOps
   - Update the local stack metadata
   - Prompt to rebase dependent branches

3. Report status to user:
   - Confirm merge success
   - List any branches that were rebased
   - Check if any conflicts occurred during rebase

## Examples

User: "Merge PR #12345"
Action: `.claude/scripts/stack merge 12345`

User: "Ship the current PR"
Action: First find PR ID, then `.claude/scripts/stack merge <id>`
