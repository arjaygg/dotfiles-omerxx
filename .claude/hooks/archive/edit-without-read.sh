#!/usr/bin/env bash
# PreToolUse: Warn when Edit targets a file not recently Read in this session.
# Matcher: Edit
# Exit: 0 = pass, configurable via hook-config.yaml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/hook-metrics.sh" 2>/dev/null || true
_HOOK_NAME="edit-without-read"
_EXIT_CODE=$(hook_exit_code "$_HOOK_NAME" 2>/dev/null || echo 2)

[[ "$_EXIT_CODE" -eq 0 ]] && exit 0

INPUT=$(cat)

IFS=$'\001' read -r TOOL_NAME FILE_PATH < <(
    echo "$INPUT" | python3 -c "
import sys, json
SEP = '\x01'
try:
    d = json.load(sys.stdin)
    tool_name = d.get('tool_name', '')
    ti = d.get('tool_input', {})
    file_path = ti.get('file_path', '')
    print(SEP.join([tool_name, file_path]))
except:
    print(SEP)
" 2>/dev/null || printf '\001'
)

[[ "$TOOL_NAME" != "Edit" ]] && exit 0
[[ -z "$FILE_PATH" ]] && exit 0

# Track reads in a session-scoped temp file
READ_LOG="/tmp/.claude-read-log-$(id -u)"

# Check if this file was recently Read (within the session)
if [[ -f "$READ_LOG" ]] && grep -qF "$FILE_PATH" "$READ_LOG" 2>/dev/null; then
    hook_metric "$_HOOK_NAME" "$TOOL_NAME" 0 2>/dev/null || true
    exit 0
fi

# File not in read log — warn
echo "BLOCKED: Editing '$FILE_PATH' without reading it first. Use Read (or Serena.getSymbolsOverview) to understand the file before editing."
hook_metric "$_HOOK_NAME" "$TOOL_NAME" "$_EXIT_CODE" 2>/dev/null || true
exit 1
