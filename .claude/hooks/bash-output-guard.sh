#!/usr/bin/env bash
# PostToolUse: Warn when Bash output is large, suggest context-mode MCP tools
# Matcher: Bash
# Exit: 0 = pass, 2 = warn

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/hook-metrics.sh" 2>/dev/null || true
_HOOK_NAME="bash-output-guard"
_EXIT_CODE=$(hook_exit_code "$_HOOK_NAME" 2>/dev/null || echo 2)

# If enforcement is "off", skip all checks
[[ "$_EXIT_CODE" -eq 0 ]] && exit 0

INPUT=$(cat)

# Extract output text and command from tool response
IFS=$'\001' read -r LINE_COUNT CMD < <(
    echo "$INPUT" | python3 -c "
import sys, json
SEP = '\x01'
try:
    d = json.load(sys.stdin)
    ti = d.get('tool_input', {})
    command = ti.get('command', '')
    tr = d.get('tool_response', {})
    content = tr.get('content', d.get('content', ''))
    text = ''
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text += item.get('text', '')
    elif isinstance(content, str):
        text = content
    lines = text.count('\n') + (1 if text and not text.endswith('\n') else 0)
    print(SEP.join([str(lines), command]))
except:
    print(SEP.join(['0', '']))
" 2>/dev/null || printf '0\001'
)

# --- Skip known short-output commands ---
# git status, git branch, git log (short), make targets, etc.
if [[ "$CMD" == git\ status* || "$CMD" == git\ branch* || "$CMD" == git\ diff\ --stat* || "$CMD" == git\ log\ --oneline* || "$CMD" == ls* || "$CMD" == pwd* || "$CMD" == which* || "$CMD" == echo* ]]; then
    hook_metric "$_HOOK_NAME" "Bash" 0 2>/dev/null || true
    exit 0
fi

# --- Warn on large output ---
if [[ "$LINE_COUNT" -gt 200 ]]; then
    echo "OUTPUT WARNING: Bash produced $LINE_COUNT lines — significant context consumption." >&2
    echo "  For data-heavy commands, use context-mode MCP tools:" >&2
    echo "    mcp__context-mode__ctx_batch_execute — runs commands + auto-indexes output" >&2
    echo "    mcp__context-mode__ctx_execute — processes data in sandbox" >&2
    hook_metric "$_HOOK_NAME" "Bash" "$_EXIT_CODE" 2>/dev/null || true
    exit "$_EXIT_CODE"
elif [[ "$LINE_COUNT" -gt 50 ]]; then
    echo "OUTPUT HINT: Bash produced $LINE_COUNT lines. For commands with large output, consider context-mode MCP tools to keep raw data out of context." >&2
    hook_metric "$_HOOK_NAME" "Bash" "$_EXIT_CODE" 2>/dev/null || true
    exit "$_EXIT_CODE"
fi

hook_metric "$_HOOK_NAME" "Bash" 0 2>/dev/null || true
exit 0
