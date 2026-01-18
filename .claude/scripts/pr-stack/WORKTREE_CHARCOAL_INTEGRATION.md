# Charcoal + Worktrees Integration

## Overview

This integration gives you **the best of both worlds**:
- **Charcoal's powerful features**: Navigation (`gt up/down`), automatic restacking, visual stack display
- **Worktrees' parallel development**: Multiple isolated directories, work on different branches simultaneously

Previously, these were mutually exclusive. Now they work together seamlessly!

## The Problem We Solved

### Before:
- **Charcoal only**: Great navigation and restacking, but you can only work in one branch at a time
- **Worktrees only**: Parallel development, but manual navigation and no automatic restacking
- **Can't use both**: Charcoal manages checkouts, which conflicts with worktree creation

### After:
- ✅ Create worktrees that are tracked by Charcoal
- ✅ Use `stack up/down` to navigate between worktrees
- ✅ Use `stack restack` to rebase entire stack and sync all worktrees
- ✅ See worktree locations in `stack status`
- ✅ Work on multiple branches in parallel with full Charcoal capabilities

## How It Works

### Architecture

1. **Shared Charcoal Metadata**: Charcoal stores its stack information in `.git/.gt/`, which is shared across all worktrees
2. **Worktree Tracking**: When you create a worktree with `--worktree`, we also track it in Charcoal
3. **Worktree-Aware Commands**: Navigation commands detect if a branch has a worktree and cd there instead of checking out
4. **Sync on Restack**: After restacking, all worktrees are notified of changes

### Key Components

```
.claude/scripts/pr-stack/lib/
├── charcoal-compat.sh          # Charcoal detection and basic commands
├── worktree-charcoal.sh        # NEW: Worktree-aware Charcoal integration
└── validation.sh               # Shared validation functions

.claude/scripts/stack            # Main CLI (updated with worktree commands)
```

## Usage

### Creating Stacked Worktrees

```bash
# Create first feature with worktree
.claude/scripts/stack create feature/database main --worktree

# Create second feature stacked on first, also with worktree
.claude/scripts/stack create feature/api feature/database --worktree

# Create third feature stacked on second
.claude/scripts/stack create feature/ui feature/api --worktree
```

**Result:**
```
.trees/
├── database/    # feature/database branch
├── api/         # feature/api branch
└── ui/          # feature/ui branch
```

All three are tracked in Charcoal's stack!

### Navigating Between Worktrees

```bash
# From .trees/ui/, navigate to parent
.claude/scripts/stack up
# Output: cd .trees/api

# From .trees/api/, navigate to child
.claude/scripts/stack down
# Output: cd .trees/ui
```

**Note:** Since scripts can't change your shell's directory, the commands output the `cd` command. You can:
1. Copy and paste the output
2. Use: `eval $(.claude/scripts/stack up)`
3. Create a shell alias (see below)

### Viewing Stack with Worktree Info

```bash
.claude/scripts/stack status
```

**Output:**
```
╔════════════════════════════════════════════════════════════╗
║              STACK STATUS (with Worktrees)                 ║
╚════════════════════════════════════════════════════════════╝

main
├── feature/database [WT: .trees/database]
    └── feature/api [WT: .trees/api]
        └── feature/ui [WT: .trees/ui]
```

### Restacking with Worktrees

```bash
# After feature/database is merged to main
.claude/scripts/stack restack
```

**What happens:**
1. Runs `gt restack` in main repo
2. Rebases feature/api onto new main
3. Rebases feature/ui onto rebased feature/api
4. Notifies all worktrees of changes
5. Syncs metadata

### Adding Worktree to Existing Branch

```bash
# You created a branch without worktree
.claude/scripts/stack create feature/api main

# Later, you want a worktree for parallel development
.claude/scripts/stack worktree-add feature/api
```

**Result:** Worktree created at `.trees/api/`, Charcoal navigation still works!

### Managing Worktrees

```bash
# List all worktrees
.claude/scripts/stack worktree-list

# Remove a worktree (with safety checks)
.claude/scripts/stack worktree-remove .trees/api
```

## Shell Aliases (Recommended)

Add to your `.zshrc` or `.bashrc`:

```bash
# Stack management
alias st='~/.claude/scripts/stack'

# Worktree-aware navigation (auto-cd)
alias stup='eval $(~/.claude/scripts/stack up)'
alias stdown='eval $(~/.claude/scripts/stack down)'

# Quick status
alias stst='~/.claude/scripts/stack status'

# Worktree management
alias stwt='~/.claude/scripts/stack worktree-add'
alias stwls='~/.claude/scripts/stack worktree-list'
```

**Usage:**
```bash
st create feature/api main --worktree
cd .trees/api
stup              # Navigates to parent worktree
stdown            # Navigates back to child worktree
stst              # Shows stack with worktree info
```

## Complete Workflow Example

### Scenario: Building a full-stack feature in parallel

```bash
# 1. Setup: Create stacked worktrees
st create feature/database main --worktree
st create feature/api feature/database --worktree
st create feature/ui feature/api --worktree

# 2. Parallel Development (3 terminal windows)
# Terminal 1
cd .trees/database
# Work on database schema

# Terminal 2
cd .trees/api
# Work on API (can reference database code)

# Terminal 3
cd .trees/ui
# Work on UI (can reference API code)

# 3. View progress
st status
# Shows all three branches with worktree locations

# 4. Create PRs in order
st pr feature/database main "Add database schema"
st pr feature/api feature/database "Add API layer"
st pr feature/ui feature/api "Add UI components"

# 5. After database PR is merged
st restack
# Automatically rebases api and ui, syncs all worktrees

# 6. Continue working in parallel
# All worktrees are now up-to-date with the merged changes
```

## Advanced Features

### Worktree Detection

The system automatically detects if you're in a worktree:

```bash
# In main repo
st up              # Uses gt up (checkout)

# In worktree
st up              # Outputs cd command to parent worktree
```

### Mixed Workflow

You can mix worktrees and regular branches:

```bash
st create feature/database main --worktree    # Has worktree
st create feature/api feature/database        # No worktree
st create feature/ui feature/api --worktree   # Has worktree
```

Navigation adapts:
- From `feature/ui` worktree → `st up` → suggests creating worktree for `feature/api` or navigating in main repo
- From main repo on `feature/api` → `st up` → checks out `feature/database` worktree

### Config Copying

When creating worktrees, these are automatically copied:
- `.env` (if gitignored)
- `.vscode/` (if untracked)
- `.claude/` (if untracked)
- `.serena/` (if untracked)
- `.cursor/` (if untracked)
- `.mcp.json` (with updated paths)
- `.cursor/mcp.json` (with updated paths)

Each worktree gets its own IDE configuration!

## Troubleshooting

### Navigation doesn't change directory

**Problem:** Running `st up` shows a cd command but doesn't change directory.

**Solution:** Use `eval`:
```bash
eval $(st up)
```

Or create an alias:
```bash
alias stup='eval $(st up)'
```

### Worktree out of sync after restack

**Problem:** After `st restack`, worktree shows conflicts.

**Solution:**
```bash
cd .trees/<worktree>
git status
# If behind upstream:
git pull --rebase
```

### Can't remove worktree

**Problem:** `st worktree-remove` fails with "worktree contains modified or untracked files"

**Solution:**
```bash
cd .trees/<worktree>
git status
# Commit or stash changes
git add .
git commit -m "WIP"
# Then remove
st worktree-remove .trees/<worktree>
```

### Charcoal not tracking worktree branches

**Problem:** Created worktree but `st status` doesn't show it in Charcoal view.

**Solution:**
```bash
# Manually track in Charcoal
gt branch track <branch-name> --parent <parent-branch>

# Or recreate with --worktree flag
st worktree-remove .trees/<name>
st create <branch> <parent> --worktree
```

## Benefits Summary

| Feature | Worktrees Only | Charcoal Only | **Integrated** |
|---------|---------------|---------------|----------------|
| Parallel development | ✅ | ❌ | ✅ |
| Easy navigation | ❌ | ✅ | ✅ |
| Automatic restacking | ❌ | ✅ | ✅ |
| Visual stack display | ❌ | ✅ | ✅ |
| Multiple IDE windows | ✅ | ❌ | ✅ |
| PR stacking metadata | ✅ | ✅ | ✅ |
| Worktree-aware commands | ❌ | ❌ | ✅ |

## Requirements

- Git 2.5+ (for worktree support)
- Charcoal (install: `brew install danerwilliams/tap/charcoal`)
- jq (for JSON parsing, optional but recommended)

## Installation

The integration is already included in your `.claude/scripts/` setup. Just ensure Charcoal is installed and initialized:

```bash
# Install Charcoal
brew install danerwilliams/tap/charcoal

# Initialize in your repo
.claude/scripts/stack init

# Start using worktrees with Charcoal!
.claude/scripts/stack create feature/test main --worktree
```

## Future Enhancements

Potential improvements:
- [ ] Auto-sync worktrees on branch switch
- [ ] Worktree-specific git hooks
- [ ] IDE integration (auto-open worktrees in new windows)
- [ ] Worktree templates
- [ ] Bulk worktree operations

## Contributing

Found a bug or have a feature request? This is part of your dotfiles setup, so feel free to modify:
- Main integration: `.claude/scripts/pr-stack/lib/worktree-charcoal.sh`
- CLI updates: `.claude/scripts/stack`
- Skills: `.claude/skills/stack-create/SKILL.md`
