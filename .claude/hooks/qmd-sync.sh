#!/usr/bin/env bash
# UserPromptSubmit hook: keep all qmd collections current.
# Non-fatal — index may be stale but never blocks the session.
set -euo pipefail

# CRITICAL: Drain stdin — all UserPromptSubmit hooks must consume stdin to prevent buffering issues
cat > /dev/null

if command -v qmd &>/dev/null; then
  (qmd update --quiet 2>/dev/null && qmd embed --quiet 2>/dev/null) &
fi

exit 0
