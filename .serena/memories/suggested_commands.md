# Suggested Commands

## Dotfiles Setup
```bash
# Deploy dotfiles via Stow (from ~/.dotfiles)
stow .

# Full machine setup (stow + all agent symlinks)
bash setup.sh
```

## AI Agent Stack
```bash
# Check pctx gateway servers
pctx mcp list -c ~/.config/pctx/pctx.json

# Verify Claude Code MCP
claude mcp list
```

## Branch Workflow
```bash
# Create stacked branch (use stack-create skill in Claude Code)
~/.dotfiles/.claude/scripts/stack create <branch-name> main

# Navigate stack
gt up / gt down

# Create PR (use stack-pr skill in Claude Code)
```

## Git
```bash
git status
git log --oneline -10
git diff HEAD
# NEVER commit directly to main — use stack create first
```

## Homebrew
```bash
brew bundle         # install all packages from Brewfile
brew bundle check   # verify everything is installed
```

## Stow
```bash
stow .              # symlink all dotfiles into ~/
stow -D .           # undo (remove) all symlinks
stow -n .           # dry run (preview what would be symlinked)
```
