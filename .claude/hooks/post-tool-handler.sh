#!/usr/bin/env bash
# PostToolUse: compact large output + warn on medium output + detect rtk compression
# Matcher: Bash|Agent
# Merges former bash-output-guard.sh (output warnings) into this single handler.
# Claude Code passes tool result as JSON on stdin:
# {"session_id":"...","tool_name":"Bash|Agent","tool_input":{...},"tool_response":{"content":[...]}}

set -euo pipefail

INPUT=$(cat)

# Extract tool_name, command, exit_code in one jq call
# Subshell isolates jq failure from pipefail
IFS=$'\001' read -r TOOL_NAME CMD EXIT_CODE < <(
    printf '%s' "$INPUT" | jq -r '[.tool_name // "", .tool_input.command // "", (.tool_response.exitCode // .tool_response.exit_code // 0 | tostring)] | join("\u0001")' 2>/dev/null || printf '\001\0010'
) || true

# --- Skip known short-output commands (fast path — no output extraction needed) ---
if [[ "$TOOL_NAME" == "Bash" ]]; then
    case "$CMD" in
        git\ status*|git\ branch*|git\ diff\ --stat*|git\ log\ --oneline*|pwd*|which*|echo*)
            exit 0 ;;
    esac
fi

# Extract output text — tool_response.content is primary; fall back to legacy top-level content
OUTPUT=$(printf '%s' "$INPUT" | jq -r '
  (.tool_response.content // .content // "") |
  if type == "array" then (map(select(.type == "text") | .text) | first // "")
  elif type == "string" then .
  else ""
  end
' 2>/dev/null || true)

LINE_COUNT=$(echo "$OUTPUT" | wc -l | tr -d ' ')

# --- Tier 1: Compact very large output (>300 for Bash, >200 for Agent) ---
COMPACT_THRESHOLD=300
[[ "$TOOL_NAME" == "Agent" ]] && COMPACT_THRESHOLD=200

if [[ "$LINE_COUNT" -gt "$COMPACT_THRESHOLD" ]]; then
    HEAD=$(echo "$OUTPUT" | head -40)
    TAIL=$(echo "$OUTPUT" | tail -40)
    OMITTED=$(( LINE_COUNT - 80 ))

    COMPACTED=$(printf '%s\n\n... %d lines omitted (use grep/search to find specific content) ...\n\n%s' \
        "$HEAD" "$OMITTED" "$TAIL")

    # Emit compacted version as JSON
    jq -Rns '{"type":"text","text":.}' <<< "$COMPACTED"

# --- Tier 2: Warn on large output (200-300 lines) ---
elif [[ "$TOOL_NAME" == "Bash" && "$LINE_COUNT" -gt 200 ]]; then
    echo "OUTPUT WARNING: Bash produced $LINE_COUNT lines — significant context consumption."
    echo "  For data-heavy commands, use context-mode MCP tools:"
    echo "    mcp__context-mode__ctx_batch_execute — runs commands + auto-indexes output"
    echo "    mcp__context-mode__ctx_execute — processes data in sandbox"

# --- Tier 3: Hint on medium output (50-200 lines) ---
elif [[ "$TOOL_NAME" == "Bash" && "$LINE_COUNT" -gt 50 ]]; then
    echo "OUTPUT HINT: Bash produced $LINE_COUNT lines. For commands with large output, consider context-mode MCP tools to keep raw data out of context."
fi

# --- Detect rtk-compressed test failures (lost diagnostics) ---
if [[ "$TOOL_NAME" == "Bash" && "$EXIT_CODE" != "0" ]]; then
    if echo "$CMD" | grep -qiE '(go test|pytest|npm test|npx jest|dotnet test|cargo test)'; then
        if echo "$OUTPUT" | grep -q '\[lean-ctx:' || [[ "$LINE_COUNT" -lt 10 ]]; then
            echo "RTK_DIAGNOSTIC_HINT: Test failed but output was compressed by rtk. To see full error details, re-run with: rtk proxy $CMD"
        fi
    fi
fi

exit 0
