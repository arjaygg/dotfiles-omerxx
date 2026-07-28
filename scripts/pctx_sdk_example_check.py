#!/usr/bin/env python3
"""Reject stale pctx SDK examples in active agent guidance."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


STALE_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "serena-search-for-pattern-call",
        re.compile(r"\bSerena\.searchForPattern\s*\("),
        "Use LeanCtx.ctxSearch({ pattern, path, include?, exclude? }) instead.",
    ),
    (
        "serena-find-file-call",
        re.compile(r"\bSerena\.findFile\s*\("),
        "Use LeanCtx.ctxGlob({ pattern, path }) or Glob instead.",
    ),
    (
        "serena-list-dir-call",
        re.compile(r"\bSerena\.listDir\s*\("),
        "Use LeanCtx.ctxTree({ path }) or Glob instead.",
    ),
    (
        "serena-read-memory-name-field",
        re.compile(r"\bSerena\.readMemory\s*\(\s*\{\s*name\s*:"),
        'Use Serena.readMemory({ memory_name: "START_HERE" }) instead.',
    ),
    (
        "read-memory-name-field",
        re.compile(r"\breadMemory\s*\(\s*\{\s*name\s*:"),
        'Use readMemory({ memory_name: "START_HERE" }) instead.',
    ),
    (
        "serena-read-memory-file-name-field",
        re.compile(r"\bmemory_file_name\b"),
        'Use memory_name for Serena.readMemory input.',
    ),
    (
        "leanctx-ctxsearch-query-field",
        re.compile(r"\bLeanCtx\.ctxSearch\s*\(\s*\{\s*query\s*:"),
        "Use LeanCtx.ctxSearch({ pattern, path }) instead.",
    ),
)


@dataclass(frozen=True)
class StaleSdkExample:
    path: str
    line: int
    kind: str
    text: str
    replacement: str


def candidate_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for name in ("AGENTS.md", "CLAUDE.md", "README.md"):
        path = root / name
        if path.is_file():
            files.append(path)
    for directory in ("ai/rules", "ai/commands"):
        base = root / directory
        if base.is_dir():
            files.extend(sorted(path for path in base.rglob("*.md") if path.is_file()))
    skills_dir = root / "ai/skills"
    if skills_dir.is_dir():
        files.extend(sorted(skills_dir.glob("*/SKILL.md")))
    hooks_dir = root / ".claude/hooks"
    if hooks_dir.is_dir():
        files.extend(sorted(path for path in hooks_dir.glob("*.sh") if path.is_file()))
    memories_dir = root / ".serena/memories"
    if memories_dir.is_dir():
        files.extend(sorted(path for path in memories_dir.rglob("*.md") if "_archive" not in path.parts))
    for name in ("plans/active-context.md", "plans/progress.md", "plans/decisions.md", "plans/pctx-functions.md"):
        path = root / name
        if path.is_file():
            files.append(path)
    return sorted(set(files))


def check_sdk_examples(root: Path, files: Iterable[Path] | None = None) -> list[StaleSdkExample]:
    issues: list[StaleSdkExample] = []
    for path in files or candidate_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            for kind, pattern, replacement in STALE_PATTERNS:
                if pattern.search(line):
                    issues.append(
                        StaleSdkExample(
                            path=relative,
                            line=line_number,
                            kind=kind,
                            text=line.strip(),
                            replacement=replacement,
                        )
                    )
    return issues


def summarize_issues(issues: Sequence[StaleSdkExample]) -> dict[str, object]:
    return {
        "total": len(issues),
        "by_kind": dict(sorted(Counter(issue.kind for issue in issues).items())),
        "by_path": dict(sorted(Counter(issue.path for issue in issues).items())),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    issues = check_sdk_examples(args.root.resolve())
    if args.summary:
        print(json.dumps(summarize_issues(issues), indent=2))
    else:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
