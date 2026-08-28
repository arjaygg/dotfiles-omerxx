#!/usr/bin/env bash
set -euo pipefail

WORKTREE_PATH="${1:-}"
LOG_FILE="/tmp/tmux-open-code.log"

ts() { date +"%Y-%m-%dT%H:%M:%S%z"; }

{
  echo "[$(ts)] open-code.sh called"
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

# Prefer VS Code CLI if present (opens faster and reuses instance).
if command -v code >/dev/null 2>&1; then
  echo "[$(ts)] using code CLI" >>"$LOG_FILE"
  # Don't exec; we want to return control to fzf/tmux immediately.
  code "$WORKTREE_PATH" >/dev/null 2>&1 && exit 0
  echo "[$(ts)] WARN: code CLI returned non-zero; falling back to open" >>"$LOG_FILE"
fi

echo "[$(ts)] using /usr/bin/open -a Visual Studio Code" >>"$LOG_FILE"
/usr/bin/open -a "Visual Studio Code" "$WORKTREE_PATH" >/dev/null 2>&1 && exit 0

echo "[$(ts)] ERROR: failed to open VS Code via open" >>"$LOG_FILE"
exit 1
