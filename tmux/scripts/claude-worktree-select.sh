#!/usr/bin/env bash
# Claude worktree selector using fzf with execute action

set -e

# Find the main repository root (works even when inside a worktree)
if git rev-parse --is-inside-work-tree &>/dev/null; then
    # Get the common git directory (points to main repo's .git)
    GIT_COMMON_DIR=$(git rev-parse --git-common-dir 2>/dev/null)
    # Get the main repository root by going up from the common git dir
    REPO_ROOT=$(cd "$GIT_COMMON_DIR/.." && pwd)
else
    REPO_ROOT="$PWD"
fi

TREES_DIR="$REPO_ROOT/.trees"

# Debug: show what we found
echo "Repository root: $REPO_ROOT"
echo "Looking for worktrees in: $TREES_DIR"
echo ""

# Check if .trees directory exists
if [ ! -d "$TREES_DIR" ]; then
    echo "❌ No .trees directory found at $TREES_DIR"
    echo ""
    read -p "Press enter to close..."
    exit 0
fi

# Get worktrees
cd "$TREES_DIR" || {
    echo "❌ Failed to cd to $TREES_DIR"
    read -p "Press enter to close..."
    exit 1
}

worktrees=$(ls -1 2>/dev/null)

if [ -z "$worktrees" ]; then
    echo "❌ No worktrees found in $TREES_DIR"
    echo ""
    read -p "Press enter to close..."
    exit 0
fi

echo "Found worktrees:"
ls -1
echo ""

# Use fzf with --bind to execute tmux command on selection
# Enter = Claude, Alt-C = Cursor Agent (CLI), Alt-O = Open in Cursor (GUI), Alt-W = Open in Windsurf (GUI)
ls -1 | fzf \
    --prompt="Select worktree: " \
    --height=40% \
    --border \
    --header="Enter: Claude | Alt-C: Cursor Agent | Alt-O: Cursor | Alt-W: Windsurf" \
    --bind="enter:execute(tmux new-window -c '$TREES_DIR/{}' -n 'claude:{}' bash -l -c \"cd '$TREES_DIR/{}' && echo '📂 Worktree: {}' && echo '🌿 Branch: \\\$(git branch --show-current)' && echo '' && echo 'Starting Claude...' && exec \\\$HOME/.local/bin/claude --dangerously-skip-permissions\")+abort" \
    --bind="alt-c:execute(tmux new-window -c '$TREES_DIR/{}' -n 'cursor:{}' bash -l -c \"cd '$TREES_DIR/{}' && echo '📂 Worktree: {}' && echo '🌿 Branch: \\\$(git branch --show-current)' && echo '' && echo 'Starting Cursor Agent...' && exec \\\$HOME/.local/bin/cursor-agent --model gpt-5.2 -f\")+abort" \
    --bind="alt-o:execute($HOME/.dotfiles/tmux/scripts/open-cursor.sh '$TREES_DIR/{}')+abort" \
    --bind="alt-w:execute($HOME/.dotfiles/tmux/scripts/open-windsurf.sh '$TREES_DIR/{}')+abort"
