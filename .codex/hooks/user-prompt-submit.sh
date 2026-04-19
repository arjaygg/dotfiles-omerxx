#!/usr/bin/env bash
set -euo pipefail

# Keep one copy of payload in case downstream scripts expect stdin.
INPUT="$(cat || true)"

printf '%s' "$INPUT" | bash "$HOME/.dotfiles/.claude/hooks/session-init-enforcer.sh" || true
printf '%s' "$INPUT" | bash "$HOME/.dotfiles/.claude/hooks/plans-healthcheck.sh" || true
printf '%s' "$INPUT" | bash "$HOME/.dotfiles/.claude/hooks/plan-todowrite-reminder.sh" || true
