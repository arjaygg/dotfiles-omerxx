#!/usr/bin/env bash
# SessionStart hook: record session start timestamp for session-scoped tracking
# Used by pre-compact.sh (H7) to find files edited THIS session (not since last git op).

set -euo pipefail

# Write session-start timestamp to a per-user temp file
TIMESTAMP_FILE="/tmp/.claude-session-start-$(id -u)"
date '+%s' > "$TIMESTAMP_FILE"

# Warn if a substantial session already ran in this directory recently
bash "$HOME/.dotfiles/.claude/hooks/duplicate-session-check.sh" || true

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
# Serena.initialInstructions() is only needed when a .serena/ config dir is present.
HAS_SERENA=false
dir="$(pwd)"
while [[ "$dir" != "/" ]]; do
    if [[ -d "$dir/.serena" ]]; then
        HAS_SERENA=true
        break
    fi
    dir="$(dirname "$dir")"
done

if $HAS_SERENA; then
    # Count available memories for the hint
    _SERENA_DIR="$(pwd)/.serena/memories"
    _MEM_COUNT=0
    if [[ -d "$_SERENA_DIR" ]]; then
        _MEM_COUNT=$(find "$_SERENA_DIR" -name "*.md" ! -path "*/_archive/*" 2>/dev/null | wc -l | tr -d ' ')
    fi
    _MEM_HINT=""
    if [[ "$_MEM_COUNT" -gt 0 ]]; then
        _MEM_HINT="  4. Serena.readMemory({ name: \"START_HERE\" }) — load project memories ($_MEM_COUNT available)"
    fi

    cat <<EOF
[SESSION INIT REQUIRED]
Before the first project file access (Read/Grep/Glob/Serena), you MUST:
  1. Call mcp__pctx__list_functions — confirm current Serena/lean-ctx signatures
  2. Write the result to plans/pctx-functions.md (create plans/ if missing)
  3. Call Serena.initialInstructions() — load project-specific rules
${_MEM_HINT}
Skip this ONLY if plans/pctx-functions.md already exists and was written today.
EOF
else
    cat <<'EOF'
[SESSION INIT REQUIRED]
Before the first project file access (Read/Grep/Glob/Serena), you MUST:
  1. Call mcp__pctx__list_functions — confirm current Serena/lean-ctx signatures
  2. Write the result to plans/pctx-functions.md (create plans/ if missing)

Skip step 3 (Serena.initialInstructions) — no .serena/ config found in this directory tree.
Skip this ONLY if plans/pctx-functions.md already exists and was written today.
EOF
fi

# Update tmux window name with Claude session context
"$HOME/.dotfiles/tmux/scripts/claude-tmux-bridge.sh" session-start &

exit 0
