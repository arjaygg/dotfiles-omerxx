---
name: stack-create
description: Creates a new stacked branch for PR stacking workflows. Use when user wants to create a new branch that builds on another branch, start a PR stack, or create a feature branch with dependencies.
---

# Stack Create

Creates a new stacked branch with optional worktree for PR stacking workflows.

## When to Use

Use this skill when the user wants to:
- Create a new branch that builds on another branch (not just main)
- Start a PR stacking workflow
- Create a feature branch with a specific base branch
- Set up parallel development with git worktrees

## Instructions

1. Parse the user's request to identify:
   - `branch-name`: The name for the new branch (required)
   - `base-branch`: The branch to base on (default: current branch or main)
   - `commit-message`: Optional initial commit message

2. Execute the unified stack CLI:
   ```bash
   ./scripts/stack create <branch-name> [base-branch]
   ```

   This will automatically:
   - Use Charcoal if available (better UX, automatic stacking)
   - Fall back to native scripts otherwise
   - Sync metadata for Azure DevOps compatibility

3. If scripts are not found, perform these steps manually:
   - Fetch latest from remote: `git fetch origin`
   - Create and checkout new branch: `git checkout -b <branch-name> <base-branch>`
   - Push with tracking: `git push -u origin <branch-name>`
   - If commit message provided, create initial commit

4. Report the result to the user, including:
   - Branch created successfully
   - Base branch it's built on
   - Whether Charcoal was used
   - Next steps (develop, then create PR)

## Charcoal Integration

If Charcoal is installed and initialized, the unified CLI will:
- Use `gt branch create` for better stack tracking
- Automatically set the parent branch
- Enable navigation with `./scripts/stack up` and `./scripts/stack down`

To enable Charcoal:
```bash
brew install danerwilliams/tap/charcoal
./scripts/stack init
```

## Examples

User: "Create a new stacked branch for user authentication"
Action: `./scripts/stack create feature/user-auth main`

User: "Create a branch for tests based on the API branch"
Action: `./scripts/stack create feature/api-tests feature/api`

User: "Stack a new branch called feature/ui on top of feature/backend"
Action: `./scripts/stack create feature/ui feature/backend`

User: "Create a feature branch on top of current branch"
Action: `./scripts/stack create feature/next-step`
(Will automatically use current branch as base)

## Related Skills

- **stack-navigate**: Move between branches (up/down)
- **stack-status**: View stack hierarchy
- **stack-pr**: Create Azure DevOps PR
- **stack-update**: Update after merge
