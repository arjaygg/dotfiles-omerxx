#!/usr/bin/env python3
"""Require manifest-declared tracked config bases to stay public-hygiene clean."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

try:
    from public_hygiene_check import Finding, scan_text, summarize_findings
except ModuleNotFoundError:  # pragma: no cover - package import path for unittest
    from scripts.public_hygiene_check import Finding, scan_text, summarize_findings


def base_hygiene_findings(root: Path, manifest_path: Path | None = None) -> list[Finding]:
    manifest = manifest_path or root / "ai/config/manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    findings: list[Finding] = []
    for client in data.get("clients", []):
        base = str(client["base"])
        path = root / base
        if not path.is_file():
            continue
        findings.extend(scan_text(base, path.read_text(encoding="utf-8", errors="replace")))
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path)
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", dest="as_json")
    output_group.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    try:
        findings = base_hygiene_findings(args.root.resolve(), args.manifest)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError) as error:
        print(f"invalid config base hygiene input: {error}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps([asdict(finding) for finding in findings], indent=2))
    elif args.summary:
        print(json.dumps(summarize_findings(findings), indent=2))
    else:
        for finding in findings:
            print(f"{finding.path}:{finding.line}: {finding.rule}: {finding.excerpt}")
        if not findings:
            print("config base hygiene check passed")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
