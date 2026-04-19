#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat || true)"

if command -v jq >/dev/null 2>&1; then
  EXIT_CODE="$(printf '%s' "$INPUT" | jq -r '.tool_response.exitCode // .tool_response.exit_code // .exitCode // .exit_code // 0' 2>/dev/null || echo 0)"
  CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // .command // .input.command // empty' 2>/dev/null || true)"
else
  EXIT_CODE="$(printf '%s' "$INPUT" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("tool_response",{}).get("exitCode", d.get("tool_response",{}).get("exit_code", d.get("exitCode", d.get("exit_code", 0)))))' 2>/dev/null || echo 0)"
  CMD="$(printf '%s' "$INPUT" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("tool_input",{}).get("command") or d.get("command") or d.get("input",{}).get("command") or "")' 2>/dev/null || true)"
  echo "[codex-hook] post-bash-observe: jq missing; using python fallback parser" >&2
fi

if [[ "${EXIT_CODE:-0}" != "0" ]]; then
  if [[ -n "${CMD:-}" ]]; then
    printf 'CODEX POST-BASH NOTICE: command failed (exit=%s): %q\n' "$EXIT_CODE" "$CMD"
  else
    printf 'CODEX POST-BASH NOTICE: command failed (exit=%s)\n' "$EXIT_CODE"
  fi
fi

exit 0
