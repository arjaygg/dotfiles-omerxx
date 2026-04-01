#!/usr/bin/env bash
# claude-tmux-bridge.sh — Claude Code <-> tmux integration bridge
# All tmux communication from Claude Code hooks goes through this script.
# Exits silently (exit 0) when not inside tmux.

set -euo pipefail

# ── Guard: not in tmux → no-op ──────────────────────────────────────────────
[[ -n "${TMUX:-}" ]] || exit 0

ACTION="${1:-}"
shift || true

# ── Helpers ──────────────────────────────────────────────────────────────────
set_pane_var()   { tmux set -p @"$1" "$2" 2>/dev/null || true; }
unset_pane_var() { tmux set -pu @"$1" 2>/dev/null || true; }
get_pane_var()   { tmux display-message -p "#{@$1}" 2>/dev/null || echo ""; }

derive_project_name() {
    local dir="${1:-$(pwd)}"
    basename "$dir"
}

derive_branch() {
    local dir="${1:-$(pwd)}"
    git -C "$dir" branch --show-current 2>/dev/null || echo ""
}

abbreviate_branch() {
    local branch="$1"
    local max="${2:-8}"
    local stripped
    stripped=$(printf '%s' "$branch" | sed 's|^\(feat\|feature\|fix\|bugfix\|hotfix\|chore\|release\)/||')
    printf '%s' "${stripped:0:$max}"
}

derive_window_name() {
    local project="$1"
    local branch="$2"
    local worktree="${3:-}"

    local label="${worktree:-$project}"
    label="${label:0:10}"

    if [[ -n "$branch" ]]; then
        local short_branch
        short_branch=$(abbreviate_branch "$branch" 8)
        echo "claude:${label}[${short_branch}]"
    else
        echo "claude:${label}"
    fi
}

rename_window() { tmux rename-window "$1" 2>/dev/null || true; }

# ── Actions ──────────────────────────────────────────────────────────────────
case "$ACTION" in
    session-start)
        local_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
        project=$(derive_project_name "$local_dir")
        branch=$(derive_branch "$local_dir")

        # Store original window name for restoration on stop
        original=$(tmux display-message -p '#W' 2>/dev/null || echo "")
        set_pane_var "claude_prev_window_name" "$original"

        # Set state variables
        set_pane_var "claude_status" "idle"
        set_pane_var "claude_project" "$project"
        set_pane_var "claude_branch" "$branch"
        set_pane_var "claude_session_id" "${CLAUDE_SESSION_ID:-unknown}"

        # Rename window
        rename_window "$(derive_window_name "$project" "$branch")"
        ;;

    session-stop)
        # Restore original window name or re-enable automatic-rename
        prev=$(get_pane_var "claude_prev_window_name")
        if [[ -n "$prev" ]]; then
            rename_window "$prev"
        else
            tmux set-window-option automatic-rename on 2>/dev/null || true
        fi

        # Clear all Claude pane variables
        for var in claude_status claude_project claude_branch claude_session_id claude_worktree claude_prev_window_name claude_activity_start; do
            unset_pane_var "$var"
        done
        ;;

    activity-start)
        set_pane_var "claude_status" "working"
        set_pane_var "claude_activity_start" "$(date +%s)"
        ;;

    activity-stop)
        set_pane_var "claude_status" "idle"
        unset_pane_var "claude_activity_start"
        _notify_project=$(get_pane_var "claude_project")
        tmux display-message -d 2000 "✓ Claude: ${_notify_project:-done}"
        ;;

    worktree-enter)
        # Read worktree name from stdin JSON if available
        local_input=""
        if [[ ! -t 0 ]]; then
            local_input=$(cat)
        fi

        worktree_name=""
        if [[ -n "$local_input" ]]; then
            # Extract "name" field from JSON
            worktree_name=$(echo "$local_input" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name',''))" 2>/dev/null || echo "")
        fi

        if [[ -n "$worktree_name" ]]; then
            set_pane_var "claude_worktree" "$worktree_name"

            local_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
            project=$(derive_project_name "$local_dir")
            branch=$(derive_branch "$local_dir")

            rename_window "$(derive_window_name "$project" "$branch" "$worktree_name")"
        fi
        ;;

    worktree-exit)
        unset_pane_var "claude_worktree"

        # Revert to project-level window name
        local_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"
        project=$(derive_project_name "$local_dir")
        branch=$(derive_branch "$local_dir")

        rename_window "$(derive_window_name "$project" "$branch")"
        ;;

    *)
        # Unknown action — silent no-op
        ;;
esac

exit 0
