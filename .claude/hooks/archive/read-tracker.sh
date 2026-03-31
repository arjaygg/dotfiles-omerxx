#!/usr/bin/env bash
# PostToolUse: Track files that have been Read for edit-without-read validation.
# Matcher: Read
# Exit: 0 always (pure tracking, no enforcement)

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', {})
    print(ti.get('file_path', ''))
except:
    print('')
" 2>/dev/null || echo "")

[[ -z "$FILE_PATH" ]] && exit 0

READ_LOG="/tmp/.claude-read-log-$(id -u)"

# Append if not already tracked (dedup)
if ! grep -qF "$FILE_PATH" "$READ_LOG" 2>/dev/null; then
    echo "$FILE_PATH" >> "$READ_LOG"
fi

exit 0
