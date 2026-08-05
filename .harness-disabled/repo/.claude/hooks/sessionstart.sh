#!/usr/bin/env bash
# Consolidated SessionStart dispatcher (R6, docs/plans/2026-07-08-reduce-context-redundancy.md)
# Folds: settings-symlink-guard.sh, session-init.sh, supermemory-project-check.sh,
#        model-availability-check.sh, lean-ctx hook observe (backgrounded).
# Replicates the _run/_bg contract from userpromptsubmit.sh: single stdin read,
# stderr passthrough via fd 3, and additionalContext JSON combining across
# sub-hooks (each may emit its own hookSpecificOutput.additionalContext blob).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_INPUT="$(cat)"
_COMBINED_CTX=""

exec 3>&2

_run() {
    local _script="$1"
    shift
    [[ -f "$_script" ]] || return 0
    local _out
    _out="$(printf '%s' "$_INPUT" | bash "$_script" "$@" 2>&3)"
    local _ctx
    _ctx="$(printf '%s' "$_out" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    c = d.get('hookSpecificOutput', {}).get('additionalContext', '')
    if c:
        print(c, end='')
except Exception:
    pass
" 2>/dev/null || true)"
    if [[ -n "$_ctx" ]]; then
        if [[ -n "$_COMBINED_CTX" ]]; then
            _COMBINED_CTX="${_COMBINED_CTX}
${_ctx}"
        else
            _COMBINED_CTX="$_ctx"
        fi
    fi
}

_run "$SCRIPT_DIR/settings-symlink-guard.sh"
_run "$SCRIPT_DIR/session-init.sh"
_LIFECYCLE_BRIDGE="$SCRIPT_DIR/lifecycle-hook.sh"
_LIFECYCLE_VALIDATOR="$SCRIPT_DIR/lifecycle-envelope.py"
_LIFECYCLE_OUT=""
_LIFECYCLE_RC=1
if [[ -f "$_LIFECYCLE_BRIDGE" && -r "$_LIFECYCLE_BRIDGE"     && -f "$_LIFECYCLE_VALIDATOR" && -r "$_LIFECYCLE_VALIDATOR" ]]; then
    _LIFECYCLE_OUT="$(printf '%s' "$_INPUT" | bash "$_LIFECYCLE_BRIDGE" SessionStart 2>&3)"
    _LIFECYCLE_RC=$?
fi
if [[ $_LIFECYCLE_RC -eq 0 && -n "$_LIFECYCLE_OUT" ]]     && printf '%s' "$_LIFECYCLE_OUT" | python3 "$_LIFECYCLE_VALIDATOR" SessionStart >/dev/null 2>&1; then
    _LIFECYCLE_CTX="$(printf '%s' "$_LIFECYCLE_OUT" | python3 -c '
import json, sys
value = json.load(sys.stdin)
print(value.get("hookSpecificOutput", {}).get("additionalContext", ""), end="")
' 2>/dev/null || true)"
    if [[ -n "$_LIFECYCLE_CTX" ]]; then
        [[ -n "$_COMBINED_CTX" ]] && _COMBINED_CTX+=$'\n'
        _COMBINED_CTX+="$_LIFECYCLE_CTX"
    fi
else
    [[ -n "$_COMBINED_CTX" ]] && _COMBINED_CTX+=$'\n'
    _COMBINED_CTX+="Lifecycle bridge output was unavailable or invalid; lifecycle mutation remains fail-closed."
fi
_run "$SCRIPT_DIR/supermemory-project-check.sh"
_run "$SCRIPT_DIR/model-availability-check.sh"

(printf '%s' "$_INPUT" | bash -lc 'lean-ctx hook observe' &>/dev/null) &

# R8c (2026-07-09): daily-gated hook graduation check. Backgrounded/silent —
# hook-graduate.sh mutates hook-config.yaml, not session context, so nothing
# here feeds additionalContext. Marker file caps it at once per day even
# across many session starts.
_GRAD_MARKER="/tmp/.claude-hook-graduate-last-run-$(id -u)"
if [[ ! -f "$_GRAD_MARKER" ]] || [[ -n "$(find "$_GRAD_MARKER" -mtime +1 2>/dev/null)" ]]; then
    (bash "$SCRIPT_DIR/hook-graduate.sh" &>/dev/null; touch "$_GRAD_MARKER") &
fi

if [[ -n "$_COMBINED_CTX" ]]; then
    python3 -c "
import json, sys
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': sys.argv[1]}}))
" "$_COMBINED_CTX"
fi

wait
exit 0
