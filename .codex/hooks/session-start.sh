#!/usr/bin/env bash
set -euo pipefail

source "$HOME/.dotfiles/.codex/hooks/lib.sh"

# Drain hook stdin payload (runtime-specific JSON)
cat >/dev/null || true

codex_hook_run "session-init" "$HOME/.dotfiles/.claude/hooks/session-init.sh"
