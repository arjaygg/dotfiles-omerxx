#!/usr/bin/env bash
# TaskCreated/TaskCompleted hook: maintains O(1) task state for task-gate.sh
#
# Fires on TaskCreated (increments) and TaskCompleted (decrements).
# State file: /tmp/.claude-task-state-$CLAUDE_SESSION_ID
#   JSON: { "open_count": N, "session": "..." }
#
# Note: no TaskUpdated event exists — counter can desync on cancellation.
# task-gate therefore warns, never hard-blocks, until counts are proven stable.

set -euo pipefail
trap 'exit 0' ERR

SESSION="${CLAUDE_SESSION_ID:-}"
[[ -z "$SESSION" ]] && exit 0

STATE_FILE="/tmp/.claude-task-state-${SESSION}"

INPUT=$(cat)
EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // ""' 2>/dev/null || echo "")
[[ -z "$EVENT" ]] && exit 0

# Read current count (default 0)
CURRENT=0
if [[ -f "$STATE_FILE" ]]; then
    CURRENT=$(jq -r '.open_count // 0' "$STATE_FILE" 2>/dev/null || echo "0")
    [[ "$CURRENT" =~ ^[0-9]+$ ]] || CURRENT=0
fi

case "$EVENT" in
    TaskCreated)   NEW=$((CURRENT + 1)) ;;
    TaskCompleted) NEW=$(( CURRENT > 0 ? CURRENT - 1 : 0 )) ;;
    *)             exit 0 ;;
esac

jq -n --argjson count "$NEW" --arg sess "$SESSION" \
    '{open_count: $count, session: $sess}' > "$STATE_FILE"
