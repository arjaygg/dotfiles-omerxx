#!/usr/bin/env python3
"""Check file-backed hook commands against the tracked distribution."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class Issue:
    event: str
    reference: str
    rule: str
    message: str


FILE_REFERENCE = re.compile(r"(?:\$HOME|~)/\.dotfiles/([^\s\"']+)")


def _hook_commands(settings: dict[str, Any]) -> list[tuple[str, str]]:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        raise ValueError("settings.hooks must be an object")
    commands: list[tuple[str, str]] = []
    for event, groups in hooks.items():
        if not isinstance(event, str) or not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                continue
            for handler in handlers:
                if isinstance(handler, dict) and isinstance(handler.get("command"), str):
                    commands.append((event, handler["command"]))
    return commands


def extract_file_references(settings: dict[str, Any]) -> list[tuple[str, str]]:
    """Return event and tracked-relative path pairs from file-backed commands."""

    references: list[tuple[str, str]] = []
    for event, command in _hook_commands(settings):
        for match in FILE_REFERENCE.finditer(command):
            reference = match.group(1).rstrip(".,;)")
            if reference.startswith((".claude/hooks/", "tmux/scripts/")):
                references.append((event, reference))
    return references


def check_settings(settings: dict[str, Any], root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for event, reference in sorted(set(extract_file_references(settings))):
        path = root / reference
        if not path.is_file():
            issues.append(
                Issue(
                    event,
                    reference,
                    "missing-file",
                    "file-backed hook command does not resolve in the tracked distribution",
                )
            )
    return issues


def load_baseline(path: Path) -> list[Issue]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("hook-reference baseline must be an array")
    issues: list[Issue] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(field), str) for field in ("event", "reference", "rule", "message")
        ):
            raise ValueError(f"baseline entry {index} requires event, reference, rule, and message")
        issues.append(Issue(entry["event"], entry["reference"], entry["rule"], entry["message"]))
    return issues


def compare_baseline(actual: list[Issue], expected: list[Issue]) -> list[Issue]:
    actual_by_key = {(issue.event, issue.reference, issue.rule, issue.message): issue for issue in actual}
    expected_by_key = {(issue.event, issue.reference, issue.rule, issue.message): issue for issue in expected}
    differences: list[Issue] = []
    for key in sorted(expected_by_key.keys() - actual_by_key.keys()):
        issue = expected_by_key[key]
        differences.append(
            Issue(issue.event, issue.reference, "baseline-missing", f"expected baseline finding disappeared: {issue.rule}: {issue.message}")
        )
    for key in sorted(actual_by_key.keys() - expected_by_key.keys()):
        issue = actual_by_key[key]
        differences.append(Issue(issue.event, issue.reference, "baseline-new", f"new hook reference finding: {issue.rule}: {issue.message}"))
    return differences


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("settings", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        settings = json.loads(args.settings.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            raise ValueError("settings root must be an object")
        issues = check_settings(settings, args.root.resolve())
        if args.baseline:
            issues = compare_baseline(issues, load_baseline(args.baseline))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"hook reference check rejected input: {error}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2, sort_keys=True))
    else:
        for issue in issues:
            print(f"{issue.event}: {issue.reference}: {issue.rule}: {issue.message}")
        if not issues:
            print("hook reference check passed")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
