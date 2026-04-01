#!/usr/bin/env bash
# PostToolUse: Track files that have been Read for edit-without-read validation.
# Matcher: Read
# Exit: 0 always (pure tracking, no enforcement)

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null)

[[ -z "$FILE_PATH" ]] && exit 0

READ_LOG="/tmp/.claude-read-log-$(id -u)"

# Append if not already tracked (dedup)
if ! grep -qF "$FILE_PATH" "$READ_LOG" 2>/dev/null; then
    echo "$FILE_PATH" >> "$READ_LOG"
fi

exit 0
