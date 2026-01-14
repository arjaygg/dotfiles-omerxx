#!/usr/bin/env bash
set -euo pipefail

WORKTREE_PATH="${1:-}"
LOG_FILE="/tmp/tmux-open-cursor.log"

ts() { date +"%Y-%m-%dT%H:%M:%S%z"; }

{
  echo "[$(ts)] open-cursor.sh called"
  echo "[$(ts)] arg1: ${WORKTREE_PATH}"
} >>"$LOG_FILE"

if [[ -z "$WORKTREE_PATH" ]]; then
  echo "[$(ts)] ERROR: missing path argument" >>"$LOG_FILE"
  exit 2
fi

if [[ ! -d "$WORKTREE_PATH" && ! -f "$WORKTREE_PATH" ]]; then
  echo "[$(ts)] ERROR: path does not exist: $WORKTREE_PATH" >>"$LOG_FILE"
  exit 3
fi

# Prefer Cursor CLI if present (opens faster and reuses instance).
if command -v cursor >/dev/null 2>&1; then
  echo "[$(ts)] using cursor CLI" >>"$LOG_FILE"
  # Don't exec; we want to return control to fzf/tmux immediately.
  cursor "$WORKTREE_PATH" >/dev/null 2>&1 && exit 0
  echo "[$(ts)] WARN: cursor CLI returned non-zero; falling back to open" >>"$LOG_FILE"
fi

echo "[$(ts)] using /usr/bin/open -a Cursor" >>"$LOG_FILE"
/usr/bin/open -a "Cursor" "$WORKTREE_PATH" >/dev/null 2>&1 && exit 0

echo "[$(ts)] ERROR: failed to open Cursor via open" >>"$LOG_FILE"
exit 1

