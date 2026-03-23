#!/usr/bin/env bash
# PostToolUse: compact Bash output >300 lines
# Claude Code passes tool result as JSON on stdin

set -euo pipefail

INPUT=$(cat)

# --- context-mode evaluation ---
if [[ "${CONTEXT_EVAL_MODE:-baseline}" == "context-mode" ]]; then
    # Try to locate the context-mode hook script
    CONTEXT_MODE_HOOK=$(find ~/.npm/_npx -path "*/node_modules/context-mode/hooks/posttooluse.mjs" 2>/dev/null | head -n 1 || true)

    if [[ -z "$CONTEXT_MODE_HOOK" ]] || [[ ! -f "$CONTEXT_MODE_HOOK" ]]; then
        CONTEXT_MODE_HOOK="$(npm root -g 2>/dev/null)/context-mode/hooks/posttooluse.mjs"
    fi

    if [[ -f "$CONTEXT_MODE_HOOK" ]]; then
        # Let context-mode capture the event for its session snapshot
        echo "$INPUT" | node "$CONTEXT_MODE_HOOK" >/dev/null 2>&1 || true
    fi
fi

# Extract stdout from tool result
OUTPUT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # Claude Code wraps output in content array or directly
    content = d.get('content', '')
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                print(item.get('text', ''))
                break
    elif isinstance(content, str):
        print(content)
    else:
        print(d.get('output', d.get('stdout', '')))
except Exception as e:
    print('')
" 2>/dev/null || echo "")

LINE_COUNT=$(echo "$OUTPUT" | wc -l | tr -d ' ')

if [[ "$LINE_COUNT" -gt 300 ]]; then
    HEAD=$(echo "$OUTPUT" | head -40)
    TAIL=$(echo "$OUTPUT" | tail -40)
    OMITTED=$(( LINE_COUNT - 80 ))

    if [[ "${CONTEXT_EVAL_MODE:-baseline}" == "context-mode" ]]; then
        COMPACTED=$(printf '%s\n\n... %d lines omitted (use grep/search to find specific content) ...\n\n%s\n\n[CONTEXT-MODE TRIAL]: Output truncated. If you need the full data, consider using `ctx_batch_execute` or similar context-mode tools to process it securely within the sandbox.' \
            "$HEAD" "$OMITTED" "$TAIL")
    else
        COMPACTED=$(printf '%s\n\n... %d lines omitted (use grep/search to find specific content) ...\n\n%s' \
            "$HEAD" "$OMITTED" "$TAIL")
    fi

    # Emit compacted version back to Claude Code
    python3 -c "
import sys, json
compacted = sys.argv[1]
print(json.dumps({'type': 'text', 'text': compacted}))
" "$COMPACTED"
fi

# --- Batching reminder after pctx execute_typescript ---
TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
if [[ "$TOOL_NAME" == "mcp__pctx__execute_typescript" ]]; then
    echo "BATCH CHECK: Was this the only Serena/MCP operation needed this turn? If 2+ ops are coming, combine them into one execute_typescript call." >&2
fi

exit 0
