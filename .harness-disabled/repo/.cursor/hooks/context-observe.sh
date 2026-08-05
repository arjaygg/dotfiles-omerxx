#!/usr/bin/env bash
set -uo pipefail

INPUT="$(cat 2>/dev/null || true)"
HOOK_DIR="$(
  CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P
)" || HOOK_DIR=""
REPO_ROOT="${HOOK_DIR:+$HOOK_DIR/../..}"
GATE="${REPO_ROOT:+$REPO_ROOT/.local/bin/context-file-gate}"

if [[ -n "$GATE" && -x "$GATE" ]]; then
  printf '%s' "$INPUT" |
    DOTFILES_ROOT="$REPO_ROOT" "$GATE" \
      --client cursor --event post_tool_use --json >/dev/null 2>&1 || true
fi

printf '{}\n'
exit 0
