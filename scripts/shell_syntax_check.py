#!/usr/bin/env python3
"""Run bash syntax checks over tracked shell scripts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class ShellSyntaxResult:
    path: str
    status: str
    message: str = ""


def candidate_files(root: Path) -> list[Path]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "*.sh"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return sorted(root.rglob("*.sh"))
    return [root / line for line in output.splitlines() if line]


def check_shell_syntax(root: Path, files: Sequence[Path] | None = None) -> list[ShellSyntaxResult]:
    results: list[ShellSyntaxResult] = []
    for path in files or candidate_files(root):
        relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        result = subprocess.run(
            ["bash", "-n", str(path)],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        results.append(
            ShellSyntaxResult(
                path=relative,
                status="ok" if result.returncode == 0 else "invalid",
                message=result.stderr.strip(),
            )
        )
    return results


def summarize_results(results: Sequence[ShellSyntaxResult]) -> dict[str, object]:
    return {
        "total": len(results),
        "by_status": dict(sorted(Counter(result.status for result in results).items())),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    results = check_shell_syntax(args.root.resolve())
    if args.summary:
        print(json.dumps(summarize_results(results), indent=2))
    else:
        print(json.dumps([asdict(result) for result in results], indent=2))
    return 1 if any(result.status != "ok" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
