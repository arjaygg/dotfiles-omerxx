#!/usr/bin/env bash
# Pre-commit: blocks commits when working tree is blocked (mixed concerns).
# Warns (advisory) when overgrown. Delegates state computation to atomic-status.sh.
set -euo pipefail

ATOMIC_STATUS="$HOME/.dotfiles/scripts/ai/atomic-status.sh"

if [[ ! -x "$ATOMIC_STATUS" ]]; then
    echo "WARNING: atomic-status.sh not found or not executable at $ATOMIC_STATUS" >&2
    exit 0
fi

STATE=$("$ATOMIC_STATUS" 2>/dev/null || echo "in_progress")

case "$STATE" in
    blocked)
        echo "⛔ git-hook: Commit blocked — mixed concerns detected across staged files." >&2
        echo "   Split your changes into focused commits, one concern at a time." >&2
        echo "   Run: $ATOMIC_STATUS  to diagnose." >&2
        exit 1
        ;;
    overgrown)
        echo "⚠️  git-hook: Working tree is overgrown (too many files/lines staged)." >&2
        echo "   Consider committing a smaller subset. Proceeding, but please split soon." >&2
        exit 0
        ;;
    *)
        exit 0
        ;;
esac
