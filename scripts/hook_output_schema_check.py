#!/usr/bin/env python3
"""Find hook scripts that appear to emit incomplete hookSpecificOutput JSON."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class HookOutputIssue:
    path: str
    line: int
    rule: str
    message: str


SKIP_DIRS = {"archive", "fixtures", "__pycache__"}
HOOK_FILE_SUFFIXES = {".sh", ".py", ".js", ".rs"}


def iter_hook_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in HOOK_FILE_SUFFIXES:
            files.append(path)
    return files


def check_hook_outputs(root: Path) -> list[HookOutputIssue]:
    base = root if root.is_dir() else root.parent
    issues: list[HookOutputIssue] = []
    for path in iter_hook_files(root):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            if _is_comment_only(line) or _is_parse_only(line) or "hookSpecificOutput" not in line:
                continue
            window = "\n".join(_strip_comment_only(item) for item in lines[index : index + 12])
            rel = path.relative_to(base).as_posix() if path.is_relative_to(base) else path.as_posix()
            if "permissionDecision" in window and "hookEventName" not in window:
                issues.append(
                    HookOutputIssue(
                        rel,
                        index + 1,
                        "permission-decision-missing-hook-event-name",
                        "permissionDecision output should include hookEventName",
                    )
                )
            if "additionalContext" in window and "hookEventName" not in window:
                issues.append(
                    HookOutputIssue(
                        rel,
                        index + 1,
                        "additional-context-missing-hook-event-name",
                        "additionalContext output should include hookEventName",
                    )
                )
            if "updatedInput" in window and not _window_allows_rewrite(window):
                issues.append(
                    HookOutputIssue(
                        rel,
                        index + 1,
                        "updated-input-not-explicitly-allowed",
                        "updatedInput output should be paired with permissionDecision=allow",
                    )
                )
    return issues


def _is_comment_only(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*")


def _strip_comment_only(line: str) -> str:
    return "" if _is_comment_only(line) else line


def _is_parse_only(line: str) -> bool:
    return ".get('hookSpecificOutput'" in line or '.get("hookSpecificOutput"' in line


def _window_allows_rewrite(window: str) -> bool:
    compact = "".join(window.split()).lower()
    return "permissiondecision\":\"allow\"" in compact or "permissiondecision:\"allow\"" in compact


def summarize_issues(issues: Sequence[HookOutputIssue]) -> dict[str, object]:
    return {
        "total": len(issues),
        "by_rule": dict(sorted(Counter(issue.rule for issue in issues).items())),
        "by_path": dict(sorted(Counter(issue.path for issue in issues).items())),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=Path(".claude/hooks"))
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", dest="as_json")
    output_group.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    issues = check_hook_outputs(args.path.resolve())
    if args.as_json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif args.summary:
        print(json.dumps(summarize_issues(issues), indent=2))
    else:
        for issue in issues:
            print(f"{issue.path}:{issue.line}: {issue.rule}: {issue.message}")
        if not issues:
            print("hook output schema check passed")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
