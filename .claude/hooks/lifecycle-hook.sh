#!/usr/bin/env bash
# Thin global Claude hook bridge to the stdlib lifecycle adapter.
set -uo pipefail

EVENT="${1:-}"
case "$EVENT" in
    PreToolUse|SessionStart|UserPromptSubmit|Stop) ;;
    *) exit 0 ;;
esac

ADAPTER="$HOME/.dotfiles/scripts/ai/lifecycle_adapter.py"
[ -f "$ADAPTER" ] || exit 0

INPUT="$(cat)"
printf '%s' "$INPUT" | python3 "$ADAPTER" hook --event "$EVENT" 2>/dev/null || exit 0
