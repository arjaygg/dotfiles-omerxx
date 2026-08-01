#!/usr/bin/env bash
# tmux-side — second client for dual-monitor viewing (session group)
#
# Usage:
#   tmux-side              # side session for current tmux session
#   tmux-side manage       # side session for named base session
#
# In a second Ghostty (outside tmux): attaches/creates <session>2
# Inside tmux: creates <session>2 detached (won't steal this client)

set -euo pipefail

base="${1:-}"
if [[ -z "$base" ]]; then
  if [[ -n "${TMUX:-}" ]]; then
    base="$(tmux display-message -p '#S')"
  else
    echo "Usage: tmux-side [session]" >&2
    echo "Run inside tmux, or pass a session name (e.g. tmux-side manage)." >&2
    exit 1
  fi
fi

if ! tmux has-session -t "$base" 2>/dev/null; then
  echo "Session '$base' not found." >&2
  tmux list-sessions >&2 || true
  exit 1
fi

side="${base}2"

if [[ -n "${TMUX:-}" ]]; then
  # Don't move the current client — only ensure the side session exists.
  if tmux has-session -t "$side" 2>/dev/null; then
    echo "Side session '$side' already exists (grouped with '$base')."
  else
    tmux new-session -d -t "$base" -s "$side"
    echo "Created side session '$side' (grouped with '$base')."
  fi
  echo "In your other Ghostty, run: tmux-side $base"
  exit 0
fi

if tmux has-session -t "$side" 2>/dev/null; then
  exec tmux attach-session -t "$side"
fi

exec tmux new-session -t "$base" -s "$side"
