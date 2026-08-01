#!/usr/bin/env python3
"""Validate lifecycle bridge output for outer hook dispatchers."""
from __future__ import annotations

import json
import re
import sys

RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def fail() -> None:
    raise SystemExit(2)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {
        "PreToolUse", "SessionStart", "UserPromptSubmit", "Stop",
    }:
        fail()
    event = sys.argv[1]
    raw = sys.stdin.buffer.read(65537)
    if not raw or len(raw) > 65536:
        fail()
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError):
        fail()
    if not isinstance(value, dict):
        fail()
    envelope = value.get("lifecycle_hook")
    if not isinstance(envelope, dict):
        fail()
    binding = envelope.get("binding")
    base = {"schema_version", "processed", "event", "binding"}
    keys = base | ({"run_id"} if binding == "bound" else set())
    if (
        set(envelope) != keys
        or envelope.get("schema_version") != 1
        or envelope.get("processed") is not True
        or envelope.get("event") != event
        or binding not in {"bound", "unbound"}
    ):
        fail()
    run_id = envelope.get("run_id")
    if binding == "bound" and (
        not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id)
    ):
        fail()

    if set(value) == {"lifecycle_hook"}:
        if binding == "unbound" or event in {"PreToolUse", "Stop"}:
            print(binding)
            return
        fail()

    if event == "PreToolUse" and set(value) == {"lifecycle_hook", "hookSpecificOutput"}:
        specific = value["hookSpecificOutput"]
        if (
            not isinstance(specific, dict)
            or set(specific) != {
                "hookEventName", "permissionDecision", "permissionDecisionReason",
            }
            or specific.get("hookEventName") != event
            or specific.get("permissionDecision") != "deny"
            or not isinstance(specific.get("permissionDecisionReason"), str)
            or not specific["permissionDecisionReason"].startswith("[HARD-BLOCK")
            or len(specific["permissionDecisionReason"]) > 4096
        ):
            fail()
        print(binding)
        return

    if event in {"SessionStart", "UserPromptSubmit"} and set(value) == {
        "lifecycle_hook", "hookSpecificOutput",
    }:
        specific = value["hookSpecificOutput"]
        if (
            not isinstance(specific, dict)
            or set(specific) != {"hookEventName", "additionalContext"}
            or specific.get("hookEventName") != event
            or not isinstance(specific.get("additionalContext"), str)
            or not specific["additionalContext"]
            or len(specific["additionalContext"]) > 4096
        ):
            fail()
        print(binding)
        return

    if event == "Stop" and binding == "bound" and set(value) == {
        "lifecycle_hook", "decision", "reason",
    }:
        if (
            value.get("decision") != "block"
            or not isinstance(value.get("reason"), str)
            or not value["reason"]
            or len(value["reason"]) > 4096
        ):
            fail()
        print(binding)
        return
    fail()


if __name__ == "__main__":
    main()
