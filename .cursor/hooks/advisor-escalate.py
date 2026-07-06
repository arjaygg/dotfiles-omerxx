#!/usr/bin/env python3
"""Cursor postToolUse hook: replicates Claude Code's advisor-tool "recurring
error" trigger. Tracks identical tool-call failures across calls; after N
repeats, injects additional_context nudging escalation to a frontier-model
Task. See .cursor/rules/model-routing.mdc "Auto-escalation" for the pattern.

Schema note: exact postToolUse payload field names are not fully documented
by Cursor. This tries several plausible field names and fails open (no
nudge, no error) if it can't determine failure. Set ADVISOR_ESCALATE_DEBUG=1
to log raw payloads to .cursor/hooks/.state/postuse-debug.log, then adjust
field names below if the live schema differs.
"""
import hashlib
import json
import os
import sys
import time

STATE_DIR = ".cursor/hooks/.state"
STATE_FILE = os.path.join(STATE_DIR, "failure-streak.json")
DEBUG_FILE = os.path.join(STATE_DIR, "postuse-debug.log")
THRESHOLD = 3
RESET_AFTER_SECONDS = 1200


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except OSError:
        pass


def is_failure(data, result_obj):
    if "success" in result_obj:
        return result_obj.get("success") is False
    for key in ("isError", "is_error"):
        if key in result_obj:
            return bool(result_obj[key])
    exit_code = result_obj.get("exit_code", result_obj.get("exitCode"))
    if exit_code is not None:
        try:
            return int(exit_code) != 0
        except (TypeError, ValueError):
            pass
    err = data.get("error") or result_obj.get("error")
    return bool(err)


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    raw = sys.stdin.read()

    if os.environ.get("ADVISOR_ESCALATE_DEBUG"):
        try:
            with open(DEBUG_FILE, "a") as f:
                f.write(raw + "\n---\n")
        except OSError:
            pass

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        print("{}")
        return

    tool = data.get("tool_name") or data.get("tool") or data.get("toolName") or "unknown"
    tool_input = data.get("tool_input") or data.get("input") or data.get("toolInput") or {}
    result_obj = (
        data.get("tool_output")
        or data.get("output")
        or data.get("result")
        or data.get("toolOutput")
        or {}
    )
    if not isinstance(result_obj, dict):
        result_obj = {}

    sig_prefix = hashlib.sha256(
        json.dumps({"tool": tool}, sort_keys=True).encode()
    ).hexdigest()[:12]

    if not is_failure(data, result_obj):
        state = load_state()
        state = {k: v for k, v in state.items() if not k.startswith(sig_prefix)}
        save_state(state)
        print("{}")
        return

    sig_input = json.dumps({"tool": tool, "input": tool_input}, sort_keys=True, default=str)
    signature = sig_prefix + hashlib.sha256(sig_input.encode()).hexdigest()[:16]

    state = load_state()
    now = time.time()
    entry = state.get(signature)
    if entry and (now - entry.get("ts", 0)) > RESET_AFTER_SECONDS:
        entry = None

    count = (entry.get("count", 0) if entry else 0) + 1
    state[signature] = {"count": count, "ts": now}
    save_state(state)

    if count >= THRESHOLD and count % THRESHOLD == 0:
        msg = (
            "This exact failure on `%s` has now recurred %d times. "
            "Per .cursor/rules/model-routing.mdc: stop retrying the same way. "
            "Spawn a Task with model claude-opus-4-8-thinking-high (or "
            "claude-fable-5-thinking-high for a genuinely hard/ambiguous case) "
            "for a second opinion on the root cause before trying again."
        ) % (tool, count)
        print(json.dumps({"additional_context": msg}))
    else:
        print("{}")


if __name__ == "__main__":
    main()
