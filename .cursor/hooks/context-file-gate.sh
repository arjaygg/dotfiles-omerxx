#!/usr/bin/env bash
set -uo pipefail

INPUT="$(cat || true)"
RESULT="$(printf '%s' "$INPUT" | "$HOME/.dotfiles/.local/bin/context-file-gate" \
  --client cursor --event pre_tool_use --json 2>/dev/null || true)"

python3 - "$RESULT" <<'PY'
import json
import sys

try:
    result = json.loads(sys.argv[1])
except (IndexError, json.JSONDecodeError, TypeError):
    print('{"permission":"allow"}')
    raise SystemExit(0)

decision = result.get("decision", "allow")
message = result.get("message", "")
if decision == "deny":
    print(json.dumps({
        "permission": "deny",
        "user_message": message,
        "agent_message": message,
    }))
else:
    if decision == "warn" and message:
        print(f"CURSOR CONTEXT WARNING: {message}", file=sys.stderr)
    print('{"permission":"allow"}')
PY
