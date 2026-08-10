#!/usr/bin/env bash
# Claude worktree selector using Git's registered worktree paths.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

list_linked_worktrees() {
    git worktree list --porcelain 2>/dev/null |
        awk '
            function emit() {
                if (path != "" && path != primary) {
                    if (branch == "") {
                        branch = "detached"
                    }
                    printf "%s\t%s\n", path, branch
                }
                path = ""
                branch = ""
            }

            /^worktree / {
                emit()
                path = substr($0, 10)
                if (primary == "") {
                    primary = path
                }
                next
            }

            /^branch / {
                branch = substr($0, 8)
                sub(/^refs\/heads\//, "", branch)
                next
            }

            /^detached$/ {
                branch = "detached"
                next
            }

            /^$/ {
                emit()
            }

            END {
                emit()
            }
        ' |
        while IFS=$'\t' read -r worktree_path branch; do
            [[ -d "$worktree_path" ]] || continue
            printf '%s\t%s\t%s\n' "$worktree_path" "$(basename "$worktree_path")" "$branch"
        done
}

launch_claude() {
    local worktree_path="$1"
    local worktree_name="$2"

    tmux new-window \
        -c "$worktree_path" \
        -n "claude:${worktree_name:0:12}" \
        "bash -l -c 'printf \"📂 Worktree: %s\\n\" \"\$PWD\"; printf \"🌿 Branch: %s\\n\\n\" \"\$(git branch --show-current 2>/dev/null)\"; printf \"Starting Claude...\\n\"; unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT; \"\$HOME/.local/bin/claude\" --dangerously-skip-permissions; \"\$HOME/.dotfiles/tmux/scripts/claude-tmux-bridge.sh\" session-stop'"
}

launch_cursor_agent() {
    local worktree_path="$1"
    local worktree_name="$2"

    tmux new-window \
        -c "$worktree_path" \
        -n "cursor:${worktree_name:0:12}" \
        "bash -l -c 'printf \"📂 Worktree: %s\\n\" \"\$PWD\"; printf \"🌿 Branch: %s\\n\\n\" \"\$(git branch --show-current 2>/dev/null)\"; printf \"Starting Cursor Agent...\\n\"; exec \"\$HOME/.local/bin/cursor-agent\" --model gpt-5.2 -f'"
}

main() {
    if ! git rev-parse --is-inside-work-tree &>/dev/null; then
        printf 'No Git repository found from %s.\n\nPress Enter to close...' "$PWD"
        read -r
        exit 0
    fi

    local display_list
    display_list=$(list_linked_worktrees)

    if [[ -z "$display_list" ]]; then
        printf 'No linked Git worktrees are registered for this repository.\n\nPress Enter to close...'
        read -r
        exit 0
    fi

    local result
    result=$(printf '%s\n' "$display_list" |
        fzf \
            --prompt="Select worktree: " \
            --height=70% \
            --border \
            --delimiter=$'\t' \
            --with-nth=2,3,1 \
            --header="Enter: Claude | Alt-C: Cursor Agent | Alt-O: Cursor | Alt-W: Windsurf" \
            --expect=enter,alt-c,alt-o,alt-w ||
        true)

    [[ -n "$result" ]] || exit 0

    local key selected
    if [[ "$result" == *$'\n'* ]]; then
        key="${result%%$'\n'*}"
        selected="${result#*$'\n'}"
    else
        key="enter"
        selected="$result"
    fi
    [[ -n "$key" ]] || key="enter"

    local worktree_path worktree_name branch
    IFS=$'\t' read -r worktree_path worktree_name branch <<<"$selected"
    [[ -d "$worktree_path" ]] || exit 0

    case "$key" in
        alt-c)
            launch_cursor_agent "$worktree_path" "$worktree_name"
            ;;
        alt-o)
            "$SCRIPT_DIR/open-cursor.sh" "$worktree_path"
            ;;
        alt-w)
            "$SCRIPT_DIR/open-windsurf.sh" "$worktree_path"
            ;;
        *)
            launch_claude "$worktree_path" "$worktree_name"
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
