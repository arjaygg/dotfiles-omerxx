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
# shellcheck source=_session-hub-lib.sh
source "$SCRIPT_DIR/_session-hub-lib.sh"

BASE_CWD="${1:-$(pwd)}"

# Resolve to MAIN repo root — handles the case where the selected session lives
# inside a .trees/ worktree. `git rev-parse --show-toplevel` returns the worktree
# path, not the main repo. `--absolute-git-dir` exposes the /worktrees/ segment.
resolve_repo_root() {
    local cwd="$1"
    local git_abs_dir
    git_abs_dir=$(git -C "$cwd" rev-parse --absolute-git-dir 2>/dev/null || echo "")
    if [[ -z "$git_abs_dir" ]]; then
        echo "$cwd"; return
    fi
    if [[ "$git_abs_dir" == *"/.git/worktrees/"* ]]; then
        # Strip /.git/worktrees/<name> → main repo root
        echo "${git_abs_dir%%/.git/worktrees/*}"
    else
        git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || echo "$cwd"
    fi
}

REPO_ROOT=$(resolve_repo_root "$BASE_CWD")

# ── Step 1: Prompt for task description ──────────────────────────────────────

task_desc=$(printf '' \
    | fzf \
        --print-query \
        --prompt="  Task description: " \
        --border \
        --border-label=" New Session " \
        --height=30% \
        --header="Describe the task (required) — this drives the worktree name via LLM  |  Esc to cancel" \
    2>/dev/null | head -1 || true)

# Require a description — blank = cancel (no silent fresh session)
if [[ -z "$task_desc" || "$task_desc" =~ ^[[:space:]]*$ ]]; then
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
window_name_trunc="${window_name:0:30}"
task_list_id=$(get_task_list_id "$worktree_path")
safe_path=$(printf '%s' "$worktree_path" | sed "s/'/'\\\\''/g")

# Check if we're in tmux; if so, check for existing window before creating
if [[ -n "$TMUX" ]]; then
    TMUX_SESSION=$(tmux display-message -p '#S' 2>/dev/null || true)
    if [[ -n "$TMUX_SESSION" ]]; then
        # Check if window already exists
        if tmux list-windows -t "$TMUX_SESSION" -F '#{window_name}' 2>/dev/null | grep -Fxq "$window_name_trunc"; then
            echo "Window '$window_name_trunc' already exists, switching to it..."
            tmux select-window -t "$TMUX_SESSION:$window_name_trunc" 2>/dev/null || true
            exit 0
        fi
    fi
fi

tmux new-window \
    -c "$worktree_path" \
    -n "$window_name_trunc" \
    bash -l -c "cd '$safe_path' && CLAUDE_CODE_TASK_LIST_ID='$task_list_id' claude --dangerously-skip-permissions; '$SCRIPT_DIR/claude-tmux-bridge.sh' session-stop"
