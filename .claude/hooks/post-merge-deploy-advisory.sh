#!/usr/bin/env bash
# PostToolUse hook for 'gh pr merge' — advisory only
# Prints advisory text so Claude sees that a PR was merged, even if invoked directly

INPUT=$(cat)
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
TOOL_OUTPUT=$(echo "$INPUT" | jq -r '.tool_response.output // ""' 2>/dev/null || echo "")

# Only fire on successful gh pr merge
if echo "$TOOL_INPUT" | grep -q "gh pr merge"; then
  if echo "$TOOL_OUTPUT" | grep -qE "(merged|Pull request .* has been merged)"; then
    echo "[CI LIFECYCLE] PR merged to main — run /ci-deploy-watch to monitor deployment"
  fi
fi
