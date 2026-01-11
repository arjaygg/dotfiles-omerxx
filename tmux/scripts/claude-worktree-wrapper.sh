#!/usr/bin/env bash
# Wrapper script for claude-worktree that handles the pane splitting
# This runs outside the popup to properly split the pane

TEMP_FILE="/tmp/claude-worktree-selection-$$"

# Clean up temp file on exit
trap "rm -f '$TEMP_FILE'" EXIT

# Run the worktree selector in a popup and capture the selection
~/.dotfiles/tmux/scripts/claude-worktree.sh > "$TEMP_FILE"

# Read the selected worktree path
if [ -f "$TEMP_FILE" ] && [ -s "$TEMP_FILE" ]; then
    worktree_path=$(cat "$TEMP_FILE")
    worktree_name=$(basename "$worktree_path")

    # Now split the current pane and open Claude in the selected worktree
    tmux split-window -h -c "$worktree_path" "cd '$worktree_path' && echo '📂 Worktree: $worktree_name' && echo '🌿 Branch: \$(git branch --show-current)' && echo '' && exec claude"

    # Balance panes
    tmux select-layout even-horizontal
fi
