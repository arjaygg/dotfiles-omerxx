#!/usr/bin/env bash
# _session-hub-new.sh — New session flow for session-hub
#
# Creates a new Claude Code session with optional worktree.
# Uses LLM (claude --print --bare) for smart name suggestion with slug fallback.
#
# Args: $1 = base_cwd (repo root, passed from session-hub Alt-N via {4})
#
# Flow:
#   1. Prompt user for task description
#   2. Fire LLM name suggestion in background
#   3. Show slug fallback immediately; replace with LLM name if it arrives fast
#   4. User confirms or overrides the name
#   5. Create worktree + open Claude

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_CWD="${1:-$(pwd)}"

# Resolve to actual git root (handles worktree paths)
REPO_ROOT=$(git -C "$BASE_CWD" rev-parse --show-toplevel 2>/dev/null || echo "$BASE_CWD")

# ── Step 1: Prompt for task description ──────────────────────────────────────

task_desc=$(printf '' \
    | fzf \
        --print-query \
        --prompt="  Task (blank = fresh start): " \
        --border \
        --border-label=" New Session " \
        --height=30% \
        --header="Describe the task to get a smart worktree name  |  Leave blank for fresh session" \
    2>/dev/null | head -1 || true)

# If blank → fresh session in repo root, no worktree
if [[ -z "$task_desc" ]]; then
    name=$(basename "$REPO_ROOT")
    window_name="claude:${name:0:20}"
    tmux new-window \
        -c "$REPO_ROOT" \
        -n "${window_name:0:30}" \
        bash -l -c "cd '$(printf '%s' "$REPO_ROOT" | sed "s/'/'\\\\''/g")' && claude; '$SCRIPT_DIR/claude-tmux-bridge.sh' session-stop"
    exit 0
fi

# ── Step 2: Slug fallback + background LLM ───────────────────────────────────

slug_fallback=$(printf '%s' "$task_desc" \
    | iconv -t ascii//TRANSLIT 2>/dev/null \
    | tr '[:upper:]' '[:lower:]' \
    | tr -cs 'a-z0-9' '-' \
    | sed 's/-\+/-/g; s/^-//; s/-$//' \
    | cut -c1-35)

[[ -z "$slug_fallback" ]] && slug_fallback="new-session"

# Fire LLM in background
tmpfile=$(mktemp /tmp/session-hub-name.XXXXXX)
timeout 20 claude --print --bare \
    --model claude-haiku-4-5 \
    "Suggest a short 2-4 word kebab-case git branch name (no type prefix like feat/ or fix/) for this task: '$task_desc'. Reply with ONLY the name, no explanation." \
    > "$tmpfile" 2>/dev/null &
llm_pid=$!

# Brief wait — use LLM name if it finishes fast
sleep 1
if ! kill -0 "$llm_pid" 2>/dev/null; then
    # LLM finished — sanitize and use it
    llm_name=$(cat "$tmpfile" \
        | tr -d '\n' \
        | iconv -t ascii//TRANSLIT 2>/dev/null \
        | tr '[:upper:]' '[:lower:]' \
        | tr -cs 'a-z0-9' '-' \
        | sed 's/-\+/-/g; s/^-//; s/-$//' \
        | cut -c1-40)
    initial_name="${llm_name:-$slug_fallback}"
else
    initial_name="$slug_fallback"
fi
rm -f "$tmpfile"

# ── Step 3: Confirm or override name ─────────────────────────────────────────

final_name=$(printf '%s\n' "$initial_name" \
    | fzf \
        --print-query \
        --prompt="  Worktree name: " \
        --border \
        --border-label=" Name Worktree " \
        --height=30% \
        --header="Enter to accept · Type to override · (LLM suggestion may have arrived)" \
    2>/dev/null | head -1 || true)

[[ -z "$final_name" ]] && final_name="$initial_name"

# Final sanitize
final_name=$(printf '%s' "$final_name" \
    | tr '[:upper:]' '[:lower:]' \
    | tr -cs 'a-z0-9' '-' \
    | sed 's/-\+/-/g; s/^-//; s/-$//' \
    | cut -c1-40)

[[ -z "$final_name" ]] && final_name="new-session-$(date +%m%d%H%M)"

# ── Step 4: Create worktree ───────────────────────────────────────────────────

worktree_path="$REPO_ROOT/.trees/$final_name"

if [[ -d "$worktree_path" ]]; then
    # Worktree already exists — just open Claude there
    :
elif git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$final_name" 2>/dev/null; then
    # Branch exists, add worktree pointing to it
    git -C "$REPO_ROOT" worktree add "$worktree_path" "$final_name" 2>/dev/null || true
else
    # Fresh branch + worktree
    git -C "$REPO_ROOT" worktree add -b "$final_name" "$worktree_path" 2>/dev/null \
        || git -C "$REPO_ROOT" worktree add "$worktree_path" 2>/dev/null \
        || { echo "Failed to create worktree at $worktree_path" >&2; exit 1; }
fi

# ── Step 5: Open Claude in new worktree ──────────────────────────────────────

window_name="claude:${final_name:0:20}"

tmux new-window \
    -c "$worktree_path" \
    -n "${window_name:0:30}" \
    bash -l -c "cd '$(printf '%s' "$worktree_path" | sed "s/'/'\\\\''/g")' && claude; '$SCRIPT_DIR/claude-tmux-bridge.sh' session-stop"
