#!/usr/bin/env bash
# claude-task-launcher.sh — Interactive CLAUDE_CODE_TASK_LIST_ID picker for prefix+C
#
# Called by tmux display-popup. Receives the pane's current working path as $1.
# Presents three default choices + free-text entry via fzf, then opens a new
# tmux window with CLAUDE_CODE_TASK_LIST_ID set to the chosen value.

set -euo pipefail

PANE_PATH="${1:-$PWD}"
SENTINEL_NO_ID="[no task id]"

# Derive default candidates
branch=""
if git -C "$PANE_PATH" rev-parse --git-dir >/dev/null 2>&1; then
  branch=$(git -C "$PANE_PATH" branch --show-current 2>/dev/null || true)
  # Fallback for worktrees / detached HEAD: use directory basename
  [[ -z "$branch" ]] && branch=$(basename "$PANE_PATH")
fi
branch_slug="${branch#*/}"   # strip type prefix: feature/foo → foo
# Generate date-only ID with canonical cwd hash for uniqueness within day
# Canonicalize path (resolve symlinks, remove trailing slash) for consistent hashing with session-hub
canonical_path=$(cd "$PANE_PATH" 2>/dev/null && pwd || printf '%s' "$PANE_PATH")
cwd_hash=$(printf '%s' "$canonical_path" | python3 -c "import sys, hashlib; print(hashlib.md5(sys.stdin.read().encode()).hexdigest()[:8])" 2>/dev/null \
    || printf '%s' "$canonical_path" | md5sum | cut -d' ' -f1 | cut -c1-8 2>/dev/null \
    || printf '%x' "$$")
datetime_id="$(date +%Y-%m-%d)-$cwd_hash"

candidates=()
[[ -n "$branch_slug" ]] && candidates+=("$branch_slug")
candidates+=("$datetime_id")
candidates+=("$SENTINEL_NO_ID")

# fzf picker with --print-query so user can type a custom ID
chosen=$(printf '%s\n' "${candidates[@]}" \
    | fzf \
        --prompt="  Task list ID: " \
        --header="Enter: launch Claude · Esc: cancel · Type to enter custom ID" \
        --border \
        --height=40% \
        --no-sort \
        --print-query \
    2>/dev/null || true)

# fzf --print-query: line 1 = typed query, line 2 = selected item
query=$(printf '%s\n' "$chosen" | sed -n '1p')
selection=$(printf '%s\n' "$chosen" | sed -n '2p')

# Priority: explicit selection > typed query > abort
task_id="${selection:-$query}"
[[ -z "$task_id" ]] && exit 0

# Launch Claude in a new tmux window
if [[ "$task_id" == "$SENTINEL_NO_ID" ]]; then
    tmux new-window -c "$PANE_PATH" "claude --dangerously-skip-permissions"
else
    tmux new-window -c "$PANE_PATH" "export CLAUDE_CODE_TASK_LIST_ID='$task_id'; claude --dangerously-skip-permissions"
fi
