#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat || true)"

printf '%s' "$INPUT" | bash "$HOME/.dotfiles/.claude/hooks/session-end.sh" || true
printf '%s' "$INPUT" | bash "$HOME/.dotfiles/.claude/hooks/plan-completion-check.sh" || true
printf '%s' "$INPUT" | bash "$HOME/.dotfiles/.claude/hooks/todo-gate.sh" || true
