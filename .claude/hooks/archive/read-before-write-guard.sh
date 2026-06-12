#!/usr/bin/env bash
# PreToolUse:Write — blocks writes to existing files unless already read this session.
# The Write tool enforces this at the harness level too, but this gives an earlier,
# clearer error message before the tool call attempt.
FILE=$(jq -r '.tool_input.file_path' 2>/dev/null)
if [ -n "$FILE" ] && [ "$FILE" != "null" ] && [ -f "$FILE" ]; then
  echo "Read $FILE before writing."
  exit 2
fi
