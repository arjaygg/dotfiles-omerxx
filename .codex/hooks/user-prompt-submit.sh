#!/usr/bin/env bash
set -euo pipefail

source "$HOME/.dotfiles/.codex/hooks/lib.sh"

# Keep one copy of payload in case downstream scripts expect stdin.
INPUT="$(cat || true)"

codex_hook_run "session-init-enforcer" "$HOME/.dotfiles/.claude/hooks/session-init-enforcer.sh" "$INPUT"
# plans-healthcheck.sh's auto-install is opt-in (DOTFILES_AUTO_INSTALL=1, unset
# here) — this used to set CLAUDE_HOOKS_DISABLE_AUTO_INSTALL=1 to suppress the
# old opt-out gate; that var is now a no-op since M5 (2026-07-08) flipped the
# default to disabled.
codex_hook_run "plans-healthcheck" "$HOME/.dotfiles/.claude/hooks/plans-healthcheck.sh" "$INPUT"
codex_hook_run "plan-todowrite-reminder" "$HOME/.dotfiles/.claude/hooks/plan-todowrite-reminder.sh" "$INPUT"
