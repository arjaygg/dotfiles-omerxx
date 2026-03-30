#!/usr/bin/env bash
# SessionStart hook: record session start timestamp for session-scoped tracking
# Used by pre-compact.sh (H7) to find files edited THIS session (not since last git op).

set -euo pipefail

# Write session-start timestamp to a per-user temp file
TIMESTAMP_FILE="/tmp/.claude-session-start-$(id -u)"
date '+%s' > "$TIMESTAMP_FILE"

# Kill stale pctx processes from other worktrees to prevent cross-contamination.
# Each stdio pctx session inherits its CWD, so a process started in worktree A
# must not serve worktree B. Only kill processes with hardcoded worktree paths.
CWD="$(pwd)"
if [[ "$CWD" == */.trees/* ]]; then
    WORKTREE_NAME="${CWD##*/.trees/}"
    WORKTREE_NAME="${WORKTREE_NAME%%/*}"
    while IFS= read -r line; do
        pid="${line%% *}"
        if echo "$line" | grep -q '\.trees/[^/]*/\.config/pctx\.json' && \
           ! echo "$line" | grep -q "\.trees/${WORKTREE_NAME}/\.config/pctx\.json"; then
            kill "$pid" 2>/dev/null || true
        fi
    done < <(pgrep -fl 'pctx.*mcp.*start' 2>/dev/null || true)
fi

# Inject mandatory session-init instruction so Claude sees it at session start
cat <<'EOF'
[SESSION INIT REQUIRED]
Before the first project file access (Read/Grep/Glob/Serena), you MUST:
  1. Call mcp__pctx__list_functions — confirm current Serena/lean-ctx signatures
  2. Write the result to plans/pctx-functions.md (create plans/ if missing)
  3. Call Serena.initialInstructions() — load project-specific rules

Skip this ONLY if plans/pctx-functions.md already exists and was written today.
EOF

# Update tmux window name with Claude session context
"$HOME/.dotfiles/tmux/scripts/claude-tmux-bridge.sh" session-start &

exit 0
