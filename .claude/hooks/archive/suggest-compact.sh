#!/usr/bin/env bash
# PreToolUse: suggest /compact at 50-operation intervals
INPUT=$(cat)
TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")
[[ "$TOOL_NAME" != "Edit" && "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "MultiEdit" ]] && exit 0

SESSION_ID="${CLAUDE_SESSION_ID:-$(id -u)}"
COUNTER="/tmp/.claude-edit-count-${SESSION_ID}"
COUNT=$(cat "$COUNTER" 2>/dev/null || echo "0")
COUNT=$(( COUNT + 1 ))
echo "$COUNT" > "$COUNTER"

THRESHOLD="${COMPACT_THRESHOLD:-50}"
if (( COUNT == THRESHOLD || (COUNT > THRESHOLD && (COUNT - THRESHOLD) % 25 == 0) )); then
    echo "COMPACT SUGGESTION: $COUNT edit/write operations this session — consider /compact to preserve context quality." >&2
fi
exit 0
