---
name: stack-pr
description: Creates a pull request in Azure DevOps for PR stacking. Use when user wants to create a PR, submit code for review, or open a pull request targeting a specific branch.
---

# Stack PR

Creates a pull request in Azure DevOps for the current or specified branch.

## When to Use

Use this skill when the user wants to:
- Create a PR for the current branch
- Submit code for review
- Open a pull request targeting a specific branch
- Create a draft PR

## Instructions

1. Parse the user's request to identify:
   - `source-branch`: Branch to create PR from (default: current branch)
   - `target-branch`: Branch to target (default: main, or the base branch if stacked)
   - `title`: PR title (optional, derived from commits if not provided)
   - `--draft`: Whether to create as draft PR

2. Execute the PR creation script:
   ```bash
   ./scripts/pr-stack/create-pr.sh <source-branch> [target-branch] [title] [--draft]
   ```

3. If the script is not found, use Azure CLI directly:
   ```bash
   az repos pr create \
     --organization "https://dev.azure.com/bofaz" \
     --project "Axos-Universal-Core" \
     --source-branch <source-branch> \
     --target-branch <target-branch> \
     --title "<title>"
   ```

4. Report the result including:
   - PR number and URL
   - Target branch
   - Next steps

## Examples

User: "Create a PR for this branch"
Action: `./scripts/pr-stack/create-pr.sh $(git branch --show-current)`

User: "Create a PR targeting the API branch"
Action: `./scripts/pr-stack/create-pr.sh $(git branch --show-current) feature/api`

User: "Open a draft PR with title 'Add user profile'"
Action: `./scripts/pr-stack/create-pr.sh $(git branch --show-current) main "Add user profile" --draft`
