#!/usr/bin/env bash
# repo-launcher.sh — cross-repo launcher via zoxide + current worktrees
#
# Shows git repos from zoxide history + current repo's .trees/ worktrees.
# Keybindings:
#   Enter    → open Claude in new tmux window
#   Alt-O    → open in Cursor IDE
#   Alt-W    → open in Windsurf IDE
#   Esc      → close
#
# Bound to: Ctrl+A G  (tmux.conf)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Collect repos ─────────────────────────────────────────────────────────────
repos_list=""

# From zoxide: all tracked dirs that contain a .git directory
if command -v zoxide &>/dev/null; then
    while IFS= read -r dir; do
        [[ -d "${dir}/.git" ]] && repos_list="${repos_list}${dir}"$'\n'
    done < <(zoxide query -l 2>/dev/null | head -200)
fi

# Current repo's worktrees (.trees/)
if git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
    GIT_COMMON_DIR=$(git rev-parse --git-common-dir 2>/dev/null)
    REPO_ROOT=$(cd "$GIT_COMMON_DIR/.." && pwd)
    if [[ -d "$REPO_ROOT/.trees" ]]; then
        while IFS= read -r wt; do
            [[ -n "$wt" ]] && repos_list="${repos_list}${REPO_ROOT}/.trees/${wt}"$'\n'
        done < <(ls -1 "$REPO_ROOT/.trees" 2>/dev/null)
    fi
fi

# Deduplicate preserving frecency order (awk keeps first occurrence; sort -u would destroy it)
repos_list=$(printf '%s' "$repos_list" | awk '!seen[$0]++' | grep -v '^$' || true)

if [[ -z "$repos_list" ]]; then
    echo "No git repos found."
    echo ""
    echo "Tip: zoxide tracks directories you visit — cd into some repos first."
    read -r
    exit 0
fi

# Annotate with inline branch labels (tab-separated so {1} returns path in fzf bindings)
display_list=$(while IFS= read -r dir; do
    [[ -z "$dir" ]] && continue
    branch=$(git -C "$dir" branch --show-current 2>/dev/null || true)
    if [[ -n "$branch" ]]; then
        printf '%s\t[%s]\n' "$dir" "$branch"
    else
        printf '%s\n' "$dir"
    fi
done <<< "$repos_list")

# ── fzf picker ────────────────────────────────────────────────────────────────
selected=$(printf '%s\n' "$display_list" \
    | fzf \
        --prompt="  Open repo: " \
        --header="Enter: Claude · Alt-O: Cursor · Alt-W: Windsurf · Esc: close" \
        --border \
        --height=70% \
        --delimiter=$'\t' \
        --preview='
            echo "Branch: $(git -C {1} branch --show-current 2>/dev/null)"
            echo ""
            git -C {1} log --oneline --color=always -8 2>/dev/null || ls -1 {1}
        ' \
        --preview-window='right:45%:wrap' \
        --bind="alt-o:execute-silent($SCRIPT_DIR/open-cursor.sh {1})+abort" \
        --bind="alt-w:execute-silent($SCRIPT_DIR/open-windsurf.sh {1})+abort" \
    2>/dev/null || true)

[[ -z "$selected" ]] && exit 0

# Strip branch label (tab-separated suffix) to recover the bare path
selected=$(printf '%s' "$selected" | cut -f1)

name=$(basename "$selected")

tmux new-window \
    -c "$selected" \
    -n "claude:${name:0:12}" \
    bash -l -c "
        cd '$selected'
        echo '📂 $selected'
        echo '🌿 Branch: \$(git branch --show-current 2>/dev/null)'
        echo ''
        echo 'Starting Claude...'
        unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT
        \$HOME/.local/bin/claude
        \$HOME/.dotfiles/tmux/scripts/claude-tmux-bridge.sh session-stop
    "
