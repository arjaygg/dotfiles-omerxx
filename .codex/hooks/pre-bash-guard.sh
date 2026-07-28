#!/usr/bin/env bash
set -euo pipefail

# Codex payload shape can vary by version. Pull common fields best-effort.
INPUT="$(cat || true)"
if command -v jq >/dev/null 2>&1; then
  CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // .command // .input.command // empty' 2>/dev/null || true)"
else
  CMD="$(printf '%s' "$INPUT" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("tool_input",{}).get("command") or d.get("command") or d.get("input",{}).get("command") or "")' 2>/dev/null || true)"
  echo "[codex-hook] pre-bash-guard: jq missing; using python fallback parser" >&2
fi

# Shared context gate: malformed payloads and missing runtimes fail open. Medium
# and rollout-phase large reads warn; huge/generated reads and promoted large
# reads exit 2 so Codex blocks the tool call.
CONTEXT_GATE="$HOME/.dotfiles/.local/bin/context-file-gate"
if [[ -x "$CONTEXT_GATE" ]]; then
  CONTEXT_RESULT="$(printf '%s' "$INPUT" | "$CONTEXT_GATE" \
    --client codex --event pre_tool_use --json 2>/dev/null || true)"
  if [[ -n "$CONTEXT_RESULT" ]]; then
    CONTEXT_DECISION="$(printf '%s' "$CONTEXT_RESULT" | python3 -c \
      'import json,sys; print(json.load(sys.stdin).get("decision", "allow"))' \
      2>/dev/null || echo allow)"
    CONTEXT_MESSAGE="$(printf '%s' "$CONTEXT_RESULT" | python3 -c \
      'import json,sys; print(json.load(sys.stdin).get("message", ""))' \
      2>/dev/null || true)"
    if [[ "$CONTEXT_DECISION" == "deny" ]]; then
      printf 'CODEX CONTEXT BLOCK: %s\n' "$CONTEXT_MESSAGE" >&2
      exit 2
    elif [[ "$CONTEXT_DECISION" == "warn" && -n "$CONTEXT_MESSAGE" ]]; then
      printf 'CODEX CONTEXT WARNING: %s\n' "$CONTEXT_MESSAGE" >&2
      python3 -c \
        'import json,sys; print(json.dumps({"systemMessage": "CODEX CONTEXT WARNING: " + sys.argv[1]}))' \
        "$CONTEXT_MESSAGE" 2>/dev/null || true
    fi
  fi
fi

# Existing command-safety advisory remains independent of context routing.
if [[ -n "$CMD" ]]; then
  if printf '%s' "$CMD" | grep -qiE '(^|[[:space:]])(rm -rf /|mkfs|dd if=|shutdown|reboot|halt)([[:space:]]|$)'; then
    echo "CODEX PRE-BASH WARNING: high-risk command detected: $CMD"
    echo "Use explicit user approval and prefer safer alternatives."
  fi
fi

exit 0
