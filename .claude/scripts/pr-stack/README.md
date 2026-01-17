# PR Stack Scripts

Automation scripts for managing stacked pull requests with Azure DevOps.

## Scripts Overview

### create-stack.sh
Creates a new branch in the PR stack based on another branch.

**Usage:**
```bash
./create-stack.sh <new-branch-name> [base-branch] [commit-message]
```

**Examples:**
```bash
# Create branch from main
./create-stack.sh feature/new-api main

# Create branch from another feature
./create-stack.sh feature/api-tests feature/new-api

# Create with initial commit
./create-stack.sh feature/ui feature/api "Initial UI setup"
```

**What it does:**
- Creates a new branch from the specified base
- Validates branch names and existence
- Updates stack tracking information
- Optionally creates an initial commit
- Shows next steps

---

### create-pr.sh
Creates a Pull Request in Azure DevOps.

**Usage:**
```bash
./create-pr.sh <source-branch> [target-branch] [title] [--draft]
```

**Examples:**
```bash
# Create PR targeting main
./create-pr.sh feature/new-api

# Create with custom title
./create-pr.sh feature/new-api main "Add user API endpoint"

# Create as draft
./create-pr.sh feature/ui feature/api "Add UI" --draft
```

**What it does:**
- Validates branches are pushed to remote
- Generates PR description with commits and dependencies
- Creates PR in Azure DevOps
- Marks dependencies for stacked PRs
- Stores PR information for tracking

**Requirements:**
- Azure CLI (`az`) installed and configured
- Azure DevOps extension for Azure CLI
- Authenticated to Azure DevOps organization

---

### list-stack.sh
Lists all branches in the current PR stack with status.

**Usage:**
```bash
./list-stack.sh [--verbose]
```

**Examples:**
```bash
# Basic view
./list-stack.sh

# Detailed view with commits and status
./list-stack.sh --verbose
```

**What it shows:**
- Tree visualization of stacked branches
- Current branch highlighted
- Number of commits ahead
- PR status (if created)
- Branch existence (local/remote)

**Example output:**
```
╔════════════════════════════════════════════════════════════╗
║                     PR STACK STATUS                        ║
╚════════════════════════════════════════════════════════════╝

main
├── feature/base-api [5 commits] → PR #12345 (ACTIVE)
│   └── feature/api-tests [3 commits] → PR #12346 (DRAFT)
│       └── feature/ui [2 commits] → NO PR
└── feature/refactor [4 commits] → PR #12347 (MERGED)

Summary:
  Total branches in stack: 4
  PRs created: 3
  Branches without PRs: 1
```

---

### update-stack.sh
Updates dependent branches after a base branch is merged.

**Usage:**
```bash
./update-stack.sh [merged-branch]
```

**Examples:**
```bash
# Update after specific branch merged
./update-stack.sh feature/base-api

# Interactive mode - prompts for branch
./update-stack.sh
```

**What it does:**
- Finds all branches that depend on the merged branch
- Rebases each dependent branch onto the merge target (usually main)
- Force-pushes updated branches (with --force-with-lease)
- Updates stack tracking to reflect new base branches
- Handles merge conflicts gracefully

**When to use:**
- After a PR is merged in Azure DevOps
- When you need to update dependent PRs to target main instead of the merged branch

---

### merge-stack.sh
Completes a PR merge and automatically updates the stack.

**Usage:**
```bash
./merge-stack.sh <pr-id>
```

**Examples:**
```bash
# Merge PR and update stack
./merge-stack.sh 12345
```

**What it does:**
1. Fetches PR information from Azure DevOps
2. Validates PR can be merged (build passed, approved, etc.)
3. Completes the PR merge
4. Updates local repository
5. Optionally deletes merged branch (local and remote)
6. Automatically runs `update-stack.sh` to update dependent branches

**Requirements:**
- Azure CLI with Azure DevOps extension
- PR must be approved and ready to merge
- Authenticated to Azure DevOps

---

## Configuration

### Azure DevOps Settings

Scripts are pre-configured for:
- **Organization**: `https://dev.azure.com/bofaz`
- **Project**: `Axos-Universal-Core`
- **Repository**: `auc-conversion`

To change these, edit the variables at the top of `create-pr.sh` and `merge-stack.sh`:

```bash
ORGANIZATION="https://dev.azure.com/your-org"
PROJECT="Your-Project-Name"
```

### Stack Tracking Files

Scripts maintain tracking information in:
- `.git/pr-stack-info` - Branch dependencies and creation time
- `.git/pr-created` - PR IDs and metadata

These files are automatically managed by the scripts.

## Workflow Example

### Scenario: Building a Feature in Stages

```bash
# Stage 1: Database Schema
./create-stack.sh feature/user-schema main "Add user schema"
# ... implement schema ...
git add .
git commit -m "feat: add user table schema"
./create-pr.sh feature/user-schema main "Add user database schema"

# Stage 2: API Layer
./create-stack.sh feature/user-api feature/user-schema "Add user API"
# ... implement API ...
git add .
git commit -m "feat: add user API endpoints"
./create-pr.sh feature/user-api feature/user-schema "Add user API endpoints"

# Stage 3: UI
./create-stack.sh feature/user-ui feature/user-api "Add user UI"
# ... implement UI ...
git add .
git commit -m "feat: add user profile page"
./create-pr.sh feature/user-ui feature/user-api "Add user profile UI" --draft

# Check status
./list-stack.sh --verbose

# After feature/user-schema PR is approved and merged
./merge-stack.sh 12345  # Automatically updates feature/user-api and feature/user-ui
```

## Prerequisites

1. **Git 2.5+** (for worktree support)
2. **Azure CLI**
   ```bash
   # Install (macOS)
   brew install azure-cli

   # Login
   az login
   ```
3. **Azure DevOps Extension**
   ```bash
   az extension add --name azure-devops
   ```
4. **Bash** (macOS/Linux) or Git Bash (Windows)

## Troubleshooting

### "Azure CLI not found"
Install Azure CLI: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

### "Branch does not exist"
Ensure you've pushed your branch:
```bash
git push -u origin <branch-name>
```

### "Failed to create PR"
Check Azure DevOps authentication:
```bash
az account show
az devops configure --list
```

### "Cannot rebase: you have unstaged changes"
Stash your changes first:
```bash
git stash
# Run update command
git stash pop
```

### "Remote already exists"
The script handles this, but if you see errors:
```bash
git remote remove origin
git remote add origin <url>
```

## Tips

1. **Use git aliases** for faster workflow:
   ```bash
   git config --global alias.stack-create '!f() { ./scripts/pr-stack/create-stack.sh "$@"; }; f'
   git config --global alias.stack-list '!./scripts/pr-stack/list-stack.sh'
   git config --global alias.stack-update '!./scripts/pr-stack/update-stack.sh'
   ```

2. **Check stack status regularly**:
   ```bash
   ./list-stack.sh
   ```

3. **Use --draft flag** for dependent PRs that aren't ready:
   ```bash
   ./create-pr.sh feature/my-feature feature/base --draft
   ```

4. **Keep PRs small**: Each PR should be reviewable in < 30 minutes

5. **Document dependencies**: Always note in PR description which PR it depends on

## Integration with AI Tools

These scripts work excellently with AI coding assistants:

- **Claude Code**: Can run scripts directly when you ask
  - "Create a stacked branch for my new feature"
  - "Show me my PR stack"

- **Cursor**: Use in terminal within Cursor

- **Windsurf**: Run from Cascade terminal

See [.claude/docs/pr-stacking.md](../../.claude/docs/pr-stacking.md) for AI-specific workflows.

## Support

For issues or questions:
1. Check [PR_STACKING_GUIDE.md](../../PR_STACKING_GUIDE.md)
2. Review script source for detailed comments
3. Contact team leads

## Contributing

When modifying scripts:
1. Test thoroughly with a test repository
2. Maintain backward compatibility
3. Update this README with any new functionality
4. Use consistent error handling and output formatting
