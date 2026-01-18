# PR Stack Scripts with Charcoal + Worktrees Integration

A unified CLI for managing stacked PRs with full Charcoal integration and worktree support for parallel development.

## ⚠️ Requirements

**Charcoal is required** - this tooling is designed around Charcoal's stack management capabilities:

```bash
# Required
brew install danerwilliams/tap/charcoal

# Also required
az extension add --name azure-devops  # Azure CLI DevOps extension

# Optional but recommended
brew install jq  # Better JSON parsing
```

**Why Charcoal is required:**
- Automatic stack rebasing and dependency resolution
- Branch relationship tracking
- Worktree-aware navigation
- Conflict handling

Without Charcoal, you'd need ~200 lines of complex manual rebase logic that's error-prone and hard to maintain.

## 🎯 What This Gives You

Get **all** of these capabilities simultaneously:

- ✅ **Parallel Development**: Work on multiple branches at the same time in separate directories
- ✅ **Easy Navigation**: Use `stack up/down` to move between branches (worktree-aware)
- ✅ **Automatic Restacking**: One command to rebase entire stack and sync all worktrees
- ✅ **Visual Stack Display**: See your PR stack with worktree locations
- ✅ **PR Stacking**: Create dependent PRs with proper base branches
- ✅ **IDE Isolation**: Each worktree gets its own configuration

## 🚀 Quick Start

### Installation

```bash
# Install Charcoal
brew install danerwilliams/tap/charcoal

# Initialize in your repo
cd /path/to/your/repo
~/.claude/scripts/stack init
```

### Create Your First Stack

```bash
# Create three stacked branches with worktrees
stack create feature/api main --worktree
stack create feature/ui feature/api --worktree
stack create feature/polish feature/ui --worktree

# Result: Three directories for parallel development
# .trees/api/
# .trees/ui/
# .trees/polish/
```

### Work in Parallel

```bash
# Terminal 1
cd .trees/api
# Work on API

# Terminal 2
cd .trees/ui
# Work on UI (can reference API code)

# Terminal 3
cd .trees/polish
# Polish the UI (can reference both)
```

### View Your Stack

```bash
stack status

# Output:
# main
# ├── feature/api [WT: .trees/api]
#     └── feature/ui [WT: .trees/ui]
#         └── feature/polish [WT: .trees/polish]
```

### Navigate Between Worktrees

```bash
# From .trees/polish/
eval $(stack up)      # Navigate to .trees/ui/
eval $(stack down)    # Navigate back to .trees/polish/
```

### Restack After Changes

```bash
# After feature/api is merged or updated
stack restack

# Automatically:
# - Rebases feature/ui onto new feature/api
# - Rebases feature/polish onto new feature/ui
# - Syncs all worktrees
```

## 📚 Documentation

- **[QUICK_START.md](./QUICK_START.md)** - Get started in 5 minutes
- **[WORKTREE_CHARCOAL_INTEGRATION.md](./WORKTREE_CHARCOAL_INTEGRATION.md)** - Complete integration guide
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Technical architecture and design
- **[COMPARISON.md](./COMPARISON.md)** - Before vs After comparison

## 🎨 Commands Reference

### Branch Management

```bash
stack create <branch> [base] [--worktree]  # Create stacked branch
stack up                                   # Navigate to parent (worktree-aware)
stack down [index]                         # Navigate to child (worktree-aware)
stack restack                              # Rebase entire stack
```

### Worktree Management

```bash
stack worktree-add <branch>      # Add worktree to existing branch
stack worktree-list              # List all worktrees
stack worktree-remove <path>     # Remove a worktree
```

### PR Management

```bash
stack pr <branch> <target> "title"  # Create PR
stack merge <pr-id>                 # Merge PR and update stack
stack update [merged-branch]        # Update stack after merge
```

### Status & Info

```bash
stack status     # Show stack with worktree info
stack init       # Initialize Charcoal
stack sync       # Sync metadata
```

## 🔧 Recommended Aliases

Add to your `.zshrc`:

```bash
# Stack management
alias st='~/.claude/scripts/stack'
alias stup='eval $(~/.claude/scripts/stack up)'
alias stdown='eval $(~/.claude/scripts/stack down)'
alias stst='~/.claude/scripts/stack status'

# Worktree management
alias stwt='~/.claude/scripts/stack worktree-add'
alias stwls='~/.claude/scripts/stack worktree-list'
```

## 💡 Use Cases

### Full-Stack Feature Development

```bash
# Create layers
st create feature/database main --worktree
st create feature/api feature/database --worktree
st create feature/ui feature/api --worktree

# Work on all layers simultaneously
# Terminal 1: Database schema
# Terminal 2: API implementation
# Terminal 3: UI components

# After database PR feedback
cd .trees/database
# Make changes
git commit --amend && git push -f

# Restack everything
st restack  # API and UI automatically rebased
```

### Hotfix While Working on Feature

```bash
# Working on feature in .trees/new-feature/
# Urgent hotfix needed

# Create hotfix in new worktree (doesn't disrupt current work)
st create hotfix/security main --worktree
cd .trees/security
# Fix, commit, push

# Continue working on feature (never stopped!)
```

### Experimental Branches

```bash
# Create experimental branch
st create experiment/new-approach feature/api --worktree

# Try new approach in .trees/new-approach/
# Keep working on main approach in .trees/api/

# If experiment works, merge it
# If not, just remove the worktree
st worktree-remove .trees/new-approach
```

## 🏗️ Architecture

```
Main Repo
├── .git/
│   ├── .gt/              # Charcoal metadata (shared)
│   ├── pr-stack-info     # PR stack metadata (shared)
│   └── worktrees/        # Worktree metadata (shared)
├── .trees/
│   ├── api/              # Worktree for feature/api
│   ├── ui/               # Worktree for feature/ui
│   └── polish/           # Worktree for feature/polish
└── ...

All worktrees share Charcoal metadata!
Navigation and restacking work across all worktrees!
```

## 🔄 How It Works

1. **Create worktree**: Native git creates isolated directory
2. **Track in Charcoal**: `gt branch track` registers the branch
3. **Navigate**: Commands detect worktrees and cd there
4. **Restack**: Charcoal rebases, then syncs all worktrees
5. **Metadata**: Kept in sync between Charcoal and native format

See [ARCHITECTURE.md](./ARCHITECTURE.md) for details.

## 🆚 Comparison

| Feature | Before | After |
|---------|--------|-------|
| Parallel development | ❌ | ✅ |
| Easy navigation | ⚠️ Charcoal only | ✅ |
| Automatic restacking | ⚠️ Charcoal only | ✅ |
| Multiple IDE windows | ⚠️ Worktrees only | ✅ |
| Visual stack display | ⚠️ Charcoal only | ✅ |

See [COMPARISON.md](./COMPARISON.md) for detailed comparison.

## 🐛 Troubleshooting

### Navigation doesn't change directory

**Problem:** `stack up` shows a cd command but doesn't change directory.

**Solution:** Use `eval $(stack up)` or create an alias:
```bash
alias stup='eval $(stack up)'
```

### Worktree out of sync after restack

**Problem:** Worktree shows conflicts after restack.

**Solution:**
```bash
cd .trees/<worktree>
git pull --rebase
```

### Can't remove worktree

**Problem:** Uncommitted changes prevent removal.

**Solution:**
```bash
cd .trees/<worktree>
git add . && git commit -m "WIP"
# Then remove
stack worktree-remove .trees/<worktree>
```

## 📦 Requirements

- Git 2.5+ (for worktree support)
- Charcoal (`brew install danerwilliams/tap/charcoal`)
- jq (optional, for better JSON parsing)
- Bash 4.0+

## 🤝 Integration with Claude Code

This system integrates with Claude Code skills:

- **stack-create**: Creates branches with worktrees
- **stack-navigate**: Worktree-aware navigation
- **stack-status**: Shows stack with worktree info
- **stack-pr**: Creates PRs from any worktree
- **stack-update**: Updates and syncs worktrees

Claude understands the full workflow and can guide you through it!

## 📝 License

Part of your dotfiles setup. Modify as needed!

## 🙏 Credits

- **Charcoal**: [danerwilliams/charcoal](https://github.com/danerwilliams/charcoal)
- **Git Worktrees**: Git core feature
- **Integration**: Custom implementation for seamless workflow

---

**Get started now:**
```bash
stack init
stack create feature/my-feature main --worktree
cd .trees/my-feature
# Start coding! 🚀
```
