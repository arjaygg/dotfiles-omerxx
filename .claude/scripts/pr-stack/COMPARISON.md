# Workflow Comparison: Before vs After

## Before: Choose One or the Other

### Option A: Charcoal Only (No Worktrees)

```bash
# Setup
gt repo init --trunk main
gt branch create feature/api
gt branch create feature/ui

# Working
# ❌ Can only work on one branch at a time
gt down              # Switch to feature/ui
# Make changes
git commit -m "Update UI"
gt up                # Switch back to feature/api
# Make changes
git commit -m "Update API"

# Restacking
gt restack           # ✅ Easy and automatic

# Limitations:
# - Can't work on multiple branches simultaneously
# - Switching branches disrupts IDE state
# - Can't have multiple IDE windows open
# - Context switching overhead
```

### Option B: Worktrees Only (No Charcoal)

```bash
# Setup
git worktree add .trees/api -b feature/api main
git worktree add .trees/ui -b feature/ui feature/api

# Working
# ✅ Can work on multiple branches simultaneously
cd .trees/api
# Terminal 1: Make changes to API

cd .trees/ui
# Terminal 2: Make changes to UI

# Restacking
# ❌ Manual and error-prone
cd .trees/ui
git rebase feature/api
git push --force-with-lease

# Limitations:
# - Manual navigation (cd commands)
# - Manual restacking (error-prone)
# - No visual stack display
# - Hard to track dependencies
```

## After: Best of Both Worlds

### Integrated Workflow

```bash
# Setup
stack init                                          # Initialize Charcoal
stack create feature/api main --worktree           # Create with worktree + Charcoal
stack create feature/ui feature/api --worktree     # Stack on top

# Working
# ✅ Parallel development
cd .trees/api
# Terminal 1: Work on API

cd .trees/ui
# Terminal 2: Work on UI

# Navigation
# ✅ Charcoal-powered, worktree-aware
eval $(stack up)     # Navigate to parent worktree
eval $(stack down)   # Navigate to child worktree

# Visualization
# ✅ See stack with worktree locations
stack status
# Output:
# main
# ├── feature/api [WT: .trees/api]
#     └── feature/ui [WT: .trees/ui]

# Restacking
# ✅ Automatic across all worktrees
stack restack        # Rebases entire stack, syncs all worktrees

# Benefits:
# ✅ Parallel development
# ✅ Easy navigation
# ✅ Automatic restacking
# ✅ Visual stack display
# ✅ Multiple IDE windows
# ✅ No context switching
```

## Feature Comparison Matrix

| Feature | Charcoal Only | Worktrees Only | **Integrated** |
|---------|--------------|----------------|----------------|
| **Development** |
| Work on multiple branches simultaneously | ❌ | ✅ | ✅ |
| Multiple IDE windows | ❌ | ✅ | ✅ |
| No context switching | ❌ | ✅ | ✅ |
| Isolated working directories | ❌ | ✅ | ✅ |
| **Navigation** |
| Easy branch navigation | ✅ | ❌ | ✅ |
| Worktree-aware navigation | ❌ | ❌ | ✅ |
| One command to parent/child | ✅ | ❌ | ✅ |
| **Stack Management** |
| Automatic restacking | ✅ | ❌ | ✅ |
| Visual stack display | ✅ | ❌ | ✅ |
| Track dependencies | ✅ | ⚠️ Manual | ✅ |
| Sync after rebase | ✅ | ❌ | ✅ |
| **PR Workflow** |
| Create stacked PRs | ✅ | ✅ | ✅ |
| Update after merge | ✅ | ⚠️ Manual | ✅ |
| PR metadata tracking | ✅ | ✅ | ✅ |
| **Configuration** |
| Per-branch IDE settings | ❌ | ✅ | ✅ |
| MCP config per worktree | ❌ | ✅ | ✅ |
| Environment isolation | ❌ | ✅ | ✅ |

## Real-World Scenarios

### Scenario 1: Building a Full-Stack Feature

#### Before (Charcoal Only)

```bash
# Day 1: Work on database
gt branch create feature/database
# Make changes, commit
git push

# Day 2: Work on API (need to switch)
gt branch create feature/api
# Make changes, commit
git push

# Day 3: Work on UI (need to switch again)
gt branch create feature/ui
# Make changes, commit
git push

# Day 4: Database PR feedback
gt up
gt up                    # Navigate back to database
# Make changes
git commit --amend
git push --force-with-lease

# Now need to restack
gt down
git rebase feature/database
git push --force-with-lease
gt down
git rebase feature/api
git push --force-with-lease

# ❌ Lots of context switching
# ❌ Can't work on multiple layers simultaneously
# ❌ Manual restack coordination
```

#### After (Integrated)

```bash
# Day 1: Setup all layers at once
stack create feature/database main --worktree
stack create feature/api feature/database --worktree
stack create feature/ui feature/api --worktree

# Days 1-4: Work in parallel
# Terminal 1: cd .trees/database (work on DB)
# Terminal 2: cd .trees/api (work on API, reference DB code)
# Terminal 3: cd .trees/ui (work on UI, reference API code)

# Day 4: Database PR feedback
cd .trees/database
# Make changes
git commit --amend
git push --force-with-lease

# Restack everything automatically
stack restack

# ✅ No context switching
# ✅ Parallel development
# ✅ Automatic restack
```

### Scenario 2: Hotfix While Working on Feature

#### Before (Charcoal Only)

```bash
# Working on feature
gt branch create feature/new-ui
# Making changes...

# Urgent: Need to create hotfix
git stash                # Save current work
gt up                    # Back to main
gt branch create hotfix/security
# Fix issue
git commit -m "Security fix"
git push
# Create PR, wait for merge

# Back to feature
gt down
gt down
git stash pop

# ❌ Disrupts current work
# ❌ Need to stash/unstash
# ❌ Context switching
```

#### After (Integrated)

```bash
# Working on feature in .trees/new-ui/
# Making changes...

# Urgent: Need to create hotfix
# Open new terminal (don't disrupt current work)
stack create hotfix/security main --worktree
cd .trees/security
# Fix issue
git commit -m "Security fix"
git push
# Create PR, wait for merge

# Continue working on feature (never stopped!)
# Terminal 1 still in .trees/new-ui/ with all changes intact

# ✅ No disruption
# ✅ No stashing needed
# ✅ Parallel work
```

### Scenario 3: Code Review Feedback

#### Before (Worktrees Only)

```bash
# Stack: feature/api → feature/ui → feature/polish
# All in worktrees

# PR feedback on feature/api
cd .trees/api
# Make changes
git commit --amend
git push --force-with-lease

# Now need to rebase ui and polish
cd .trees/ui
git fetch origin feature/api
git rebase feature/api
# Resolve conflicts...
git push --force-with-lease

cd .trees/polish
git fetch origin feature/ui
git rebase feature/ui
# Resolve conflicts...
git push --force-with-lease

# ❌ Manual rebase chain
# ❌ Error-prone
# ❌ Easy to forget a step
```

#### After (Integrated)

```bash
# Stack: feature/api → feature/ui → feature/polish
# All in worktrees with Charcoal tracking

# PR feedback on feature/api
cd .trees/api
# Make changes
git commit --amend
git push --force-with-lease

# Restack everything automatically
stack restack

# ✅ One command
# ✅ Automatic propagation
# ✅ All worktrees synced
```

## Performance Comparison

### Switching Between Branches

| Operation | Charcoal Only | Worktrees Only | Integrated |
|-----------|--------------|----------------|------------|
| Switch to parent | `gt up` (~1s) | `cd ../parent` (~0s) | `eval $(stack up)` (~0s) |
| IDE state | ⚠️ Reloads | ✅ Preserved | ✅ Preserved |
| Uncommitted changes | ⚠️ Must stash | ✅ Isolated | ✅ Isolated |

### Restacking After Merge

| Operation | Charcoal Only | Worktrees Only | Integrated |
|-----------|--------------|----------------|------------|
| Commands needed | 1 (`gt restack`) | 3-5 (manual rebases) | 1 (`stack restack`) |
| Error handling | ✅ Automatic | ❌ Manual | ✅ Automatic |
| Worktree sync | N/A | ❌ Manual | ✅ Automatic |

### Initial Setup

| Operation | Charcoal Only | Worktrees Only | Integrated |
|-----------|--------------|----------------|------------|
| Create 3 stacked branches | 3 commands | 3 commands | 3 commands |
| Setup time | ~5s | ~10s (with config) | ~10s (with config) |
| Charcoal tracking | ✅ Automatic | ❌ None | ✅ Automatic |

## Migration Guide

### From Charcoal-Only to Integrated

```bash
# You have existing Charcoal branches
gt stack
# main
# ├── feature/api
#     └── feature/ui

# Add worktrees to existing branches
stack worktree-add feature/api
stack worktree-add feature/ui

# Now you have both!
stack status
# main
# ├── feature/api [WT: .trees/api]
#     └── feature/ui [WT: .trees/ui]
```

### From Worktrees-Only to Integrated

```bash
# You have existing worktrees
git worktree list
# .trees/api    feature/api
# .trees/ui     feature/ui

# Initialize Charcoal and import
stack init

# Track existing branches
gt branch track feature/api --parent main
gt branch track feature/ui --parent feature/api

# Sync metadata
stack sync

# Now you have both!
stack status
# main
# ├── feature/api [WT: .trees/api]
#     └── feature/ui [WT: .trees/ui]
```

## Conclusion

The integrated approach gives you:

1. **Parallel Development** from worktrees
2. **Easy Navigation** from Charcoal
3. **Automatic Restacking** from Charcoal
4. **Visual Stack Display** from Charcoal
5. **Worktree-Aware Commands** from integration layer

**You no longer have to choose!** Get the best of both worlds with a unified workflow.
