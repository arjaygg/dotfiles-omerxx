#!/usr/bin/env bash
# Consolidated Stop dispatcher (R6, docs/plans/2026-07-08-reduce-context-redundancy.md)
# Folds: session-end.sh, plan-completion-check.sh, feedback-capture.sh,
#        task-gate.sh, lean-ctx hook observe (backgrounded).
# task-gate.sh is the only sub-hook that can emit a blocking permissionDecision
# JSON on stdout; the other three only produce side effects / stderr warnings,
# so no JSON merge is needed — task-gate.sh runs last and its raw stdout/exit
# code become this script's stdout/exit code, preserving its block semantics.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_INPUT="$(cat)"

exec 3>&2

_run() {
    local _script="$1"
    [[ -f "$_script" ]] || return 0
    printf '%s' "$_INPUT" | bash "$_script" 2>&3
}

(printf '%s' "$_INPUT" | bash -lc 'lean-ctx hook observe' &>/dev/null) &

_run "$SCRIPT_DIR/session-end.sh"
_run "$SCRIPT_DIR/plan-completion-check.sh"
_run "$SCRIPT_DIR/feedback-capture.sh"

printf '%s' "$_INPUT" | bash "$SCRIPT_DIR/task-gate.sh"
_rc=$?

wait
exit "$_rc"
