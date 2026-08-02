#!/usr/bin/env bash
# Fail-closed global Claude bridge for explicitly opted-in lifecycle repositories.
set -uo pipefail

EVENT="${1:-}"
case "$EVENT" in
    PreToolUse|SessionStart|UserPromptSubmit|Stop) ;;
    *) exit 0 ;;
esac

unbound() {
    printf '{"lifecycle_hook":{"schema_version":1,"processed":true,"event":"%s","binding":"unbound"}}\n' "$EVENT"
}

fail_closed() {
    case "$EVENT" in
        PreToolUse)
            printf '%s\n' '{"lifecycle_hook":{"schema_version":1,"processed":true,"event":"PreToolUse","binding":"bound"},"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"[HARD-BLOCK — DO NOT RETRY] Lifecycle hook bridge failed closed."}}'
            ;;
        Stop)
            printf '%s\n' '{"lifecycle_hook":{"schema_version":1,"processed":true,"event":"Stop","binding":"bound"},"decision":"block","reason":"Lifecycle hook bridge failed closed."}'
            ;;
        *)
            printf '{"lifecycle_hook":{"schema_version":1,"processed":true,"event":"%s","binding":"bound"},"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"Lifecycle hook bridge failed closed; repair lifecycle configuration before mutation."}}\n' "$EVENT" "$EVENT"
            ;;
    esac
}

if ! command -v python3 >/dev/null 2>&1 || ! command -v git >/dev/null 2>&1; then
    fail_closed
    exit 0
fi

INPUT="$(cat)"
PARSE_RC=0
HOOK_CWD="$(printf '%s' "$INPUT" | python3 -c '
import json, pathlib, sys
try:
    value = json.load(sys.stdin)
    if not isinstance(value, dict):
        raise ValueError
    cwd = value.get("cwd")
    session = value.get("session_id")
    if not isinstance(cwd, str) or not pathlib.Path(cwd).is_absolute():
        raise ValueError
    if not isinstance(session, str) or not session:
        raise ValueError
    print(cwd)
except Exception:
    raise SystemExit(2)
' 2>/dev/null)" || PARSE_RC=$?
[ -n "$HOOK_CWD" ] || HOOK_CWD="$PWD"
if [ "$PARSE_RC" -ne 0 ]; then
    fail_closed
    exit 0
fi

# A silent fallback requires proof that no worktree marker exists in this path ancestry.
HAS_GIT_MARKER="$(python3 - "$HOOK_CWD" <<'PYMARKER' 2>/dev/null
import pathlib, sys
try:
    path = pathlib.Path(sys.argv[1]).resolve(strict=True)
except (OSError, RuntimeError):
    raise SystemExit(2)
if path.is_file():
    path = path.parent
print("yes" if any((parent / ".git").exists() for parent in (path, *path.parents)) else "no")
PYMARKER
)" || {
    fail_closed
    exit 0
}
if [ "$HAS_GIT_MARKER" = "no" ]; then
    unbound
    exit 0
fi

REPO_ROOT="$(git -C "$HOOK_CWD" rev-parse --show-toplevel 2>/dev/null)" || {
    fail_closed
    exit 0
}
CONFIG="$REPO_ROOT/.claude-atomic.yaml"
MODE="$(python3 - "$CONFIG" <<'PYMODE' 2>/dev/null
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
if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
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
PYMODE
)" || MODE="error"
case "$MODE" in
    disabled) unbound; exit 0 ;;
    enabled) ;;
    *) fail_closed; exit 0 ;;
esac
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DOTFILES_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
ADAPTER="$DOTFILES_ROOT/scripts/ai/lifecycle_adapter.py"
if [ ! -f "$ADAPTER" ] || [ -L "$ADAPTER" ]; then
    fail_closed
    exit 0
fi
if ! git -C "$DOTFILES_ROOT" ls-files --error-unmatch -- scripts/ai/lifecycle_adapter.py >/dev/null 2>&1; then
    fail_closed
    exit 0
fi
RESOLVED_ADAPTER="$(python3 - "$ADAPTER" <<'PYREAL' 2>/dev/null
import pathlib, sys
try:
    print(pathlib.Path(sys.argv[1]).resolve(strict=True))
except (OSError, RuntimeError):
    raise SystemExit(2)
PYREAL
)" || {
    fail_closed
    exit 0
}
[ "$RESOLVED_ADAPTER" = "$ADAPTER" ] || {
    fail_closed
    exit 0
}

OUTPUT="$(printf '%s' "$INPUT" | python3 "$ADAPTER" hook --event "$EVENT" 2>/dev/null)"
RC=$?
if [ "$RC" -ne 0 ] || [ -z "$OUTPUT" ]; then
    fail_closed
    exit 0
fi
VALID_RC=0
python3 -c '
import json, re, sys
expected = sys.argv[1]
try:
    value = json.loads(sys.stdin.read())
    if not isinstance(value, dict):
        raise ValueError
    envelope = value.get("lifecycle_hook")
    if not isinstance(envelope, dict):
        raise ValueError
    base_keys = {"schema_version", "processed", "event", "binding"}
    binding = envelope.get("binding")
    expected_keys = base_keys | ({"run_id"} if binding == "bound" else set())
    if set(envelope) != expected_keys:
        raise ValueError
    if (
        envelope.get("schema_version") != 1
        or envelope.get("processed") is not True
        or envelope.get("event") != expected
        or binding not in {"bound", "unbound"}
    ):
        raise ValueError
    if binding == "bound":
        run_id = envelope.get("run_id")
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
            raise ValueError
    if expected == "PreToolUse":
        if set(value) == {"lifecycle_hook"}:
            pass
        elif set(value) == {"lifecycle_hook", "hookSpecificOutput"}:
            specific = value["hookSpecificOutput"]
            if (
                not isinstance(specific, dict)
                or set(specific) != {"hookEventName", "permissionDecision", "permissionDecisionReason"}
                or specific.get("hookEventName") != expected
                or specific.get("permissionDecision") != "deny"
                or not isinstance(specific.get("permissionDecisionReason"), str)
                or not specific["permissionDecisionReason"].startswith("[HARD-BLOCK")
            ):
                raise ValueError
        else:
            raise ValueError
    elif expected in {"SessionStart", "UserPromptSubmit"}:
        if binding == "unbound" and set(value) == {"lifecycle_hook"}:
            pass
        else:
            if set(value) != {"lifecycle_hook", "hookSpecificOutput"}:
                raise ValueError
            specific = value["hookSpecificOutput"]
            if (
                not isinstance(specific, dict)
                or set(specific) != {"hookEventName", "additionalContext"}
                or specific.get("hookEventName") != expected
                or not isinstance(specific.get("additionalContext"), str)
                or not specific["additionalContext"]
            ):
                raise ValueError
    elif binding == "unbound":
        if set(value) != {"lifecycle_hook"}:
            raise ValueError
    elif set(value) == {"lifecycle_hook"}:
        pass
    elif set(value) == {"lifecycle_hook", "decision", "reason"}:
        if value.get("decision") != "block" or not isinstance(value.get("reason"), str) or not value["reason"]:
            raise ValueError
    else:
        raise ValueError
except Exception:
    raise SystemExit(2)
' "$EVENT" <<< "$OUTPUT" 2>/dev/null || VALID_RC=$?
if [ "$VALID_RC" -ne 0 ]; then
    fail_closed
    exit 0
fi

# The Stop envelope is always emitted, including the unbound case. stop.sh
# distinguishes "unbound, fall through to the legacy gate" from "bridge broken,
# fail closed" solely by parsing this envelope, so swallowing the unbound Stop
# envelope here deadlocks every unbound session: stop.sh sees empty output,
# cannot resolve a binding, and blocks Stop forever.
printf '%s\n' "$OUTPUT"
exit 0
