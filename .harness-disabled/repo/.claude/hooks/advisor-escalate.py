#!/usr/bin/env python3
"""Claude Code PostToolUse hook: backstop for the native `advisor` tool.

The native advisor (advisorModel: "fable" in settings.json) is a server-side
Anthropic API feature that auto-consults a second model at decision points.
It is known to silently stop firing once a transcript exceeds ~100K tokens
(returns advisor_tool_result_error / unavailable, with no fallback) — see
GitHub issues #66784, #66742, #66714, #67609. This hook detects the symptom
(the same tool call failing repeatedly) and nudges the agent to manually
spawn a Fable/Opus second opinion instead of silently retrying forever.

Ported from .cursor/hooks/advisor-escalate.py (Cursor has no native advisor
equivalent, so that hook is the primary mechanism there; here it's a
backstop for when the native one goes quiet). See
ai/rules/agent-user-global.md "Auto-escalation via the advisor tool" ->
"Known limitation" for the user-facing writeup of this gap.

Claude Code PostToolUse hook contract: stdin is a JSON payload describing
the tool call and its result; stdout, if non-empty JSON, may set
{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "..."}}
to inject a non-blocking nudge. `decision`/`reason` fields on PostToolUse
mean BLOCK, not nudge — never emit those here. Stop hooks only support
decision:"block" (no additionalContext), so the "before declaring task
complete" advisor trigger can't be covered by a hook; that stays a
prose-rule responsibility (see AGENTS.md "Advisor Trigger Conditions").
"""
import hashlib
import json
import os
import re
import sys
import time

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(HOOK_DIR, ".state", "advisor-escalate")
THRESHOLD = 3
RESET_AFTER_SECONDS = 1200
STATE_TTL_SECONDS = 7 * 24 * 3600

_ERROR_CLASS_RE = re.compile(r"[0-9a-f]{6,}|[0-9]+")


def safe_session_id(session_id):
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "unknown")[:80]


def state_file(session_id):
    return os.path.join(STATE_DIR, "failure-streak-%s.json" % safe_session_id(session_id))


def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_state(path, state):
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f)
    except OSError:
        pass


def prune_old_state_files():
    try:
        now = time.time()
        for name in os.listdir(STATE_DIR):
            path = os.path.join(STATE_DIR, name)
            try:
                if now - os.path.getmtime(path) > STATE_TTL_SECONDS:
                    os.remove(path)
            except OSError:
                pass
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


def error_text(data, result_obj):
    err = data.get("error") or result_obj.get("error") or ""
    if isinstance(err, dict):
        err = err.get("message", "")
    if not err:
        err = result_obj.get("output") or result_obj.get("content") or ""
    return str(err)


def error_class(text):
    return _ERROR_CLASS_RE.sub("#", text)[:300]


def is_excluded(text):
    # N6b (policy unchanged, scope corrected): "BLOCKED:" denials from
    # pre-tool-gate-v2.sh/hook-rule-loader.sh used to be excluded outright,
    # so an agent retrying the exact same denied call never accumulated a
    # recurrence signature and never got escalated — this hid the retry-loop
    # case the whole hook exists to catch. Gate denials now count like any
    # other tool failure; only genuine informational nudges stay excluded.
    if "hook additional context" in text.lower():
        return True
    return False


def is_advisor_recursion_guard(tool, tool_input):
    return tool == "Agent" and tool_input.get("model") == "fable"


def emit(context=None):
    if context:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context,
            }
        }))
    else:
        print("{}")


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        emit()
        return

    tool = data.get("tool_name") or data.get("tool") or data.get("toolName") or "unknown"
    tool_input = data.get("tool_input") or data.get("input") or data.get("toolInput") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    result_obj = (
        data.get("tool_output")
        or data.get("output")
        or data.get("result")
        or data.get("toolOutput")
        or {}
    )
    if not isinstance(result_obj, dict):
        result_obj = {}

    session_id = data.get("session_id") or data.get("sessionId") or "unknown"
    path = state_file(session_id)

    sig_prefix = hashlib.sha256(
        json.dumps({"tool": tool}, sort_keys=True).encode()
    ).hexdigest()[:12]

    if is_advisor_recursion_guard(tool, tool_input):
        emit()
        return

    if not is_failure(data, result_obj):
        state = load_state(path)
        state = {k: v for k, v in state.items() if not k.startswith(sig_prefix)}
        save_state(path, state)
        emit()
        return

    err_text = error_text(data, result_obj)
    if is_excluded(err_text):
        emit()
        return

    sig_input = json.dumps({"tool": tool, "input": tool_input}, sort_keys=True, default=str)
    err_sig = error_class(err_text)
    signature = (
        sig_prefix
        + hashlib.sha256(sig_input.encode()).hexdigest()[:16]
        + hashlib.sha256(err_sig.encode()).hexdigest()[:8]
    )

    state = load_state(path)
    now = time.time()
    entry = state.get(signature)
    if entry and (now - entry.get("ts", 0)) > RESET_AFTER_SECONDS:
        entry = None

    count = (entry.get("count", 0) if entry else 0) + 1
    state[signature] = {"count": count, "ts": now}
    save_state(path, state)
    prune_old_state_files()

    if count >= THRESHOLD and count % THRESHOLD == 0:
        msg = (
            "This exact failure on `%s` has now recurred %d times this session. "
            "The native advisor tool is known to go silent on long transcripts "
            "(no fallback fires when it does) — don't assume it will catch this. "
            "Get a second opinion now: "
            "Agent({model: \"fable\", subagent_type: \"fork\", description: \"root cause check\", "
            "prompt: \"Stuck on repeated %s failures. <describe what you tried and the error>. "
            "What's the actual root cause and what should I try instead?\"}). "
            "If Fable is unavailable, use model: \"opus\" instead."
        ) % (tool, count, tool)
        emit(msg)
    else:
        emit()


if __name__ == "__main__":
    main()
