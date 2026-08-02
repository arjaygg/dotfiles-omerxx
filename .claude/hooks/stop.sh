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

# Loop-breaker for the lifecycle branch below. task-gate.sh and git-pipeline-gate.sh
# each short-circuit on stop_hook_active, and git-pipeline-gate.sh additionally
# degrades after 2 denies per stage -- but the lifecycle branch returns before either
# script runs, so a lifecycle block has no way to stop repeating and simply recurs
# until the client's own block cap fires.
#
# stop_hook_active alone is not a sufficient breaker here: it is global across every
# registered Stop hook and does not identify which one blocked
# (plans/2026-07-25-agentic-git-pipeline.md L224-239). This mirrors
# git-pipeline-gate.sh instead -- a session-scoped counter keyed by block reason.
#
# Returns 0 to degrade (allow the Stop, loudly), 1 to keep blocking.
_lifecycle_degrade() {
    local _key="$1" _reason="$2" _session _state _count=0 _tmp
    _session="$(printf '%s' "$_INPUT" | jq -r '.session_id // "nosession"' 2>/dev/null || echo nosession)"
    case "$_session" in ''|*[!A-Za-z0-9._-]*) _session="nosession" ;; esac
    _state="/tmp/.claude-lifecycle-stop-${_session}"
    if [[ -f "$_state" ]]; then
        _count="$(jq -r --arg k "$_key" '.[$k] // 0' "$_state" 2>/dev/null || echo 0)"
        [[ "$_count" =~ ^[0-9]+$ ]] || _count=0
    fi
    if [[ "$_count" -ge 2 ]]; then
        echo "LIFECYCLE-STOP: degraded (2 blocks already issued for '${_key}' this session) -- ${_reason}" >&2
        osascript -e "display notification \"${_reason}\" with title \"lifecycle stop (degraded)\"" >/dev/null 2>&1 || true
        return 0
    fi
    _tmp="$(mktemp "${_state}.XXXXXX" 2>/dev/null || echo "${_state}.tmp")"
    if [[ -f "$_state" ]]; then
        jq --arg k "$_key" --argjson v "$((_count + 1))" '.[$k] = $v' "$_state" >"$_tmp" 2>/dev/null && mv "$_tmp" "$_state"
    else
        jq -n --arg k "$_key" --argjson v "$((_count + 1))" '{($k): $v}' >"$_tmp" 2>/dev/null && mv "$_tmp" "$_state"
    fi
    rm -f "$_tmp" 2>/dev/null || true
    return 1
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
# Only an exact rc=0 unbound envelope may fall back to the legacy gate.
_LIFECYCLE_BRIDGE="$SCRIPT_DIR/lifecycle-hook.sh"
_LIFECYCLE_VALIDATOR="$SCRIPT_DIR/lifecycle-envelope.py"
_LIFECYCLE_OUT=""
_LIFECYCLE_RC=1
if [[ -f "$_LIFECYCLE_BRIDGE" && -r "$_LIFECYCLE_BRIDGE"     && -f "$_LIFECYCLE_VALIDATOR" && -r "$_LIFECYCLE_VALIDATOR" ]]; then
    _LIFECYCLE_OUT="$(printf '%s' "$_INPUT" | bash "$_LIFECYCLE_BRIDGE" Stop 2>&3)"
    _LIFECYCLE_RC=$?
fi
_LIFECYCLE_BINDING=""
if [[ $_LIFECYCLE_RC -eq 0 && -n "$_LIFECYCLE_OUT" ]]; then
    _LIFECYCLE_BINDING="$(printf '%s' "$_LIFECYCLE_OUT"         | python3 "$_LIFECYCLE_VALIDATOR" Stop 2>/dev/null)"
fi
if [[ "$_LIFECYCLE_BINDING" == "bound" ]]; then
    _BOUND_BLOCK="$(printf '%s' "$_LIFECYCLE_OUT" | python3 -c '
import json, sys
value = json.load(sys.stdin)
if value.get("decision") == "block":
    print(json.dumps({"decision": "block", "reason": value["reason"]}, separators=(",", ":")))
')"
    if [[ -n "$_BOUND_BLOCK" ]]; then
        _BOUND_REASON="$(printf '%s' "$_BOUND_BLOCK" | jq -r '.reason' 2>/dev/null || echo 'lifecycle block')"
        if ! _lifecycle_degrade "bound:${_BOUND_REASON}" "$_BOUND_REASON"; then
            printf '%s\n' "$_BOUND_BLOCK"
        fi
    fi
    wait
    exit 0
fi
if [[ "$_LIFECYCLE_BINDING" != "unbound" ]]; then
    _FAIL_CLOSED_REASON='Lifecycle Stop bridge output was unavailable or invalid; failed closed.'
    if ! _lifecycle_degrade "invalid" "$_FAIL_CLOSED_REASON"; then
        jq -nc --arg reason "$_FAIL_CLOSED_REASON" '{"decision":"block","reason":$reason}'
    fi
    wait
    exit 0
fi

_GIT_GATE_OUT="$(printf '%s' "$_INPUT" | bash "$SCRIPT_DIR/git-pipeline-gate.sh" 2>&3)"
_rc=$?
[[ -n "$_GIT_GATE_OUT" ]] && printf '%s\n' "$_GIT_GATE_OUT"

wait
exit "$_rc"
