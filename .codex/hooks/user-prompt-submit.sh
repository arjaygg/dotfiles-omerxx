#!/usr/bin/env bash
set -euo pipefail

source "$HOME/.dotfiles/.codex/hooks/lib.sh"

# Keep one copy of payload in case downstream scripts expect stdin.
INPUT="$(cat || true)"

codex_hook_run "session-init-enforcer" "$HOME/.dotfiles/.claude/hooks/session-init-enforcer.sh" "$INPUT"
CLAUDE_HOOKS_DISABLE_AUTO_INSTALL=1 \
  codex_hook_run "plans-healthcheck" "$HOME/.dotfiles/.claude/hooks/plans-healthcheck.sh" "$INPUT"
codex_hook_run "plan-todowrite-reminder" "$HOME/.dotfiles/.claude/hooks/plan-todowrite-reminder.sh" "$INPUT"
