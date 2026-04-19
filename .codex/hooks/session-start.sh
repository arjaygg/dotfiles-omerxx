#!/usr/bin/env bash
set -euo pipefail

# Drain hook stdin payload (runtime-specific JSON)
cat >/dev/null || true

# Reuse portable/session-safe Claude script(s)
bash "$HOME/.dotfiles/.claude/hooks/session-init.sh" || true
