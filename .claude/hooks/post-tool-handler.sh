#!/usr/bin/env bash
# PostToolUse: compact Bash output >300 lines
# Claude Code passes tool result as JSON on stdin

set -euo pipefail

INPUT=$(cat)

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

    COMPACTED=$(printf '%s\n\n... %d lines omitted (use grep/search to find specific content) ...\n\n%s' \
        "$HEAD" "$OMITTED" "$TAIL")

    # Emit compacted version back to Claude Code
    python3 -c "
import sys, json
compacted = sys.argv[1]
print(json.dumps({'type': 'text', 'text': compacted}))
" "$COMPACTED"
fi

exit 0
