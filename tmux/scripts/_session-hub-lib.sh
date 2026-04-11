#!/usr/bin/env bash
# _session-hub-lib.sh — Shared helpers for session-hub scripts
#
# Source this file from _session-hub-new.sh, _session-hub-handoff.sh,
# and session-hub.sh before calling any function defined here.

# ── get_task_list_id ──────────────────────────────────────────────────────────
# Returns a stable UUID for the given project directory.
# Stored in plans/.task-list-id — persists across sessions and is shared by
# all tmux panes/windows that open Claude in the same worktree directory.
# When a future feature spawns additional panes from an active session, they
# can call get_task_list_id with the same cwd to join the same task list.
get_task_list_id() {
    local proj_dir="$1"
    local id_file="$proj_dir/plans/.task-list-id"
    if [[ -f "$id_file" ]]; then
        cat "$id_file"
        return
    fi
    mkdir -p "$proj_dir/plans"
    local new_id
    new_id=$(python3 -c "import uuid; print(str(uuid.uuid4()))" 2>/dev/null \
        || printf '%s-%s' "$(date +%s%N 2>/dev/null || date +%s)" "$$")
    printf '%s' "$new_id" > "$id_file"
    printf '%s' "$new_id"
}

# ── claude_launch_cmd ─────────────────────────────────────────────────────────
# Emits the full `claude ...` command string with shared defaults applied:
#   - CLAUDE_CODE_TASK_LIST_ID set from plans/.task-list-id
#   - --dangerously-skip-permissions (override by setting SKIP_PERMISSIONS=0)
#
# Args:
#   $1 = cwd (project/worktree directory)
#   $2 = extra args (e.g. "--resume SESSION_ID"), may be empty
#
# Usage: eval "$(claude_launch_cmd "$cwd" "--resume $session_id")"
#   or embed in a bash -l -c string.
claude_launch_cmd() {
    local cwd="$1"
    local extra_args="${2:-}"
    local task_id
    task_id=$(get_task_list_id "$cwd")
    local skip_flag="--dangerously-skip-permissions"
    [[ "${SKIP_PERMISSIONS:-1}" == "0" ]] && skip_flag=""
    printf 'CLAUDE_CODE_TASK_LIST_ID=%s claude %s %s' \
        "$task_id" "$skip_flag" "$extra_args"
}
