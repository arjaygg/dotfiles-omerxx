---
name: stack-status
description: Shows the current PR stack status and branch hierarchy. Use when user wants to see their PR stack, view branch relationships, check PR status, or understand the dependency tree.
---

# Stack Status

Shows the current PR stack status including branch relationships and PR states.

## When to Use

Use this skill when the user wants to:
- See their current PR stack
- View branch relationships and dependencies
- Check which PRs are open, merged, or draft
- Understand the branch hierarchy
- See which branches need rebasing

## Instructions

1. Parse the user's request to identify:
   - `--verbose`: Whether to show detailed information

2. Execute the stack listing script:
   ```bash
   ./scripts/pr-stack/list-stack.sh [--verbose]
   ```

3. If the script is not found, gather information manually:
   - List branches: `git branch -a`
   - Check tracking: `git branch -vv`
   - Query Azure DevOps for PR status if authenticated

4. Present the stack visualization to the user showing:
   - Branch hierarchy (tree format)
   - PR status for each branch
   - Commits ahead of base
   - Which branch is currently checked out

## Output Format

```
PR Stack Status:
================

main
├── feature/base-impl (PR #123 - APPROVED)
│   └── feature/enhanced-impl (PR #124 - DRAFT)
├── feature/parallel-work (PR #125 - IN REVIEW)
└── refactor/cleanup (LOCAL ONLY)
```

## Examples

User: "Show me my PR stack"
Action: `./scripts/pr-stack/list-stack.sh`

User: "What's the status of my branches?"
Action: `./scripts/pr-stack/list-stack.sh --verbose`

User: "Show branch dependencies"
Action: `./scripts/pr-stack/list-stack.sh`
