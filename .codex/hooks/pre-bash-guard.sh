#!/usr/bin/env bash
set -euo pipefail

# Codex payload shape can vary by version. Pull common command fields best-effort.
INPUT="$(cat || true)"
if command -v jq >/dev/null 2>&1; then
  CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // .command // .input.command // empty' 2>/dev/null || true)"
else
  CMD="$(printf '%s' "$INPUT" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("tool_input",{}).get("command") or d.get("command") or d.get("input",{}).get("command") or "")' 2>/dev/null || true)"
  echo "[codex-hook] pre-bash-guard: jq missing; using python fallback parser" >&2
fi

# Hook is advisory-only; hard enforcement belongs in .codex/rules/default.rules + CI.
if [[ -n "$CMD" ]]; then
  if printf '%s' "$CMD" | grep -qiE '(^|[[:space:]])(rm -rf /|mkfs|dd if=|shutdown|reboot|halt)([[:space:]]|$)'; then
    echo "CODEX PRE-BASH WARNING: high-risk command detected: $CMD"
    echo "Use explicit user approval and prefer safer alternatives."
  fi
fi

exit 0
