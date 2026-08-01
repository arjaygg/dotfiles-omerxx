#!/usr/bin/env bash
# Fail-closed global Claude bridge for opted-in lifecycle repositories.
set -uo pipefail

EVENT="${1:-}"
case "$EVENT" in
    PreToolUse|SessionStart|UserPromptSubmit|Stop) ;;
    *) exit 0 ;;
esac

fail_closed() {
    case "$EVENT" in
        PreToolUse)
            printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"[HARD-BLOCK — DO NOT RETRY] Lifecycle hook bridge failed closed."}}'
            ;;
        Stop)
            printf '%s\n' '{"decision":"block","reason":"Lifecycle hook bridge failed closed.","lifecycle_bound":true}'
            ;;
        *)
            printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"Lifecycle hook bridge failed closed; repair lifecycle configuration before mutation."}}\n' "$EVENT"
            ;;
    esac
}

INPUT="$(cat)"
PARSE_RC=0
HOOK_CWD="$(printf '%s' "$INPUT" | python3 -c '
import json, sys
try:
    value = json.load(sys.stdin)
    cwd = value.get("cwd") if isinstance(value, dict) else None
    if cwd is not None and not isinstance(cwd, str):
        raise ValueError
    print(cwd or "")
except Exception:
    raise SystemExit(2)
' 2>/dev/null)" || PARSE_RC=$?
if [ "$PARSE_RC" -ne 0 ]; then
    HOOK_CWD="$PWD"
elif [ -z "$HOOK_CWD" ]; then
    HOOK_CWD="$PWD"
fi

REPO_ROOT="$(git -C "$HOOK_CWD" rev-parse --show-toplevel 2>/dev/null)" || exit 0
CONFIG="$REPO_ROOT/.claude-atomic.yaml"
MODE="$(python3 - "$CONFIG" <<'PY' 2>/dev/null
import os, re, stat, sys
path = sys.argv[1]
try:
    metadata = os.lstat(path)
except FileNotFoundError:
    print("disabled")
    raise SystemExit
except OSError:
    print("error")
    raise SystemExit
if not stat.S_ISREG(metadata.st_mode):
    print("error")
    raise SystemExit
try:
    lines = open(path, encoding="utf-8").read().splitlines()
except (OSError, UnicodeError):
    print("error")
    raise SystemExit
starts = []
for index, raw in enumerate(lines):
    clean = raw.split("#", 1)[0].rstrip()
    if clean and not clean[0].isspace() and clean.startswith("lifecycle"):
        if clean != "lifecycle:":
            print("error")
            raise SystemExit
        starts.append(index)
if not starts:
    print("disabled")
    raise SystemExit
if len(starts) != 1:
    print("error")
    raise SystemExit
enabled = []
for raw in lines[starts[0] + 1:]:
    clean = raw.split("#", 1)[0].rstrip()
    if clean and not clean[0].isspace():
        break
    if clean.lstrip().startswith("enabled"):
        match = re.fullmatch(r"\s+enabled:\s*([^\s]+)\s*", clean)
        if not match:
            print("error")
            raise SystemExit
        enabled.append(match.group(1).strip("\"'").lower())
if len(enabled) != 1:
    print("error")
elif enabled[0] in {"true", "yes", "on", "1"}:
    print("enabled")
elif enabled[0] in {"false", "no", "off", "0"}:
    print("disabled")
else:
    print("error")
PY
)" || MODE="error"

case "$MODE" in
    disabled) exit 0 ;;
    enabled) ;;
    *) fail_closed; exit 0 ;;
esac
if [ "$PARSE_RC" -ne 0 ]; then
    fail_closed
    exit 0
fi

ADAPTER="$HOME/.dotfiles/scripts/ai/lifecycle_adapter.py"
if [ ! -f "$ADAPTER" ]; then
    fail_closed
    exit 0
fi
OUTPUT="$(printf '%s' "$INPUT" | python3 "$ADAPTER" hook --event "$EVENT" 2>/dev/null)"
RC=$?
if [ "$RC" -ne 0 ]; then
    fail_closed
    exit 0
fi
if [ -n "$OUTPUT" ] && ! printf '%s' "$OUTPUT" | python3 -c 'import json,sys; value=json.load(sys.stdin); assert isinstance(value,dict)' 2>/dev/null; then
    fail_closed
    exit 0
fi
if [ "$EVENT" = "Stop" ]; then
    if [ -z "$OUTPUT" ]; then
        fail_closed
        exit 0
    fi
    if printf '%s' "$OUTPUT" | python3 -c 'import json,sys; raise SystemExit(0 if json.load(sys.stdin).get("lifecycle_bound") is False else 1)' 2>/dev/null; then
        exit 0
    fi
elif [ "$EVENT" != "PreToolUse" ] && [ -z "$OUTPUT" ]; then
    fail_closed
    exit 0
fi
[ -n "$OUTPUT" ] && printf '%s\n' "$OUTPUT"
exit 0
