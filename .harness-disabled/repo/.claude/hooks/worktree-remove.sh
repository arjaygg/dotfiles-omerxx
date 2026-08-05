#!/usr/bin/env bash
# worktree-remove.sh — WorktreeRemove hook for Claude Code
#
# Delegates worktree cleanup to the stack's safe-removal command,
# which refuses removal if the worktree has uncommitted changes.
#
# Called by ExitWorktree({action: "remove"}) and session cleanup.
#
# Input:  JSON on stdin — { "path": "<absolute-path>", ... }
# Output: Exit 0 on success, non-zero on failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_SCRIPT="$SCRIPT_DIR/../scripts/stack"

# ── JSON parsing ─────────────────────────────────────────────────────────────
parse_json_field() {
    local json="$1"
    local field="$2"

    if command -v jq &>/dev/null; then
        echo "$json" | jq -r ".$field // empty"
    elif command -v python3 &>/dev/null; then
        echo "$json" | python3 -c "
import json, sys
d = json.load(sys.stdin)
v = d.get('$field', '')
if v is not None:
    print(v)
"
    else
        echo "$json" | grep -o "\"$field\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
            | sed 's/.*"[^"]*"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/'
    fi
}

INPUT="$(cat)"
WORKTREE_PATH="$(parse_json_field "$INPUT" "path")"

if [ -z "$WORKTREE_PATH" ]; then
    echo "worktree-remove.sh: missing 'path' in hook payload" >&2
    exit 1
fi

echo "worktree-remove.sh: removing worktree at $WORKTREE_PATH" >&2

# Delegate to stack's safe removal (refuses if dirty)
if [ -x "$STACK_SCRIPT" ]; then
    "$STACK_SCRIPT" worktree-remove "$WORKTREE_PATH"
else
    # Fallback: use git directly with the same safety check
    STATUS="$(git -C "$WORKTREE_PATH" status --short 2>/dev/null || true)"
    if [ -n "$STATUS" ]; then
        echo "worktree-remove.sh: refusing to remove worktree with uncommitted changes:" >&2
        echo "$STATUS" >&2
        exit 1
    fi
    git worktree remove "$WORKTREE_PATH"
fi

echo "worktree-remove.sh: done" >&2
