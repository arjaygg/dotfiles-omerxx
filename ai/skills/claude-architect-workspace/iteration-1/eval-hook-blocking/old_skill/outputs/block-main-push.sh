#!/usr/bin/env bash
# block-main-push.sh
# Claude Code PreToolUse hook: blocks any `git push` targeting main or master.
# Install via ~/.claude/settings.json hooks (see settings-snippet.json).
#
# Input: JSON object on stdin from Claude Code hook framework.
# Exit 0  → allow the tool call through.
# Exit 2  → block and surface the message to the user.

set -euo pipefail

# Read the full hook payload from stdin
INPUT="$(cat)"

# Extract the tool name
TOOL_NAME="$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')"

# Only inspect Bash tool calls
if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

# Extract the command string Claude is about to run
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')"

# Detect patterns that push to main or master:
#   git push [<remote>] main
#   git push [<remote>] master
#   git push [<remote>] HEAD:main
#   git push [<remote>] HEAD:master
#   git push --force ... (any variant targeting protected branches)
if printf '%s' "$COMMAND" | grep -qE '^\s*git\s+push\b' ; then
  if printf '%s' "$COMMAND" | grep -qE '\b(main|master)\b' ; then
    cat <<'MSG'
BLOCKED: Direct push to a protected branch (main/master) is not allowed.

To get your changes into main/master:
  1. Push to a feature branch:       git push origin HEAD
  2. Open a Pull Request / PR review
  3. Merge via the PR process

If you genuinely need to push directly (e.g. initial repo setup), do it
manually in your terminal — this restriction only applies to Claude.
MSG
    exit 2
  fi
fi

exit 0
