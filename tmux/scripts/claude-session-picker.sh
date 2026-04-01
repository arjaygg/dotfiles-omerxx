#!/usr/bin/env bash
# claude-session-picker.sh — Live Claude session switcher
#
# Shows all tmux panes that have an active Claude Code session (@claude_status set).
# Fallback: if no active sessions exist, launches the worktree selector instead.
#
# Keybindings (inside picker):
#   Enter   → switch to that pane
#   Alt-K   → send Ctrl-C to the selected pane (interrupt current task)
#   Alt-W   → open worktree launcher (claude-worktree-select.sh)
#   Esc/q   → close
#
# Bound to: Ctrl+A w  (tmux.conf)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKTREE_SELECT="$SCRIPT_DIR/claude-worktree-select.sh"

# ── Build pane list ──────────────────────────────────────────────────────────
# Fields (tab-separated): TARGET STATUS PROJECT BRANCH WORKTREE SESSION WINDOW
pane_data=$(tmux list-panes -a \
    -F '#{session_name}:#{window_index}.#{pane_index}	#{@claude_status}	#{@claude_project}	#{@claude_branch}	#{@claude_worktree}	#{session_name}	#{window_name}	#{@claude_activity_start}' \
    2>/dev/null || true)

# Filter to only panes with @claude_status set (non-empty)
active_panes=$(printf '%s\n' "$pane_data" | awk -F'\t' '$2 != ""')

if [[ -z "$active_panes" ]]; then
    # No active Claude sessions — fall through to worktree launcher
    if [[ -x "$WORKTREE_SELECT" ]]; then
        exec bash "$WORKTREE_SELECT"
    else
        printf 'No active Claude sessions found.\n\nPress Enter to close...'
        read -r
        exit 0
    fi
fi

# ── Format display lines ─────────────────────────────────────────────────────
# Output: "TARGET  ICON  PROJECT[BRANCH]  [wt:WORKTREE]  (session)"
display_list=$(printf '%s\n' "$active_panes" | awk -F'\t' '{
    target  = $1
    status  = $2
    project = $3
    branch  = ($4 != "") ? "[" $4 "]" : ""
    wt      = ($5 != "") ? "  wt:" $5 : ""
    sess    = $6
    start   = $8
    elapsed = ""
    if (start != "" && status == "working") {
        diff = systime() - start + 0
        if (diff < 60) elapsed = " " diff "s"
        else elapsed = " " int(diff/60) "m"
    }
    icon    = (status == "working") ? "⚙" : "·"
    printf "%-22s  %s  %-20s%s%s  (%s)\n", target, icon, project branch, wt, elapsed, sess
}')

# ── fzf picker ───────────────────────────────────────────────────────────────
_rebuild_list() {
    tmux list-panes -a \
        -F '#{session_name}:#{window_index}.#{pane_index}	#{@claude_status}	#{@claude_project}	#{@claude_branch}	#{@claude_worktree}	#{session_name}	#{window_name}	#{@claude_activity_start}' \
        2>/dev/null \
    | awk -F'\t' '$2 != "" {
        target  = $1; status = $2; project = $3
        branch  = ($4 != "") ? "[" $4 "]" : ""
        wt      = ($5 != "") ? "  wt:" $5 : ""
        sess    = $6
        start   = $8
        elapsed = ""
        if (start != "" && status == "working") {
            diff = systime() - start + 0
            if (diff < 60) elapsed = " " diff "s"
            else elapsed = " " int(diff/60) "m"
        }
        icon    = (status == "working") ? "⚙" : "·"
        printf "%-22s  %s  %-20s%s%s  (%s)\n", target, icon, project branch, wt, elapsed, sess
    }'
}
export -f _rebuild_list

selected=$(printf '%s\n' "$display_list" \
    | fzf \
        --prompt="  Claude sessions: " \
        --header="Enter: switch · Alt-K: interrupt · Alt-W: worktrees · Esc: close" \
        --border \
        --height=70% \
        --ansi \
        --no-sort \
        --preview='
            target=$(printf "%s" {} | awk "{print \$1}")
            printf "\033[1;34m── Pane: %s ──\033[0m\n" "$target"
            tmux capture-pane -p -t "$target" -e 2>/dev/null | tail -25
        ' \
        --preview-window='right:50%:wrap' \
        --bind='alt-k:execute-silent(
            target=$(printf "%s" {} | awk "{print \$1}")
            tmux send-keys -t "$target" C-c
        )+reload(bash -c _rebuild_list)' \
        --bind="alt-w:execute(bash \"$WORKTREE_SELECT\")+abort" \
    2>/dev/null || true)

[[ -z "$selected" ]] && exit 0

# Extract target pane address (first field)
target=$(printf '%s' "$selected" | awk '{print $1}')
[[ -z "$target" ]] && exit 0

# Switch to the selected pane
tmux switch-client -t "$target" 2>/dev/null || true
