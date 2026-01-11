#!/usr/bin/env bash
# Tmux script to open Claude in a worktree pane
# Usage: claude-worktree.sh [worktree-name]

set -e

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")
TREES_DIR="$REPO_ROOT/.trees"

# Function to list existing worktrees
list_worktrees() {
    if [ ! -d "$TREES_DIR" ]; then
        echo "No .trees directory found"
        return 1
    fi

    cd "$TREES_DIR"
    ls -1 2>/dev/null || echo "No worktrees found"
}

# Function to select worktree with fzf
select_worktree() {
    local worktree_name

    # Get list of worktrees
    if [ ! -d "$TREES_DIR" ]; then
        echo "No worktrees found. Use subagent to create one first."
        echo ""
        echo "Press any key to close..."
        read -n 1 -s
        return 1
    fi

    # Use fzf to select
    worktree_name=$(cd "$TREES_DIR" && ls -1 | fzf --prompt="Select worktree: " --height=40% --border --header="Choose a worktree to open in new pane")

    if [ -z "$worktree_name" ]; then
        return 1
    fi

    echo "$worktree_name"
}

# Main logic
main() {
    local worktree_name="$1"

    # If no argument, use fzf to select
    if [ -z "$worktree_name" ]; then
        worktree_name=$(select_worktree) || exit 0
    fi

    if [ -z "$worktree_name" ]; then
        exit 0
    fi

    local worktree_path="$TREES_DIR/$worktree_name"

    # Check if worktree exists
    if [ ! -d "$worktree_path" ]; then
        echo "Worktree not found: $worktree_path"
        echo "Available worktrees:"
        list_worktrees
        exit 1
    fi

    # Check if we're in a tmux session
    if [ -z "$TMUX" ]; then
        echo "Not in a tmux session"
        exit 1
    fi

    # Output the worktree path for tmux to capture
    echo "$worktree_path"
}

main "$@"
