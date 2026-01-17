---
name: stack-status
description: Shows the current PR stack status and branch hierarchy. Use when user wants to see their PR stack, view branch relationships, check PR status, or understand the dependency tree.
---

# Stack Status

Displays the current state of the PR stack, including branch hierarchy and PR status.

## When to Use

Use this skill when the user wants to:
- See the full stack of branches
- Check which PRs are merged/open
- Understand branch dependencies
- Visualize the tree structure

## Instructions

1. Execute the status command:
   ```bash
   .claude/scripts/stack status
   ```

2. This will display:
   - Visual tree of branches (via Charcoal if available)
   - PR status for each branch
   - Current position in the stack

## Examples

User: "Show me my PR stack"
Action: `.claude/scripts/stack status`

User: "Where am I in the stack?"
Action: `.claude/scripts/stack status`
