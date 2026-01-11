#!/usr/bin/env bash
# Claude worktree selector using fzf with execute action

set -e

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")
TREES_DIR="$REPO_ROOT/.trees"

# Check if .trees directory exists
if [ ! -d "$TREES_DIR" ]; then
    tmux display-message "No worktrees found. Create with git-worktree-tmux agent."
    exit 0
fi

# Get worktrees
cd "$TREES_DIR"
worktrees=$(ls -1 2>/dev/null)

if [ -z "$worktrees" ]; then
    tmux display-message "No worktrees in $TREES_DIR"
    exit 0
fi

# Use fzf with --bind to execute tmux command on selection
# Enter = Claude, Alt-C = Cursor Agent
ls -1 | fzf \
    --prompt="Select worktree: " \
    --height=40% \
    --border \
    --header="Enter: Claude | Alt-C: Cursor Agent" \
    --bind="enter:execute(tmux new-window -c '$TREES_DIR/{}' -n 'claude:{}' bash -l -c \"cd '$TREES_DIR/{}' && echo '📂 Worktree: {}' && echo '🌿 Branch: \\\$(git branch --show-current)' && echo '' && echo 'Starting Claude...' && exec \\\$HOME/.local/bin/claude --dangerously-skip-permissions\")+abort" \
    --bind="alt-c:execute(tmux new-window -c '$TREES_DIR/{}' -n 'cursor:{}' bash -l -c \"cd '$TREES_DIR/{}' && echo '📂 Worktree: {}' && echo '🌿 Branch: \\\$(git branch --show-current)' && echo '' && echo 'Starting Cursor Agent...' && exec \\\$HOME/.local/bin/cursor-agent --model gpt-5.2 -f\")+abort"
