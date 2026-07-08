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
    [[ -f "$_script" ]] || return 0
    local _out
    _out="$(printf '%s' "$_INPUT" | bash "$_script" 2>&3)"
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
_run "$SCRIPT_DIR/supermemory-project-check.sh"
_run "$SCRIPT_DIR/model-availability-check.sh"

(printf '%s' "$_INPUT" | bash -lc 'lean-ctx hook observe' &>/dev/null) &

if [[ -n "$_COMBINED_CTX" ]]; then
    python3 -c "
import json, sys
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': sys.argv[1]}}))
" "$_COMBINED_CTX"
fi

wait
exit 0
