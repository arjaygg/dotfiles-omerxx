---
name: stack-pr
description: Creates a Pull Request in Azure DevOps for the current or specified branch. Handles stacked dependencies automatically.
---

# Stack PR

Creates a Pull Request in Azure DevOps, correctly handling stacked dependencies.

## When to Use

Use this skill when the user wants to:
- Create a PR for their current work
- Submit a feature for review
- Create a draft PR
- Stack a PR on top of another PR

## Instructions

1. Identify parameters:
   - `branch`: Source branch (default: current)
   - `target`: Target branch (default: inferred from stack or main)
   - `title`: PR title (optional)
   - `draft`: Whether to create as draft (optional)

2. Execute the PR creation script:
   ```bash
   .claude/scripts/stack pr <branch> [target] [title]
   ```

   This will:
   - Push the branch if needed
   - Create PR in Azure DevOps
   - Link dependencies in description
   - Add "Stacked PR" metadata

3. Return the PR URL to the user.

## Examples

User: "Create a PR for this feature"
Action: `.claude/scripts/stack pr $(git branch --show-current)`

User: "Create a stacked PR for feature/login-ui"
Action: `.claude/scripts/stack pr feature/login-ui`

User: "Submit this as a draft"
Action: `.claude/scripts/stack pr $(git branch --show-current) --draft`
