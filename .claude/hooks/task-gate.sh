#!/usr/bin/env bash
# Stop hook: warns (or blocks) if orphaned background tasks, crons, or open task-list items remain.
#
# Replaces todo-gate.sh (which re-parsed entire JSONL transcript via python3 on every Stop).
# This version is O(1): reads a session-scoped state file written by task-event-tracker.sh.
#
# Checks (in order):
#   1. Open task count from /tmp/.claude-task-state-$CLAUDE_SESSION_ID
#   2. background_tasks field from Stop payload (orphaned bg work)
#   3. session_crons field from Stop payload (crons that will expire with the session)
#
# Levels (hook-config.yaml key: task-gate):
#   warn  — emit advisory to stderr, allow stop
#   block — emit JSON block decision, prevent stop
#   off   — disabled entirely

set -euo pipefail
trap 'exit 0' ERR

HOOK_CONFIG="$HOME/.dotfiles/.claude/hooks/hook-config.yaml"
LEVEL=$(grep "^task-gate:" "$HOOK_CONFIG" 2>/dev/null | awk '{print $2}' | tr -d '"' | tr -d "'" || echo "warn")
[ "$LEVEL" = "off" ] && exit 0

INPUT=$(cat)

# Guard: stop_hook_active prevents infinite loops when the Stop hook itself causes a Stop
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
[ "$STOP_HOOK_ACTIVE" = "true" ] && exit 0

# ------------------------------------------------------------------
# 1. Open task count (from task-event-tracker.sh state file)
# ------------------------------------------------------------------
SESSION="${CLAUDE_SESSION_ID:-}"
OPEN_TASKS=0
if [[ -n "$SESSION" ]]; then
    STATE_FILE="/tmp/.claude-task-state-${SESSION}"
    if [[ -f "$STATE_FILE" ]]; then
        OPEN_TASKS=$(jq -r '.open_count // 0' "$STATE_FILE" 2>/dev/null || echo "0")
        [[ "$OPEN_TASKS" =~ ^[0-9]+$ ]] || OPEN_TASKS=0
    fi
fi

# ------------------------------------------------------------------
# 2. Background tasks from Stop payload
# ------------------------------------------------------------------
BG_TASKS=$(echo "$INPUT" | jq -r '(.background_tasks // []) | length' 2>/dev/null || echo "0")
[[ "$BG_TASKS" =~ ^[0-9]+$ ]] || BG_TASKS=0

# ------------------------------------------------------------------
# 3. Active session crons from Stop payload
# ------------------------------------------------------------------
CRON_JOBS=$(echo "$INPUT" | jq -r '(.session_crons // []) | length' 2>/dev/null || echo "0")
[[ "$CRON_JOBS" =~ ^[0-9]+$ ]] || CRON_JOBS=0

# If all zero, nothing to warn about
TOTAL=$(( OPEN_TASKS + BG_TASKS + CRON_JOBS ))
[ "$TOTAL" -eq 0 ] && exit 0

# Build warning message
REASONS=()
[ "$OPEN_TASKS" -gt 0 ] && REASONS+=("${OPEN_TASKS} open task(s) in task list not yet completed")
[ "$BG_TASKS" -gt 0 ] && REASONS+=("${BG_TASKS} background task(s) still running")
[ "$CRON_JOBS" -gt 0 ] && REASONS+=("${CRON_JOBS} active cron job(s) that will expire with this session")

MSG="TASK-GATE:"
for reason in "${REASONS[@]}"; do
    MSG+=" ${reason};"
done
MSG="${MSG%;}"

if [ "$LEVEL" = "block" ]; then
    jq -n --arg reason "$MSG" \
        '{"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": $reason}}'
    exit 0
else
    echo "$MSG" >&2
    exit 0
fi
