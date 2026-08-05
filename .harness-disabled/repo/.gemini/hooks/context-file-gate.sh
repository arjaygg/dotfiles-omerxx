#!/usr/bin/env bash
set -uo pipefail

INPUT="$(cat || true)"
NORMALIZED="$(python3 - 3<<<"$INPUT" 2>/dev/null <<'PY' || printf '%s' "$INPUT"
import json
import os

with os.fdopen(3) as stream:
    payload = json.load(stream)
tool_call = payload.get("toolCall")
if isinstance(tool_call, dict):
    args = tool_call.get("args")
    if isinstance(args, dict):
        tool_name = str(tool_call.get("name", ""))

        def unquote(value):
            if (
                isinstance(value, str)
                and len(value) >= 2
                and value[0] == value[-1]
                and value[0] in {"'", '"'}
            ):
                return value[1:-1]
            return value

        if tool_name == "run_command" and "command" not in args:
            command = unquote(args.get("CommandLine"))
            if isinstance(command, str):
                args["command"] = command

        if tool_name == "view_file" and "path" not in args:
            path = unquote(args.get("AbsolutePath"))
            if isinstance(path, str):
                args["path"] = path

        if tool_name == "view_file" and "limit" not in args:
            try:
                start = int(args.get("StartLine"))
                end = int(args.get("EndLine"))
            except (TypeError, ValueError):
                pass
            else:
                if end >= start:
                    args["limit"] = end - start + 1

print(json.dumps(payload, separators=(",", ":")))
PY
)"
RESULT="$(printf '%s' "$NORMALIZED" | "$HOME/.dotfiles/.local/bin/context-file-gate" \
  --client agy --event pre_tool_use --json 2>/dev/null || true)"

python3 - "$RESULT" <<'PY'
import json
import sys

try:
    result = json.loads(sys.argv[1])
except (IndexError, json.JSONDecodeError, TypeError):
    print('{"allow_tool":true}')
    raise SystemExit(0)

decision = result.get("decision", "allow")
message = result.get("message", "")
if decision == "deny":
    print(json.dumps({"allow_tool": False, "deny_reason": message}))
else:
    if decision == "warn" and message:
        print(f"GEMINI CONTEXT WARNING: {message}", file=sys.stderr)
    print('{"allow_tool":true}')
PY
