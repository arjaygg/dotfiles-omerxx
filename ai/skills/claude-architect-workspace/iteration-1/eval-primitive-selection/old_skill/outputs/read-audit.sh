#!/usr/bin/env bash
# PostToolUse: Log every file read by Claude to a persistent audit log.
# Matcher: Read
# Exit: 0 always (pure side-effect, no enforcement)
#
# Log format (one line per Read):
#   <ISO8601_UTC>  session=<id>  <absolute_file_path>
#
# Log location: ~/.claude/read-audit.log

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(python3 -c "
import sys, json
try:
    d = json.loads('''$INPUT''')
    ti = d.get('tool_input', {})
    print(ti.get('file_path', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

# Also try reading from stdin directly in case the here-string approach fails
if [[ -z "$FILE_PATH" ]]; then
    FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', {})
    print(ti.get('file_path', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")
fi

[[ -z "$FILE_PATH" ]] && exit 0

AUDIT_LOG="${HOME}/.claude/read-audit.log"

# Ensure the log file's parent directory exists (it always should, but be safe)
mkdir -p "$(dirname "$AUDIT_LOG")"

# Derive a stable session identifier.
# Claude Code sets CLAUDE_SESSION_ID in the hook environment when available.
# Fall back to the PID of the current shell's parent group as a session proxy.
SESSION_ID="${CLAUDE_SESSION_ID:-$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ' || echo "unknown")}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u +"%Y-%m-%dT%H:%M:%SZ")

printf '%s\tsession=%s\t%s\n' "$TIMESTAMP" "$SESSION_ID" "$FILE_PATH" >> "$AUDIT_LOG"

exit 0
