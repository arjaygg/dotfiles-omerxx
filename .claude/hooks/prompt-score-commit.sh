#!/usr/bin/env bash
# PostToolUse hook — Scores the most recent prompt +3 when a git commit succeeds.
# Fires after Bash tool use. Checks if the command was a git commit.
# Always exits 0 (advisory, never blocks).

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name // ""' 2>/dev/null)

# Only process Bash tool calls
[[ "$tool_name" == "Bash" ]] || exit 0

command=$(echo "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)
[[ "$command" == *"git commit"* ]] || exit 0

# Check exit code — only score on success
exit_code=$(echo "$input" | jq -r '.tool_response.exitCode // .tool_response.exit_code // "1"' 2>/dev/null)
[[ "$exit_code" == "0" ]] || exit 0

# Score in background
(
    SCORE_SCRIPT="$HOME/.dotfiles/.claude/scripts/prompt-library-score.sh"
    [[ -x "$SCORE_SCRIPT" ]] && "$SCORE_SCRIPT" --recent +3 >/dev/null 2>&1
) &

exit 0
