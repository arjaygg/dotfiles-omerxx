#!/usr/bin/env bash
set -euo pipefail

TOOL_INPUT=$(cat)
TOOL_NAME=$(echo "$TOOL_INPUT" | jq -r '.tool_name // empty')

if [[ "$TOOL_NAME" != "Bash" ]]; then exit 0; fi

COMMAND=$(echo "$TOOL_INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -qE "git push.*(main|master)"; then
  echo "BLOCKED: Direct push to main/master not allowed. Use a PR." >&2
  exit 2
fi

exit 0
