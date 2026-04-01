#!/usr/bin/env bash
set -euo pipefail

TOOL_INPUT=$(cat)
TOOL_NAME=$(echo "$TOOL_INPUT" | jq -r '.tool_name // empty')

if [[ "$TOOL_NAME" != "Read" ]]; then
  exit 0
fi

FILE=$(echo "$TOOL_INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE" ]]; then
  exit 0
fi

mkdir -p ~/.claude
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) READ: $FILE" >> ~/.claude/read-audit.log

exit 0
