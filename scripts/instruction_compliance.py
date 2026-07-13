#!/usr/bin/env python3
"""Check always-loaded guidance for transient or machine-specific content."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class Issue:
    path: str
    rule: str
    line: int
    message: str


MEMORY_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+.*\b(?:Added Memories|Session Memories)\b", re.IGNORECASE)
CURRENT_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+Current \(\d{4}-\d{2}-\d{2}\)", re.IGNORECASE)
SESSION_MARKER = re.compile(
    r"\b(?:session restart required|done this session|not yet started|current branch:|uncommitted (?:files|changes))\b",
    re.IGNORECASE,
)
ABSOLUTE_USER_PATH = re.compile(r"(?<![A-Za-z0-9])/(?:Users|home)/[A-Za-z0-9._-]+(?:/|$)")


def scan_file(path: Path) -> list[Issue]:
    issues: list[Issue] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if MEMORY_HEADING.search(line):
            issues.append(
                Issue(
                    str(path),
                    "memory-section",
                    line_number,
                    "always-loaded guidance contains a session-memory section",
                )
            )
        if CURRENT_HEADING.search(line):
            issues.append(
                Issue(
                    str(path),
                    "dated-current-section",
                    line_number,
                    "always-loaded guidance contains dated session state",
                )
            )
        if SESSION_MARKER.search(line):
            issues.append(
                Issue(
                    str(path),
                    "session-state-marker",
                    line_number,
                    "always-loaded guidance contains transient session state",
                )
            )
        if ABSOLUTE_USER_PATH.search(line):
            issues.append(
                Issue(
                    str(path),
                    "absolute-user-path",
                    line_number,
                    "always-loaded guidance contains an absolute user path",
                )
            )
    return issues


def load_baseline(path: Path) -> list[Issue]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("instruction-compliance baseline must be an array")
    issues: list[Issue] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(field), (str, int)) for field in ("path", "rule", "line", "message")
        ):
            raise ValueError(f"baseline entry {index} requires path, rule, line, and message")
        if not isinstance(entry["line"], int) or entry["line"] < 1:
            raise ValueError(f"baseline entry {index} line must be a positive integer")
        issues.append(Issue(entry["path"], entry["rule"], entry["line"], entry["message"]))
    return issues


def compare_baseline(actual: list[Issue], expected: list[Issue]) -> list[Issue]:
    actual_by_key = {(issue.path, issue.rule, issue.line, issue.message): issue for issue in actual}
    expected_by_key = {(issue.path, issue.rule, issue.line, issue.message): issue for issue in expected}
    differences: list[Issue] = []
    for key in sorted(expected_by_key.keys() - actual_by_key.keys()):
        issue = expected_by_key[key]
        differences.append(
            Issue(issue.path, "baseline-missing", issue.line, f"expected baseline finding disappeared: {issue.rule}: {issue.message}")
        )
    for key in sorted(actual_by_key.keys() - expected_by_key.keys()):
        issue = actual_by_key[key]
        differences.append(Issue(issue.path, "baseline-new", issue.line, f"new compliance finding: {issue.rule}: {issue.message}"))
    return differences


def check_paths(paths: Sequence[Path]) -> list[Issue]:
    issues: list[Issue] = []
    for path in sorted(paths, key=lambda item: str(item)):
        issues.extend(scan_file(path))
    return issues


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        issues = check_paths(args.paths)
        if args.baseline:
            issues = compare_baseline(issues, load_baseline(args.baseline))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"instruction compliance rejected input: {error}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2, sort_keys=True))
    else:
        for issue in issues:
            print(f"{issue.path}:{issue.line}: {issue.rule}: {issue.message}")
        if not issues:
            print("instruction compliance check passed")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
