#!/usr/bin/env bash
# Outer fail-closed PreToolUse dispatcher for the lifecycle bridge.
set -uo pipefail

HOOK="$HOME/.dotfiles/.claude/hooks/lifecycle-hook.sh"
VALIDATOR="$HOME/.dotfiles/.claude/hooks/lifecycle-envelope.py"
INPUT="$(cat)"

deny() {
    printf '%s\n' '{"lifecycle_hook":{"schema_version":1,"processed":true,"event":"PreToolUse","binding":"bound","run_id":"outer-fail-closed"},"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"[HARD-BLOCK — DO NOT RETRY] Lifecycle hook bridge output was unavailable or invalid; failed closed."}}'
}

if [ ! -f "$HOOK" ] || [ ! -r "$HOOK" ] || [ ! -f "$VALIDATOR" ] || [ ! -r "$VALIDATOR" ]; then
    deny
    exit 0
fi

OUTPUT="$(printf '%s' "$INPUT" | bash "$HOOK" PreToolUse 2>/dev/null)"
RC=$?
if [ "$RC" -ne 0 ] || [ -z "$OUTPUT" ]; then
    deny
    exit 0
fi
if ! printf '%s' "$OUTPUT" | python3 "$VALIDATOR" PreToolUse >/dev/null 2>&1; then
    deny
    exit 0
fi
printf '%s\n' "$OUTPUT"
exit 0
