#!/usr/bin/env bash
# PostToolUse: Track sequential Serena/pctx MCP calls and suggest batching
# Matcher: mcp__serena__.*|mcp__pctx__.*
# Exit: 0 = pass, 2 = warn

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/hook-metrics.sh" 2>/dev/null || true
_HOOK_NAME="pctx-batch-tracker"
_EXIT_CODE=$(hook_exit_code "$_HOOK_NAME" 2>/dev/null || echo 2)

INPUT=$(cat)

IFS=$'\001' read -r TOOL_NAME SESSION_ID < <(
    echo "$INPUT" | jq -r '[.tool_name // "", .session_id // "default"] | join("\u0001")' 2>/dev/null || printf '\001default'
)

# --- If this IS a pctx execute_typescript call, reset the counter (batched path) ---
if [[ "$TOOL_NAME" == "mcp__pctx__execute_typescript" ]]; then
    TRACKER="/tmp/.claude-serena-calls-$(id -u)-${SESSION_ID}"
    rm -f "$TRACKER" 2>/dev/null || true
    hook_metric "$_HOOK_NAME" "$TOOL_NAME" 0 2>/dev/null || true
    exit 0
fi

# --- Track the call ---
TRACKER="/tmp/.claude-serena-calls-$(id -u)-${SESSION_ID}"
NOW=$(date '+%s')

# Append timestamp
echo "$NOW $TOOL_NAME" >> "$TRACKER"

# Prune entries older than 60 seconds
if [[ -f "$TRACKER" ]]; then
    CUTOFF=$((NOW - 60))
    TEMP=$(mktemp)
    awk -v cutoff="$CUTOFF" '$1 >= cutoff' "$TRACKER" > "$TEMP" 2>/dev/null && mv "$TEMP" "$TRACKER" || rm -f "$TEMP"
fi

# Count recent calls
COUNT=0
[[ -f "$TRACKER" ]] && COUNT=$(wc -l < "$TRACKER" | tr -d ' ')

if [[ "$COUNT" -ge 3 ]]; then
    echo "BATCH HINT: You've made $COUNT sequential Serena/pctx MCP calls in the last 60s."
    echo "  Consider batching into one pctx execute_typescript call with Promise.all()."
    echo "  See: tool-priority.md §2 'Batching & Code Mode'"
    # Reset after warning to avoid repeated noise
    rm -f "$TRACKER" 2>/dev/null || true
    hook_metric "$_HOOK_NAME" "$TOOL_NAME" 0 2>/dev/null || true
    exit 0
fi

hook_metric "$_HOOK_NAME" "$TOOL_NAME" 0 2>/dev/null || true
exit 0
