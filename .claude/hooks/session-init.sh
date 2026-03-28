#!/usr/bin/env bash
# SessionStart hook: record session start timestamp for session-scoped tracking
# Used by pre-compact.sh (H7) to find files edited THIS session (not since last git op).

set -euo pipefail

# Write session-start timestamp to a per-user temp file
TIMESTAMP_FILE="/tmp/.claude-session-start-$(id -u)"
date '+%s' > "$TIMESTAMP_FILE"

exit 0
