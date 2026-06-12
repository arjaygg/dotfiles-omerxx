#!/usr/bin/env bash
# PostToolUse hook — fires after Agent tool calls complete.
#
# Inspects teammate output for quality signals:
#   - Did the agent produce any output at all?
#   - Did it report a blocked or error state?
#   - Did any git changes land on main (forbidden)?
#
# Emits advisory to stderr only (never blocks — teammates surface their own errors).
# Level: advisory (always warn, never block)

set -euo pipefail
trap 'exit 0' ERR

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")

# Only fire on Agent tool completions
[[ "$TOOL_NAME" == "Agent" ]] || exit 0

OUTPUT=$(echo "$INPUT" | jq -r '.tool_response // .output // ""' 2>/dev/null || echo "")
AGENT_NAME=$(echo "$INPUT" | jq -r '.tool_input.name // "unnamed"' 2>/dev/null || echo "unnamed")

# --- Guard 1: Empty output ---
if [[ -z "$OUTPUT" || "$OUTPUT" == "null" ]]; then
    echo "TEAMMATE-GATE [${AGENT_NAME}]: produced no output — check if it was interrupted." >&2
    exit 0
fi

# --- Guard 2: Error or blocked indicators ---
if echo "$OUTPUT" | grep -qiE "(error:|blocked:|BLOCKED|failed to|cannot|permission denied)" 2>/dev/null; then
    FIRST_ERROR=$(echo "$OUTPUT" | grep -iEm 1 "(error:|blocked:|BLOCKED|failed to|cannot|permission denied)" || echo "see output")
    echo "TEAMMATE-GATE [${AGENT_NAME}]: possible error — \"${FIRST_ERROR}\"" >&2
fi

# --- Guard 3: Check if any git changes landed on main ---
# This is best-effort — only fires if git is accessible and we're in a git repo
if git rev-parse --git-dir >/dev/null 2>&1; then
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
    if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
        # Check if HEAD moved (new commits on main)
        RECENT_MSG=$(git log -1 --format="%s" 2>/dev/null || echo "")
        if [[ -n "$RECENT_MSG" ]]; then
            echo "TEAMMATE-GATE [${AGENT_NAME}]: current branch is '${CURRENT_BRANCH}' — teammate may have committed directly to main. Verify: git log -3." >&2
        fi
    fi
fi

exit 0
