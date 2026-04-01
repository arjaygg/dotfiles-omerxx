#!/usr/bin/env bash
# PostToolUse: Log files read by Claude to ~/.claude/read-audit.log for audit purposes.
# Matcher: Read
# Exit: 0 always (pure tracking, no enforcement)

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_name', ''))
except:
    print('')
" 2>/dev/null || echo "")

# Guard: only apply to Read tool
if [[ "$TOOL_NAME" != "Read" ]]; then
  exit 0
fi

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

AUDIT_LOG="$HOME/.claude/read-audit.log"

# Ensure log directory exists
mkdir -p "$(dirname "$AUDIT_LOG")"

# Append timestamped entry
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) READ: $FILE_PATH" >> "$AUDIT_LOG"

exit 0
