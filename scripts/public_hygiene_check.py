#!/usr/bin/env python3
"""Detect common privacy and secret leaks in tracked dotfiles source."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    excerpt: str


_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "absolute-home-path",
        re.compile(
            r"(?<![A-Za-z0-9_])(?:"
            r"/(?:Users|home)/[A-Za-z0-9._-]+(?:/|$)"
            r"|[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z0-9._ -]+(?:[\\/]|$)"
            r"|\\{2,}[A-Za-z0-9._ -]+\\+[A-Za-z0-9$._ -]+(?:\\|$)"
            r")",
            re.I,
        ),
    ),
    (
        "private-org-url",
        re.compile(r"(?:https?://)?(?:dev\.azure\.com/bofaz|bofaz\.visualstudio\.com)", re.I),
    ),
    (
        "private-org-name",
        re.compile(
            r"\b(?:A" + r"xos(?: Financial| Bank)?|A" + r"xos-(?:Universal-Core|Core-Services)|"
            r"A" + r"xos Clearing)\b",
            re.I,
        ),
    ),
    (
        "secret-assignment",
        re.compile(
            r"\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret|token)\b"
            r"[\"']?\s*[:=]\s*(?:[\"']?)(?!\[REDACTED(?:[^\]]*)?\]|<[^>]+>|"
            r"YOUR_[A-Z0-9_]+|CHANGE_ME|REPLACE_ME)[A-Za-z0-9_./+=:-]{16,}",
            re.I,
        ),
    ),
    (
        "private-key",
        re.compile(
            r"-----BEGIN (?:(?:[A-Z0-9]+(?: [A-Z0-9]+)* )?PRIVATE KEY"
            r"|PGP PRIVATE KEY BLOCK)-----"
        ),
    ),
)


def scan_text(path: str, text: str) -> list[Finding]:
    """Return one finding per matching rule and line."""

    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        excerpt = line.strip()[:240]
        for rule, pattern in _RULES:
            if pattern.search(line):
                findings.append(Finding(path, line_number, rule, excerpt))
    return findings


def _tracked_paths(root: Path) -> Iterable[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    for raw_path in result.stdout.split(b"\0"):
        if raw_path:
            yield root / raw_path.decode("utf-8")


def scan_repo(root: Path) -> list[Finding]:
    """Scan UTF-8 tracked files under a git worktree."""

    findings: list[Finding] = []
    for path in _tracked_paths(root):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        findings.extend(scan_text(path.relative_to(root).as_posix(), text))
    return findings


def summarize_findings(findings: Sequence[Finding]) -> dict[str, object]:
    """Return counts only, without excerpts or matched private values."""

    by_rule: dict[str, int] = {}
    by_path: dict[str, int] = {}
    for finding in findings:
        by_rule[finding.rule] = by_rule.get(finding.rule, 0) + 1
        by_path[finding.path] = by_path.get(finding.path, 0) + 1
    return {
        "total": len(findings),
        "by_rule": dict(sorted(by_rule.items())),
        "by_path": dict(sorted(by_path.items())),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--summary", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    findings = scan_repo(root)
    if args.summary:
        print(json.dumps(summarize_findings(findings), indent=2))
    elif args.as_json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    else:
        for finding in findings:
            print(f"{finding.path}:{finding.line}: {finding.rule}: {finding.excerpt}")
        if not findings:
            print("public hygiene check passed")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
