#!/usr/bin/env python3
"""Statically validate Claude Code hook settings without executing hooks."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
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
MCP_MATCH_ALL = frozenset({"", "*", ".*"})


@dataclass(frozen=True)
class Issue:
    event: str
    rule: str
    message: str


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
            rewrite_handlers = [
                handler
                for handler in handlers
                if isinstance(handler, dict)
                and handler.get("type") == "command"
                and isinstance(handler.get("command"), str)
                and _command_may_rewrite_input(handler["command"])
            ]
            if event == "PreToolUse" and len(rewrite_handlers) > 1:
                issues.append(
                    Issue(
                        event,
                        "multiple-input-rewriters",
                        "multiple PreToolUse command hooks may rewrite tool input",
                    )
                )
            for handler in handlers:
                if not isinstance(handler, dict):
                    issues.append(Issue(event, "invalid-handler", "handler must be an object"))
                    continue
                handler_type = handler.get("type")
                if handler_type not in HANDLER_TYPES:
                    issues.append(Issue(event, "unknown-handler-type", "handler type is unsupported"))
                    continue
                if handler_type == "command":
                    if "command" not in handler:
                        issues.append(Issue(event, "missing-command", "command handler requires command"))
                    elif not isinstance(handler["command"], str):
                        issues.append(Issue(event, "invalid-command", "command must be a string"))
                    elif (
                        event == "PreToolUse"
                        and "pre-tool-gate-v2.sh" in handler["command"]
                        and not _matcher_covers_mcp_tools(group.get("matcher"))
                    ):
                        issues.append(
                            Issue(
                                event,
                                "missing-mcp-tool-matcher",
                                "pre-tool-gate-v2.sh contains MCP tool logic but this matcher excludes mcp__* tools",
                            )
                        )
    return issues


def _matcher_covers_mcp_tools(matcher: object) -> bool:
    if matcher is None:
        return True
    if not isinstance(matcher, str):
        return False
    return matcher.strip() in MCP_MATCH_ALL or "mcp__" in matcher


def _command_may_rewrite_input(command: str) -> bool:
    lowered = command.lower()
    return "rewrite" in lowered or "updatedinput" in lowered


def summarize_issues(issues: Sequence[Issue]) -> dict[str, object]:
    return {
        "total": len(issues),
        "by_rule": dict(sorted(Counter(issue.rule for issue in issues).items())),
        "by_event": dict(sorted(Counter(issue.event for issue in issues).items())),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("settings", type=Path)
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", dest="as_json")
    output_group.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)
    try:
        settings = json.loads(args.settings.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"invalid settings: {error}", file=sys.stderr)
        return 2
    issues = check_hooks(settings)
    if args.as_json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif args.summary:
        print(json.dumps(summarize_issues(issues), indent=2))
    else:
        for issue in issues:
            print(f"{issue.event}: {issue.rule}: {issue.message}")
        if not issues:
            print("hook config check passed")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
