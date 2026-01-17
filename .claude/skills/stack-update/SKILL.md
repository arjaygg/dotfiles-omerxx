---
name: stack-update
description: Updates the PR stack after a base branch is merged. Use when a PR was merged and dependent branches need rebasing, or when user needs to sync their stack with main.
---

# Stack Update

Updates the stack after a base branch is merged, rebasing dependent branches.

## When to Use

Use this skill when the user wants to:
- Update their stack after a PR was merged
- Rebase dependent branches onto a new base
- Sync their stack with main
- Fix branch dependencies after a merge
- Restack all branches in the stack

## Instructions

1. Parse the user's request to identify:
   - `merged-branch`: The branch that was just merged (optional, auto-detects if not provided)
   - `restack`: Whether to use Charcoal's restack feature (for rebasing entire stack)

2. Execute the appropriate command:

   **For post-merge updates:**
   ```bash
   ./scripts/stack update [merged-branch]
   ```

   **For restacking all branches (requires Charcoal):**
   ```bash
   ./scripts/stack restack
   ```

3. If scripts are not found, perform manually:
   - Fetch latest: `git fetch origin`
   - Update main: `git checkout main && git pull`
   - For each dependent branch:
     - Checkout: `git checkout <branch>`
     - Rebase: `git rebase main` (or new target)
     - Force push safely: `git push --force-with-lease`

4. Report results including:
   - Which branches were updated
   - Any conflicts encountered
   - New stack status

## Charcoal Restack

If Charcoal is installed, the `restack` command provides a simpler way to rebase all branches:

```bash
# Restack entire stack with one command
./scripts/stack restack
```

Benefits of Charcoal restack:
- Automatically rebases all branches in correct order
- Handles complex stack hierarchies
- Preserves commit history properly

To enable Charcoal:
```bash
brew install danerwilliams/tap/charcoal
./scripts/stack init
```

## Safety

- Always uses `--force-with-lease` to prevent overwriting others' changes
- Shows which branches will be updated before proceeding
- Reports conflicts clearly if they occur
- Syncs metadata between Charcoal and native format

## Examples

User: "Update the stack after feature/base merged"
Action: `./scripts/stack update feature/base`

User: "The base PR was merged, update dependent branches"
Action: `./scripts/stack update`

User: "Sync my stack with main"
Action: `./scripts/stack update`

User: "Rebase all my stacked branches"
Action: `./scripts/stack restack`

User: "My base branch was updated, restack everything"
Action: `./scripts/stack restack`

## Related Skills

- **stack-create**: Create new stacked branches
- **stack-navigate**: Move between branches (up/down)
- **stack-status**: View stack hierarchy
- **stack-merge**: Merge PR and update dependents
