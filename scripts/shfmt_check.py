#!/usr/bin/env python3
"""Check governed shell formatting with a reviewed shfmt baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

DEFAULT_PATHS = (
    Path(".claude/hooks"),
    Path(".codex/hooks"),
    Path(".cursor/hooks"),
    Path(".gemini/extension/scripts"),
    Path(".gemini/hooks"),
    Path("scripts"),
)


def _shell_files(paths: Sequence[Path]) -> list[str]:
    files: set[str] = set()
    for path in paths:
        if path.is_file() and path.suffix in {".sh", ".bash"}:
            files.add(path.as_posix())
        elif path.is_dir():
            files.update(
                candidate.as_posix()
                for candidate in path.rglob("*")
                if candidate.is_file() and candidate.suffix in {".sh", ".bash"}
            )
    return sorted(files)


def _fingerprint(paths: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(sorted(paths)).encode("utf-8")).hexdigest()


def check(paths: Sequence[Path], *, command: str = "shfmt") -> dict[str, object]:
    executable = shutil.which(command)
    if executable is None:
        raise RuntimeError(f"required formatter not found: {command}")
    files = _shell_files(paths)
    result = subprocess.run(
        [executable, "-l", *files],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in {0, 1}:
        message = (result.stderr or result.stdout).strip() or f"{command} exited {result.returncode}"
        raise RuntimeError(message)
    unformatted = sorted(line for line in result.stdout.splitlines() if line.strip())
    return {
        "schema": 1,
        "shell_file_count": len(files),
        "unformatted_count": len(unformatted),
        "fingerprint": _fingerprint(unformatted),
        "unformatted": unformatted,
    }


def _load_baseline(path: Path) -> tuple[int, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid shfmt baseline: {error}") from error
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "shell_file_count", "unformatted_count", "fingerprint"}
        or value.get("schema") != 1
        or not isinstance(value.get("shell_file_count"), int)
        or not isinstance(value.get("unformatted_count"), int)
        or not isinstance(value.get("fingerprint"), str)
        or len(value["fingerprint"]) != 64
        or any(char not in "0123456789abcdef" for char in value["fingerprint"])
    ):
        raise ValueError("shfmt baseline has invalid fields")
    return value["unformatted_count"], value["fingerprint"]


def compare(paths: Sequence[Path], baseline: Path, *, command: str = "shfmt") -> dict[str, object]:
    report = check(paths, command=command)
    expected_count, expected_fingerprint = _load_baseline(baseline)
    report.update(
        {
            "baseline_unformatted_count": expected_count,
            "baseline_fingerprint": expected_fingerprint,
            "baseline_match": report["unformatted_count"] == expected_count
            and report["fingerprint"] == expected_fingerprint,
        }
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=list(DEFAULT_PATHS))
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--command", default="shfmt")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        report = compare(args.paths, args.baseline, command=args.command) if args.baseline else check(args.paths, command=args.command)
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        print(f"shfmt check rejected input: {error}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"shfmt unformatted files: {report['unformatted_count']}")
        for path in report["unformatted"]:
            print(path)
        if args.baseline:
            print(f"shfmt baseline match: {report['baseline_match']}")
    if args.baseline:
        return 0 if report["baseline_match"] else 1
    return 0 if not report["unformatted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
