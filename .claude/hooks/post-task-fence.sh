#!/usr/bin/env bash
# PostToolUse hook for TaskUpdate: warns when a task is marked "completed"
# but the working tree has uncommitted changes.
# Nudges the agent to commit before starting the next task.
#
# Exit codes: 0 = allow, 2 = warn (advisory)
set -euo pipefail

INPUT=$(cat)

# Parse task status from PostToolUse payload
STATUS=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('status', ''))
except:
    pass
" 2>/dev/null || echo "")

# Only fire on task completion
[[ "$STATUS" != "completed" ]] && exit 0

# Only fence in repos with hyper-atomic hooks installed
HOOKS_PATH=$(git config --local core.hooksPath 2>/dev/null || echo "")
[[ "$HOOKS_PATH" != "$HOME/.dotfiles/git/hooks" ]] && exit 0

STAGED=$(git diff --cached --name-only 2>/dev/null || true)
UNSTAGED=$(git diff --name-only 2>/dev/null || true)

if [[ -n "$STAGED" || -n "$UNSTAGED" ]]; then
    echo "WARNING: Task marked complete with uncommitted changes." >&2
    if [[ -n "$STAGED" ]]; then
        _count=$(echo "$STAGED" | wc -l | tr -d ' ')
        echo "  Staged: $_count file(s)" >&2
    fi
    if [[ -n "$UNSTAGED" ]]; then
        _count=$(echo "$UNSTAGED" | wc -l | tr -d ' ')
        echo "  Unstaged: $_count file(s)" >&2
    fi
    echo "  Commit before starting next task:" >&2
    echo "  ~/.dotfiles/scripts/ai/commit.sh -m 'type(scope): subject' -m 'why'" >&2
    exit 2
fi

exit 0
