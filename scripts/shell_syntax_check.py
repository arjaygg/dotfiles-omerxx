#!/usr/bin/env python3
"""Validate Bash syntax for tracked shell hooks and support scripts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_PATHS = (
    Path(".claude/hooks"),
    Path(".codex/hooks"),
    Path(".cursor/hooks"),
    Path(".gemini/extension/scripts"),
    Path(".gemini/hooks"),
    Path("scripts"),
)
SHELL_SUFFIXES = frozenset({".bash", ".sh"})


@dataclass(frozen=True)
class Issue:
    path: str
    message: str


def _shell_files(paths: Iterable[Path]) -> list[Path]:
    files: set[Path] = set()
    for path in paths:
        if path.is_file():
            if path.suffix in SHELL_SUFFIXES:
                files.add(path)
            continue
        if path.is_dir():
            files.update(candidate for candidate in path.rglob("*") if candidate.is_file() and candidate.suffix in SHELL_SUFFIXES)
    return sorted(files, key=lambda candidate: str(candidate))


def check_paths(paths: Sequence[Path]) -> list[Issue]:
    issues: list[Issue] = []
    for path in _shell_files(paths):
        try:
            result = subprocess.run(
                ["bash", "-n", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            issues.append(Issue(str(path), str(error)))
            continue
        if result.returncode != 0:
            message = (result.stderr or result.stdout).strip() or f"bash -n exited {result.returncode}"
            issues.append(Issue(str(path), message))
    return issues


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=list(DEFAULT_PATHS))
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    issues = check_paths(args.paths)
    if args.as_json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    else:
        for issue in issues:
            print(f"{issue.path}: {issue.message}")
        if not issues:
            print("shell syntax check passed")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
