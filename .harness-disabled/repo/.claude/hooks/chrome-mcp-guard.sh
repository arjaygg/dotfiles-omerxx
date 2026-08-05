#!/usr/bin/env bash
# chrome-mcp-guard.sh — PreToolUse advisory hook
# Fires once per session, the first time a claude-in-chrome tool is called,
# to inject context-efficiency guidance (ai/rules/chrome-mcp-efficiency.md).
# This is advisory only: it never blocks tool calls.

PAYLOAD=$(cat -)
TOOL=$(printf '%s' "$PAYLOAD" | jq -r '.tool_name // empty' 2>/dev/null)

# Only fire for claude-in-chrome tools
[[ "$TOOL" == mcp__claude-in-chrome__* ]] || exit 0

# Fire once per session — track via a state file keyed on the transcript/session id
SESSION_ID=$(printf '%s' "$PAYLOAD" | jq -r '.session_id // empty' 2>/dev/null)
STATE_DIR="$HOME/.dotfiles/.claude/hooks/.state"
mkdir -p "$STATE_DIR" 2>/dev/null
STATE_FILE="$STATE_DIR/chrome-mcp-guard.${SESSION_ID:-default}"

[[ -f "$STATE_FILE" ]] && exit 0
touch "$STATE_FILE" 2>/dev/null

>&2 cat <<'MSG'
[chrome-mcp] Chrome browser tools in use — apply context-efficiency rules:
  • Prefer get_page_text/read_page over computer screenshots for reading content
  • Filter read_console_messages/read_network_requests with a pattern, don't dump unfiltered
  • Batch Chrome ToolSearch calls once per task, not one tool at a time
  • Don't re-read full page state after every micro-action in a multi-step flow
  • Close tabs (tabs_close_mcp) once a sub-task is done
Full rules: ai/rules/chrome-mcp-efficiency.md
MSG

exit 0
