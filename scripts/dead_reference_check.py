#!/usr/bin/env python3
"""Detect dead distribution links and explicit local script references."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


SCRIPT_REFERENCE = re.compile(
    r"(?<![:/A-Za-z0-9_])(?:\./)?(scripts/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)"
)


@dataclass(frozen=True)
class Finding:
    kind: str
    source: str
    reference: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _label(root: Path, path: Path) -> str:
    try:
        candidate = path if path.is_absolute() else root / path
        return candidate.relative_to(root).as_posix()
    except ValueError:
        return "<outside-root>"


def _broken_symlinks(root: Path, directory: str) -> list[Finding]:
    base = root / directory
    if not base.is_dir():
        return []
    findings: list[Finding] = []
    for path in sorted(base.iterdir(), key=lambda item: item.name):
        if not path.is_symlink() or path.exists():
            continue
        target = path.readlink()
        reference = "<absolute-target>" if target.is_absolute() else target.as_posix()
        findings.append(
            Finding(
                "broken-symlink",
                _label(root, path),
                reference,
                "symlink target does not exist",
            )
        )
    return findings


def _script_references(root: Path) -> list[Finding]:
    directory = root / "ai/commands"
    if not directory.is_dir():
        return []
    findings: list[Finding] = []
    for source in sorted(directory.rglob("*.md"), key=lambda item: item.as_posix()):
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        references = sorted({match.group(1) for match in SCRIPT_REFERENCE.finditer(text)})
        for reference in references:
            if (root / reference).is_file():
                continue
            findings.append(
                Finding(
                    "missing-script-reference",
                    _label(root, source),
                    reference,
                    "referenced repository script does not exist",
                )
            )
    return findings


def scan_root(root: Path) -> list[Finding]:
    """Return sorted findings without changing links or source files."""

    root = root.resolve()
    findings = _broken_symlinks(root, ".claude/commands")
    findings.extend(_broken_symlinks(root, ".claude/skills"))
    findings.extend(_script_references(root))
    return sorted(set(findings), key=lambda item: (item.kind, item.source, item.reference, item.message))


def _finding_key(finding: Finding) -> tuple[str, str, str, str]:
    return (finding.kind, finding.source, finding.reference, finding.message)


def _dicts(findings: Iterable[Finding]) -> list[dict[str, str]]:
    return [finding.as_dict() for finding in sorted(set(findings), key=_finding_key)]


def compare_baseline(current: Iterable[Finding], baseline: Iterable[Finding]) -> dict[str, object]:
    current_set = set(current)
    baseline_set = set(baseline)
    added = current_set - baseline_set
    removed = baseline_set - current_set
    return {
        "match": not added and not removed,
        "added": _dicts(added),
        "removed": _dicts(removed),
    }


def _load_baseline(path: Path) -> list[Finding]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        raise ValueError("dead-reference baseline schema must be 1")
    values = payload.get("findings")
    if not isinstance(values, list):
        raise ValueError("dead-reference baseline findings must be an array")
    findings: list[Finding] = []
    for value in values:
        if not isinstance(value, dict) or set(value) != {"kind", "source", "reference", "message"}:
            raise ValueError("dead-reference baseline finding has invalid fields")
        if not all(isinstance(value[key], str) for key in value):
            raise ValueError("dead-reference baseline finding fields must be strings")
        findings.append(Finding(**value))
    return findings


def _payload(findings: list[Finding], comparison: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {"schema": 1, "findings": _dicts(findings)}
    if comparison is not None:
        payload.update(comparison)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        findings = scan_root(args.root)
        comparison = None
        if args.baseline is not None:
            comparison = compare_baseline(findings, _load_baseline(args.baseline))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(f"dead-reference check rejected input: {error}", file=sys.stderr)
        return 2

    payload = _payload(findings, comparison)
    if args.as_json or args.baseline is not None:
        print(json.dumps(payload, indent=2))
    else:
        for finding in findings:
            print(f"{finding.kind}: {finding.source}: {finding.reference}: {finding.message}")
    if comparison is not None:
        return 0 if comparison["match"] else 1
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
