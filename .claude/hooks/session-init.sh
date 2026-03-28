#!/usr/bin/env bash
# SessionStart hook: record session start timestamp for session-scoped tracking
# Used by pre-compact.sh (H7) to find files edited THIS session (not since last git op).

set -euo pipefail

# Write session-start timestamp to a per-user temp file
TIMESTAMP_FILE="/tmp/.claude-session-start-$(id -u)"
date '+%s' > "$TIMESTAMP_FILE"

# Inject mandatory session-init instruction so Claude sees it at session start
cat <<'EOF'
[SESSION INIT REQUIRED]
Before the first project file access (Read/Grep/Glob/Serena), you MUST:
  1. Call mcp__pctx__list_functions — confirm current Serena/lean-ctx signatures
  2. Write the result to plans/pctx-functions.md (create plans/ if missing)
  3. Call Serena.initialInstructions() — load project-specific rules

Skip this ONLY if plans/pctx-functions.md already exists and was written today.
EOF

exit 0
