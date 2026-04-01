#!/usr/bin/env bash
set -euo pipefail

TOOL_INPUT=$(cat)
TOOL_NAME=$(echo "$TOOL_INPUT" | jq -r '.tool_name // empty')

if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

COMMAND=$(echo "$TOOL_INPUT" | jq -r '.tool_input.command // empty')

# Block direct pushes to main or master (with or without remote prefix)
if echo "$COMMAND" | grep -qE "git push\b.*\b(main|master)\b"; then
  echo "BLOCKED: Direct push to main/master is not allowed. Use a feature branch and create a PR instead." >&2
  exit 2
fi

exit 0
