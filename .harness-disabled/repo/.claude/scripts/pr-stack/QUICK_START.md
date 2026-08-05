# Quick Start: Charcoal + Worktrees

## TL;DR

Use **Charcoal's navigation and restacking** with **worktrees for parallel development**!

## Prerequisites

**Charcoal is required** for all stack operations:

```bash
# Check if installed
gt --version

# If not installed
brew install danerwilliams/tap/charcoal
```

## Setup (One-time)

```bash
# Install Charcoal
brew install danerwilliams/tap/charcoal

# Initialize in your repo
.claude/scripts/stack init
```

## Basic Usage

### Create stacked worktrees

```bash
# Create three stacked branches, each in its own worktree
.claude/scripts/stack create feature/api main --worktree
.claude/scripts/stack create feature/ui feature/api --worktree
.claude/scripts/stack create feature/polish feature/ui --worktree
```

**Result:** Three directories for parallel development:
- `.trees/api/`
- `.trees/ui/`
- `.trees/polish/`

### Work in parallel

```bash
# Terminal 1
cd .trees/api
# Make changes to API

# Terminal 2
cd .trees/ui
# Make changes to UI

# Terminal 3
cd .trees/polish
# Polish the UI
```

### View your stack

```bash
.claude/scripts/stack status
```

**Output:**
```
main
├── feature/api [WT: .trees/api]
    └── feature/ui [WT: .trees/ui]
        └── feature/polish [WT: .trees/polish]
```

### Navigate between worktrees

```bash
# From .trees/polish/
.claude/scripts/stack up
# Outputs: cd .trees/ui

# Copy and paste, or use eval:
eval $(.claude/scripts/stack up)
```

### Restack after merge

```bash
# After feature/api is merged to main
.claude/scripts/stack restack
```

**What happens:**
- Rebases feature/ui onto new main
- Rebases feature/polish onto rebased feature/ui
- Syncs all worktrees automatically

## Recommended Aliases

Add to `.zshrc`:

```bash
alias st='~/.claude/scripts/stack'
alias stup='eval $(~/.claude/scripts/stack up)'
alias stdown='eval $(~/.claude/scripts/stack down)'
```

**Usage:**
```bash
st create feature/api main --worktree
cd .trees/api
stup              # Navigate to parent
stdown            # Navigate to child
st status         # View stack
st restack        # Rebase everything
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `st create <branch> [base] --worktree` | Create branch with worktree |
| `st up` | Navigate to parent branch/worktree |
| `st down` | Navigate to child branch/worktree |
| `st status` | Show stack with worktree info |
| `st restack` | Rebase stack and sync worktrees |
| `st worktree-add <branch>` | Add worktree to existing branch |
| `st worktree-list` | List all worktrees |
| `st worktree-remove <path>` | Remove a worktree |
| `st pr <branch> <target> "title"` | Create PR |

## Full Documentation

See [WORKTREE_CHARCOAL_INTEGRATION.md](./WORKTREE_CHARCOAL_INTEGRATION.md) for:
- Architecture details
- Advanced features
- Troubleshooting
- Complete workflow examples
