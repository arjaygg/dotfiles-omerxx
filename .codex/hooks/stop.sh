#!/usr/bin/env bash
set -euo pipefail

source "$HOME/.dotfiles/.codex/hooks/lib.sh"

INPUT="$(cat || true)"

codex_hook_run "session-end" "$HOME/.dotfiles/.claude/hooks/session-end.sh" "$INPUT"
codex_hook_run "plan-completion-check" "$HOME/.dotfiles/.claude/hooks/plan-completion-check.sh" "$INPUT"
codex_hook_run "todo-gate" "$HOME/.dotfiles/.claude/hooks/todo-gate.sh" "$INPUT"
