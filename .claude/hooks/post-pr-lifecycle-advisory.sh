#!/usr/bin/env bash
# PostToolUse hook for 'gh pr create' — advisory only
# Prints advisory text so Claude sees that a PR was created, even if invoked directly

INPUT=$(cat)
TOOL_INPUT=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")

# Only fire on successful gh pr create
if echo "$TOOL_INPUT" | grep -q "gh pr create"; then
  PR_OUTPUT=$(echo "$INPUT" | jq -r '.tool_response.output // ""' 2>/dev/null || echo "")
  if echo "$PR_OUTPUT" | grep -q "https://github.com"; then
    PR_URL=$(echo "$PR_OUTPUT" | grep -o 'https://github.com[^ ]*' | head -1)
    PR_NUMBER=$(echo "$PR_URL" | grep -o '[0-9]*$')
    echo "[CI LIFECYCLE] PR #$PR_NUMBER created — run /ci-pr-lifecycle to start automated monitoring"
  fi
fi
