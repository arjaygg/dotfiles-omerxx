---
name: stack-merge
description: Completes a PR merge in Azure DevOps and updates the entire stack. Use when user wants to merge a PR and automatically update all dependent branches.
---

# Stack Merge

Completes a PR merge in Azure DevOps and updates the entire stack.

## When to Use

Use this skill when the user wants to:
- Merge a PR that's been approved
- Complete a PR and update dependent branches
- Merge and clean up the stack automatically

## Instructions

1. Parse the user's request to identify:
   - `pr-id`: The Azure DevOps PR ID to merge (required)

2. Execute the merge script:
   ```bash
   ./scripts/pr-stack/merge-stack.sh <pr-id>
   ```

3. If the script is not found, perform manually:
   - Complete PR merge via Azure CLI:
     ```bash
     az repos pr update --id <pr-id> --status completed \
       --organization "https://dev.azure.com/bofaz"
     ```
   - Update local repository: `git fetch origin && git pull`
   - Run stack update to rebase dependents

4. Report results including:
   - PR merged successfully
   - Branches that were updated
   - New stack status

## Requirements

- PR must be approved
- All build validations must pass
- No merge conflicts

## Examples

User: "Merge PR 123"
Action: `./scripts/pr-stack/merge-stack.sh 123`

User: "Complete the merge for PR #456 and update the stack"
Action: `./scripts/pr-stack/merge-stack.sh 456`

User: "Help me merge this PR"
Action: First get PR ID, then `./scripts/pr-stack/merge-stack.sh <id>`
