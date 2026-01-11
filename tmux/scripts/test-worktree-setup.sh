#!/usr/bin/env bash
# Test worktree setup is complete

echo "🔍 Checking Worktree Setup..."
echo ""

# Check subagent
if [ -f ~/.dotfiles/.claude/agents/git-worktree-tmux.md ]; then
    echo "✅ Subagent: git-worktree-tmux.md found"
else
    echo "❌ Subagent: NOT FOUND"
fi

# Check tmux script
if [ -x ~/.dotfiles/tmux/scripts/claude-worktree.sh ]; then
    echo "✅ Tmux script: claude-worktree.sh found and executable"
else
    echo "❌ Tmux script: NOT FOUND or not executable"
fi

# Check tmux config has keybinding
if grep -q "claude-worktree.sh" ~/.dotfiles/tmux/tmux.conf; then
    echo "✅ Keybinding: Configured in tmux.conf"
else
    echo "❌ Keybinding: NOT FOUND in tmux.conf"
fi

# Check if in tmux
if [ -n "$TMUX" ]; then
    echo "✅ Tmux: Currently in tmux session"
else
    echo "⚠️  Tmux: Not currently in tmux (start with: tmux)"
fi

# Check if in git repo
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "✅ Git repo: Currently in a git repository"

    # Check for .trees in gitignore
    if grep -q "^.trees/" .gitignore 2>/dev/null; then
        echo "✅ Gitignore: .trees/ already in .gitignore"
    else
        echo "⚠️  Gitignore: .trees/ not in .gitignore (will be added by subagent)"
    fi
else
    echo "⚠️  Git repo: Not in a git repository"
fi

echo ""
echo "📋 Test Commands:"
echo "1. In Claude: 'Create a worktree for test-feature'"
echo "2. Keybinding: Ctrl+A w (if worktrees exist)"
echo "3. Manual: ~/.dotfiles/tmux/scripts/claude-worktree.sh"
