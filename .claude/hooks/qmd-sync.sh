#!/usr/bin/env bash
# UserPromptSubmit hook: keep all qmd collections current.
# Non-fatal — index may be stale but never blocks the session.
set -euo pipefail

if command -v qmd &>/dev/null; then
  qmd update --quiet 2>/dev/null || true
  qmd embed  --quiet 2>/dev/null || true
fi

exit 0
