#!/usr/bin/env python3
"""Detect common privacy and secret leaks in tracked dotfiles source."""

from __future__ import annotations

import argparse
import hashlib
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
        re.compile(r"(?<![A-Za-z0-9_])/(?:Users|home)/[A-Za-z0-9._-]+(?:/|$)"),
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
            r"\s*[:=]\s*(?:[\"']?)(?!\[REDACTED(?:[^\]]*)?\]|<[^>]+>|"
            r"YOUR_[A-Z0-9_]+|CHANGE_ME|REPLACE_ME)[A-Za-z0-9_./+=:-]{16,}",
            re.I,
        ),
    ),
    (
        "private-key",
        re.compile(r"-----BEGIN [A-Z0-9 ]+ PRIVATE KEY-----"),
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


def _finding_key(finding: Finding) -> tuple[str, int, str]:
    return finding.path, finding.line, finding.rule


def _fingerprint(keys: set[tuple[str, int, str]]) -> str:
    encoded = "\n".join(f"{path}\0{line}\0{rule}" for path, line, rule in sorted(keys))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load_baseline(path: Path) -> tuple[int, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid public-hygiene baseline: {error}") from error
    if not isinstance(payload, dict) or set(payload) != {"schema", "finding_count", "fingerprint"}:
        raise ValueError("public-hygiene baseline must contain schema, finding_count, and fingerprint")
    if payload["schema"] != 1 or not isinstance(payload["finding_count"], int) or payload["finding_count"] < 0:
        raise ValueError("public-hygiene baseline has invalid schema or finding_count")
    fingerprint = payload["fingerprint"]
    if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
        raise ValueError("public-hygiene baseline has invalid fingerprint")
    return payload["finding_count"], fingerprint


def compare_baseline(root: Path, baseline_path: Path) -> dict[str, object]:
    """Compare tracked findings with a reviewed no-regressions baseline."""

    actual = {_finding_key(finding) for finding in scan_repo(root)}
    expected_count, expected_fingerprint = _load_baseline(baseline_path)
    actual_fingerprint = _fingerprint(actual)
    return {
        "schema": 1,
        "finding_count": len(actual),
        "baseline_finding_count": expected_count,
        "fingerprint": actual_fingerprint,
        "baseline_fingerprint": expected_fingerprint,
        "baseline_match": len(actual) == expected_count and actual_fingerprint == expected_fingerprint,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--baseline", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    if args.baseline is not None:
        try:
            report = compare_baseline(root, args.baseline)
        except (OSError, UnicodeError, ValueError) as error:
            print(f"public hygiene baseline rejected: {error}", file=sys.stderr)
            return 2
        if args.as_json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(f"public hygiene findings: {report['finding_count']}")
            print(f"baseline match: {report['baseline_match']}")
        return 0 if report["baseline_match"] else 1
    findings = scan_repo(root)
    if args.as_json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    else:
        for finding in findings:
            print(f"{finding.path}:{finding.line}: {finding.rule}: {finding.excerpt}")
        if not findings:
            print("public hygiene check passed")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
