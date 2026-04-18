#!/usr/bin/env bash
# PostToolUse: Read — auto-delete session-handoff.md after it is consumed.
# Eliminates the per-prompt "HANDOFF AVAILABLE" injection that persists until the file is manually deleted.
set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

[[ "$TOOL_NAME" != "Read" ]] && exit 0
[[ -z "$FILE_PATH" ]] && exit 0

if [[ "$FILE_PATH" == *"plans/session-handoff.md" && -f "$FILE_PATH" ]]; then
    rm -f "$FILE_PATH"
    echo "[auto-cleanup] Deleted session-handoff.md — handoff context consumed, future prompts will be clean." >&2
fi
