#!/usr/bin/env bash
# PostToolUse: compact Bash output >300 lines
# Claude Code passes tool result as JSON on stdin:
# {"session_id":"...","tool_name":"Bash","tool_input":{...},"tool_response":{"content":[...]}}

set -euo pipefail

INPUT=$(cat)

# Extract tool name from top-level field
TOOL_NAME=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_name', ''))
except:
    pass
" 2>/dev/null || echo "")

# Extract stdout — tool_response.content is primary; fall back to legacy top-level content
OUTPUT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    tr = d.get('tool_response', {})
    content = tr.get('content', d.get('content', ''))
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                sys.stdout.write(item.get('text', ''))
                break
    elif isinstance(content, str):
        sys.stdout.write(content)
    else:
        sys.stdout.write(d.get('output', d.get('stdout', '')))
except:
    pass
" 2>/dev/null || true)

LINE_COUNT=$(echo "$OUTPUT" | wc -l | tr -d ' ')

if [[ "$LINE_COUNT" -gt 300 ]]; then
    HEAD=$(echo "$OUTPUT" | head -40)
    TAIL=$(echo "$OUTPUT" | tail -40)
    OMITTED=$(( LINE_COUNT - 80 ))

    COMPACTED=$(printf '%s\n\n... %d lines omitted (use grep/search to find specific content) ...\n\n%s' \
        "$HEAD" "$OMITTED" "$TAIL")

    # Emit compacted version via stdin (avoids shell arg injection with quotes/$vars/newlines)
    echo "$COMPACTED" | python3 -c "
import sys, json
text = sys.stdin.read()
print(json.dumps({'type': 'text', 'text': text}))
"
fi

# --- Batching reminder after pctx execute_typescript (max once per session) ---
REMINDER_FLAG="/tmp/.claude-pctx-reminder-$(id -u)"
if [[ "$TOOL_NAME" == "mcp__pctx__execute_typescript" ]] && [[ ! -f "$REMINDER_FLAG" ]]; then
    touch "$REMINDER_FLAG"
    echo "BATCH CHECK: Was this the only Serena/MCP operation needed this turn? If 2+ ops are coming, combine them into one execute_typescript call." >&2
fi

exit 0
