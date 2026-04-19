#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat || true)"

EXIT_CODE="$(printf '%s' "$INPUT" | jq -r '.tool_response.exitCode // .tool_response.exit_code // .exitCode // .exit_code // 0' 2>/dev/null || echo 0)"
CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // .command // .input.command // empty' 2>/dev/null || true)"

if [[ "${EXIT_CODE:-0}" != "0" ]]; then
  echo "CODEX POST-BASH NOTICE: command failed (exit=${EXIT_CODE})${CMD:+: $CMD}"
fi

exit 0
