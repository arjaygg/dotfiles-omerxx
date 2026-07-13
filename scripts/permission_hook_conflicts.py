#!/usr/bin/env python3
"""Report exact and opt-in conservative permission/hook contradictions."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TOOL_EVENTS = frozenset({"PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest", "PermissionDenied"})


@dataclass(frozen=True)
class Conflict:
    event: str
    rule: str
    detail: str


def _rules(permissions: object, key: str) -> set[str]:
    if not isinstance(permissions, dict):
        return set()
    values = permissions.get(key)
    return {value for value in values if isinstance(value, str)} if isinstance(values, list) else set()


def _tool_name(rule: str) -> str:
    return rule.split("(", 1)[0].strip()


def _hook_candidates(settings: dict[str, Any]) -> list[tuple[str, str]]:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return []
    candidates: list[tuple[str, str]] = []
    for event, groups in hooks.items():
        if event not in TOOL_EVENTS or not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher")
            if isinstance(matcher, str):
                candidates.append((event, matcher))
            handlers = group.get("hooks")
            if isinstance(handlers, list):
                candidates.extend(
                    (event, handler["if"])
                    for handler in handlers
                    if isinstance(handler, dict) and isinstance(handler.get("if"), str)
                )
    return candidates


def check_potential_overlaps(settings: dict[str, Any]) -> list[Conflict]:
    """Report possible overlaps without claiming regex or runtime semantics."""

    deny = _rules(settings.get("permissions"), "deny")
    conflicts: list[Conflict] = []
    for event, matcher in sorted(set(_hook_candidates(settings))):
        # Do not guess about alternation or regex-like matchers in this mode.
        if "|" in matcher or any(char in matcher for char in "*[]()\\"):
            continue
        matcher_tools = {_tool_name(value) for value in matcher.split("|")}
        for rule in sorted(deny):
            tool = _tool_name(rule)
            if "(" not in rule or rule == matcher:
                continue
            if tool in matcher_tools or "*" in matcher_tools:
                conflicts.append(
                    Conflict(
                        event,
                        "potential-wildcard-overlap",
                        f"permission deny may cover hook matcher {matcher}: {rule}",
                    )
                )
    return conflicts


def check_conflicts(settings: dict[str, Any], *, include_overlaps: bool = False) -> list[Conflict]:
    permissions = settings.get("permissions")
    allow = _rules(permissions, "allow")
    ask = _rules(permissions, "ask")
    deny = _rules(permissions, "deny")
    conflicts = [
        Conflict("permissions", "permission-conflict", f"exact rule is both denied and {kind}: {rule}")
        for rule in sorted(deny & (allow | ask))
        for kind in ("allowed" if rule in allow else "asked",)
    ]

    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return conflicts + (check_potential_overlaps(settings) if include_overlaps else [])
    seen: set[tuple[str, str]] = set()
    for event, groups in hooks.items():
        if event not in TOOL_EVENTS or not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            candidates = []
            matcher = group.get("matcher")
            if isinstance(matcher, str):
                candidates.append(matcher)
            handlers = group.get("hooks")
            if isinstance(handlers, list):
                candidates.extend(
                    handler["if"]
                    for handler in handlers
                    if isinstance(handler, dict) and isinstance(handler.get("if"), str)
                )
            for candidate in candidates:
                key = (event, candidate)
                if candidate in deny and key not in seen:
                    seen.add(key)
                    conflicts.append(
                        Conflict(
                            event,
                            "hook-unreachable-under-deny",
                            f"exact hook matcher is covered by permission deny: {candidate}",
                        )
                    )
    if include_overlaps:
        conflicts.extend(check_potential_overlaps(settings))
    return conflicts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("settings", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--include-overlaps", action="store_true", help="report conservative wildcard/matcher overlaps")
    args = parser.parse_args(argv)
    try:
        settings = json.loads(args.settings.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"permission/hook conflict check rejected input: {error}", file=sys.stderr)
        return 2
    if not isinstance(settings, dict):
        print("permission/hook conflict check requires a JSON object", file=sys.stderr)
        return 2
    conflicts = check_conflicts(settings, include_overlaps=args.include_overlaps)
    if args.as_json:
        print(json.dumps([asdict(conflict) for conflict in conflicts], indent=2))
    else:
        for conflict in conflicts:
            print(f"{conflict.event}: {conflict.rule}: {conflict.detail}")
        if not conflicts:
            print("permission/hook conflict check passed")
    return 1 if conflicts else 0


if __name__ == "__main__":
    raise SystemExit(main())
