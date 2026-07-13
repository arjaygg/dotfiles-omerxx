#!/usr/bin/env python3
"""Run ShellCheck on governed scripts and compare a reviewed error baseline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

try:
    from scripts.shell_syntax_check import DEFAULT_PATHS, _shell_files
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.shell_syntax_check import DEFAULT_PATHS, _shell_files


@dataclass(frozen=True)
class Issue:
    path: str
    line: int
    end_line: int
    column: int
    end_column: int
    level: str
    code: int
    message: str


def parse_findings(output: str) -> list[Issue]:
    value = json.loads(output or "[]")
    if not isinstance(value, list):
        raise ValueError("ShellCheck JSON output must be an array")
    findings: list[Issue] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("ShellCheck finding must be an object")
        try:
            findings.append(
                Issue(
                    path=str(item["file"]),
                    line=int(item["line"]),
                    end_line=int(item.get("endLine", item["line"])),
                    column=int(item["column"]),
                    end_column=int(item.get("endColumn", item["column"])),
                    level=str(item["level"]),
                    code=int(item["code"]),
                    message=str(item["message"]),
                )
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("ShellCheck finding has invalid fields") from error
    return findings


def run_shellcheck(
    paths: Sequence[Path],
    *,
    executable: Sequence[str] | None = None,
    severity: str = "error",
) -> tuple[bool, list[Issue]]:
    command = list(executable or ("shellcheck",))
    findings: list[Issue] = []
    for path in sorted(paths, key=lambda item: str(item)):
        try:
            result = subprocess.run(
                [*command, "--severity", severity, "--format=json", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            return False, []
        if result.returncode not in (0, 1):
            detail = (result.stderr or result.stdout).strip() or f"exit {result.returncode}"
            raise RuntimeError(f"ShellCheck failed for {path}: {detail}")
        findings.extend(parse_findings(result.stdout))
    return True, sorted(findings, key=lambda item: (item.path, item.line, item.column, item.code, item.message))


def _dicts(findings: Sequence[Issue]) -> list[dict[str, object]]:
    return [asdict(item) for item in sorted(set(findings), key=lambda item: (item.path, item.line, item.column, item.code, item.message))]


def compare_baseline(current: Sequence[Issue], baseline: Sequence[Issue]) -> dict[str, object]:
    current_set = set(current)
    baseline_set = set(baseline)
    return {
        "match": current_set == baseline_set,
        "added": _dicts(list(current_set - baseline_set)),
        "removed": _dicts(list(baseline_set - current_set)),
    }


def _load_baseline(path: Path) -> list[Issue]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        raise ValueError("ShellCheck baseline schema must be 1")
    values = payload.get("findings")
    if not isinstance(values, list):
        raise ValueError("ShellCheck baseline findings must be an array")
    try:
        return [Issue(**value) for value in values]
    except (TypeError, ValueError) as error:
        raise ValueError("ShellCheck baseline finding has invalid fields") from error


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=list(DEFAULT_PATHS))
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--severity", choices=("error", "warning", "info", "style"), default="error")
    parser.add_argument("--require", action="store_true", help="fail if ShellCheck is unavailable")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        available, findings = run_shellcheck(_shell_files(args.paths), severity=args.severity)
        comparison = None
        if args.baseline is not None and available:
            comparison = compare_baseline(findings, _load_baseline(args.baseline))
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        print(f"ShellCheck validation rejected input: {error}", file=sys.stderr)
        return 2
    if not available:
        if args.require:
            print("ShellCheck is unavailable", file=sys.stderr)
            return 2
        payload: dict[str, object] = {"schema": 1, "available": False, "findings": []}
        print(json.dumps(payload, indent=2))
        return 0
    payload = {"schema": 1, "available": True, "findings": _dicts(findings)}
    if comparison is not None:
        payload.update(comparison)
    if args.as_json or comparison is not None:
        print(json.dumps(payload, indent=2))
    else:
        for finding in findings:
            print(f"{finding.path}:{finding.line}:{finding.column}: {finding.level} SC{finding.code} {finding.message}")
    if comparison is not None:
        return 0 if comparison["match"] else 1
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
