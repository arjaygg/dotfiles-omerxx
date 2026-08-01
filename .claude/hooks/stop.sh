#!/usr/bin/env bash
# Consolidated Stop dispatcher (R6, docs/plans/2026-07-08-reduce-context-redundancy.md)
# Extended (plan: plans/2026-07-25-agentic-git-pipeline.md, Step 3) with git-pipeline-gate.sh.
# Folds: session-end.sh, plan-completion-check.sh, feedback-capture.sh,
#        task-gate.sh, git-pipeline-gate.sh, lean-ctx hook observe (backgrounded).
#
# task-gate.sh and git-pipeline-gate.sh are the only sub-hooks that can emit a
# blocking Stop decision, and they run in that fixed order with first-deny-wins
# arbitration: if task-gate.sh already signaled a block (either the correct
# {"decision":"block",...} shape or task-gate.sh's known legacy
# {"hookSpecificOutput":{"permissionDecision":"deny",...}} shape -- a
# pre-existing bug tracked separately and not fixed here), that output wins
# verbatim and git-pipeline-gate.sh does not run at all. Otherwise
# git-pipeline-gate.sh's own stdout/exit code become this script's stdout/exit
# code, preserving its block semantics.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_INPUT="$(cat)"

exec 3>&2

_run() {
    local _script="$1"
    shift
    [[ -f "$_script" ]] || return 0
    printf '%s' "$_INPUT" | bash "$_script" "$@" 2>&3
}

_is_block() {
    [[ -z "$1" ]] && return 1
    echo "$1" | jq -e '(.decision == "block") or (.hookSpecificOutput.permissionDecision == "deny")' >/dev/null 2>&1
}

(printf '%s' "$_INPUT" | bash -lc 'lean-ctx hook observe' &>/dev/null) &

_run "$SCRIPT_DIR/session-end.sh"
_run "$SCRIPT_DIR/plan-completion-check.sh"
_run "$SCRIPT_DIR/feedback-capture.sh"

_TASK_GATE_OUT="$(printf '%s' "$_INPUT" | bash "$SCRIPT_DIR/task-gate.sh" 2>&3)"
_rc=$?

if _is_block "$_TASK_GATE_OUT"; then
    printf '%s\n' "$_TASK_GATE_OUT"
    wait
    exit "$_rc"
fi
[[ -n "$_TASK_GATE_OUT" ]] && printf '%s\n' "$_TASK_GATE_OUT"

# A validated bound lifecycle envelope supersedes the legacy pipeline gate.
# Disabled/non-repository and exact unbound Stop produce no bridge output.
if [[ ! -f "$SCRIPT_DIR/lifecycle-hook.sh" || ! -r "$SCRIPT_DIR/lifecycle-hook.sh" ]]; then
    printf '%s\n' '{"decision":"block","reason":"Lifecycle Stop bridge is unavailable; failed closed."}'
    wait
    exit 0
fi
_LIFECYCLE_OUT="$(_run "$SCRIPT_DIR/lifecycle-hook.sh" Stop)"
_rc=$?
if [[ -n "$_LIFECYCLE_OUT" ]]; then
    if printf '%s' "$_LIFECYCLE_OUT" | jq -e '
        (type == "object") and
        (.lifecycle_hook | type == "object") and
        ((.lifecycle_hook | keys | sort) == ["binding","event","processed","run_id","schema_version"]) and
        (.lifecycle_hook.schema_version == 1) and
        (.lifecycle_hook.processed == true) and
        (.lifecycle_hook.event == "Stop") and
        (.lifecycle_hook.binding == "bound") and
        (.lifecycle_hook.run_id | type == "string" and length > 0) and
        (
            ((keys | sort) == ["lifecycle_hook"]) or
            (
                ((keys | sort) == ["decision","lifecycle_hook","reason"]) and
                (.decision == "block") and
                (.reason | type == "string" and length > 0)
            )
        )
    ' >/dev/null 2>&1; then
        if _is_block "$_LIFECYCLE_OUT"; then
            printf '%s' "$_LIFECYCLE_OUT" | jq -c '{decision,reason}'
        fi
    else
        printf '%s
' '{"decision":"block","reason":"Lifecycle Stop envelope was malformed; failed closed."}'
    fi
    wait
    exit "$_rc"
fi

_GIT_GATE_OUT="$(printf '%s' "$_INPUT" | bash "$SCRIPT_DIR/git-pipeline-gate.sh" 2>&3)"
_rc=$?
[[ -n "$_GIT_GATE_OUT" ]] && printf '%s\n' "$_GIT_GATE_OUT"

wait
exit "$_rc"
