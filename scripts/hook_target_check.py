#!/usr/bin/env python3
"""Validate hook command targets referenced from Claude settings."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class HookTargetIssue:
    event: str
    path: str
    rule: str
    message: str


DOTFILES_REF = re.compile(r"(?:\$HOME/\.dotfiles|~/\.dotfiles)/([^\"'\s]+)")


def iter_command_hooks(settings: dict[str, object]) -> list[tuple[str, str]]:
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return []
    commands: list[tuple[str, str]] = []
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks", [])
            if not isinstance(handlers, list):
                continue
            for handler in handlers:
                if (
                    isinstance(handler, dict)
                    and handler.get("type") == "command"
                    and isinstance(handler.get("command"), str)
                ):
                    commands.append((str(event), handler["command"]))
    return commands


def check_hook_targets(settings_path: Path, repo_root: Path) -> list[HookTargetIssue]:
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    issues: list[HookTargetIssue] = []
    seen: set[tuple[str, str, str]] = set()
    for event, command in iter_command_hooks(settings):
        direct_target = _direct_dotfiles_target(command, repo_root)
        for relative in sorted(set(DOTFILES_REF.findall(command))):
            path = repo_root / relative
            issue_key_base = (event, relative)
            if not path.exists():
                key = (*issue_key_base, "missing-target")
                if key not in seen:
                    seen.add(key)
                    issues.append(
                        HookTargetIssue(event, relative, "missing-target", "hook command target is missing")
                    )
                continue
            if path.is_dir():
                key = (*issue_key_base, "target-is-directory")
                if key not in seen:
                    seen.add(key)
                    issues.append(
                        HookTargetIssue(event, relative, "target-is-directory", "hook command target is a directory")
                    )
                continue
            if direct_target == path and not _is_executable(path):
                key = (*issue_key_base, "direct-target-not-executable")
                if key not in seen:
                    seen.add(key)
                    issues.append(
                        HookTargetIssue(
                            event,
                            relative,
                            "direct-target-not-executable",
                            "directly executed hook command target is not executable",
                        )
                    )
    return issues


def _direct_dotfiles_target(command: str, repo_root: Path) -> Path | None:
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if not parts:
        return None
    first = parts[0]
    match = DOTFILES_REF.fullmatch(first)
    if match is None:
        return None
    return repo_root / match.group(1)


def _is_executable(path: Path) -> bool:
    return bool(path.stat().st_mode & 0o111)


def summarize_issues(issues: Sequence[HookTargetIssue]) -> dict[str, object]:
    return {
        "total": len(issues),
        "by_rule": dict(sorted(Counter(issue.rule for issue in issues).items())),
        "by_event": dict(sorted(Counter(issue.event for issue in issues).items())),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("settings", nargs="?", type=Path, default=Path(".claude/settings.json"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", dest="as_json")
    output_group.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    try:
        issues = check_hook_targets(args.settings.resolve(), args.repo_root.resolve())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"invalid hook target input: {error}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif args.summary:
        print(json.dumps(summarize_issues(issues), indent=2))
    else:
        for issue in issues:
            print(f"{issue.event}: {issue.path}: {issue.rule}: {issue.message}")
        if not issues:
            print("hook target check passed")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
