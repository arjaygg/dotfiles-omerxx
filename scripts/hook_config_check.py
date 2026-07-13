#!/usr/bin/env python3
"""Statically validate Claude Code hook settings without executing hooks."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


ALLOWED_EVENTS = frozenset(
    {
        "SessionStart",
        "Setup",
        "InstructionsLoaded",
        "UserPromptSubmit",
        "UserPromptExpansion",
        "MessageDisplay",
        "PreToolUse",
        "PermissionRequest",
        "PermissionDenied",
        "PostToolUse",
        "PostToolUseFailure",
        "PostToolBatch",
        "Notification",
        "SubagentStart",
        "SubagentStop",
        "TaskCreated",
        "TaskCompleted",
        "Stop",
        "StopFailure",
        "TeammateIdle",
        "ConfigChange",
        "CwdChanged",
        "FileChanged",
        "WorktreeCreate",
        "WorktreeRemove",
        "PreCompact",
        "PostCompact",
        "SessionEnd",
        "Elicitation",
        "ElicitationResult",
    }
)
MATCHER_UNSUPPORTED = frozenset(
    {
        "UserPromptSubmit",
        "PostToolBatch",
        "Stop",
        "TeammateIdle",
        "TaskCreated",
        "TaskCompleted",
        "WorktreeCreate",
        "WorktreeRemove",
        "MessageDisplay",
        "CwdChanged",
    }
)
HANDLER_TYPES = frozenset({"command", "http", "mcp_tool", "prompt", "agent"})
REQUIRED_STRING_FIELDS = {
    "command": ("command",),
    "http": ("url",),
    "mcp_tool": ("server", "tool"),
    "prompt": ("prompt",),
    "agent": ("prompt",),
}


@dataclass(frozen=True)
class Issue:
    event: str
    rule: str
    message: str


def load_baseline(path: Path) -> list[Issue]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("hook baseline must be an array")

    issues: list[Issue] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(field), str) for field in ("event", "rule", "message")
        ):
            raise ValueError(f"baseline entry {index} requires event, rule, and message strings")
        issues.append(Issue(entry["event"], entry["rule"], entry["message"]))
    return issues


def compare_baseline(actual: list[Issue], expected: list[Issue]) -> list[Issue]:
    actual_by_key = {(issue.event, issue.rule, issue.message): issue for issue in actual}
    expected_by_key = {(issue.event, issue.rule, issue.message): issue for issue in expected}
    findings: list[Issue] = []

    for key in sorted(expected_by_key.keys() - actual_by_key.keys()):
        issue = expected_by_key[key]
        findings.append(
            Issue(issue.event, "baseline-missing", f"expected baseline finding disappeared: {issue.rule}: {issue.message}")
        )
    for key in sorted(actual_by_key.keys() - expected_by_key.keys()):
        issue = actual_by_key[key]
        findings.append(Issue(issue.event, "baseline-new", f"new hook configuration finding: {issue.rule}: {issue.message}"))
    return findings


def check_hooks(settings: dict[str, object]) -> list[Issue]:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return [Issue("hooks", "invalid-hooks", "settings.hooks must be an object")]

    issues: list[Issue] = []
    for event, groups in hooks.items():
        if event not in ALLOWED_EVENTS:
            issues.append(Issue(event, "unknown-event", "event is not in the current hook reference"))
        if not isinstance(groups, list):
            issues.append(Issue(event, "invalid-groups", "event value must be an array"))
            continue
        for group in groups:
            if not isinstance(group, dict):
                issues.append(Issue(event, "invalid-group", "matcher group must be an object"))
                continue
            if event in MATCHER_UNSUPPORTED and "matcher" in group:
                issues.append(Issue(event, "ignored-matcher", "matcher is ignored for this event"))
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                issues.append(Issue(event, "invalid-handlers", "group.hooks must be an array"))
                continue
            if event in {"WorktreeCreate", "WorktreeRemove"} and len(handlers) > 1:
                issues.append(
                    Issue(
                        event,
                        "parallel-handlers",
                        "matching handlers execute in parallel; ordering is not guaranteed",
                    )
                )
            for handler in handlers:
                if not isinstance(handler, dict):
                    issues.append(Issue(event, "invalid-handler", "handler must be an object"))
                    continue
                handler_type = handler.get("type")
                if not isinstance(handler_type, str) or handler_type not in HANDLER_TYPES:
                    issues.append(Issue(event, "unknown-handler-type", "handler type is unsupported"))
                    continue
                for field in REQUIRED_STRING_FIELDS[handler_type]:
                    if field not in handler:
                        issues.append(Issue(event, f"missing-{field}", f"{handler_type} handler requires {field}"))
                    elif not isinstance(handler[field], str):
                        issues.append(Issue(event, f"invalid-{field}", f"{field} must be a string"))
    return issues


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("settings", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        settings = json.loads(args.settings.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"invalid settings: {error}", file=sys.stderr)
        return 2
    issues = check_hooks(settings)
    if args.baseline:
        try:
            issues = compare_baseline(issues, load_baseline(args.baseline))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            print(f"invalid hook baseline: {error}", file=sys.stderr)
            return 2
    if args.as_json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    else:
        for issue in issues:
            print(f"{issue.event}: {issue.rule}: {issue.message}")
        if not issues:
            print("hook config check passed")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
