#!/usr/bin/env bash
set -euo pipefail

# Codex payload shape can vary by version. Pull common command fields best-effort.
INPUT="$(cat || true)"
CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // .command // .input.command // empty' 2>/dev/null || true)"

# Hook is advisory-only; hard enforcement belongs in .codex/rules/default.rules + CI.
if [[ -n "$CMD" ]]; then
  if printf '%s' "$CMD" | grep -qiE '(^|[[:space:]])(rm -rf /|mkfs|dd if=|shutdown|reboot|halt)([[:space:]]|$)'; then
    echo "CODEX PRE-BASH WARNING: high-risk command detected: $CMD"
    echo "Use explicit user approval and prefer safer alternatives."
  fi
fi

exit 0
