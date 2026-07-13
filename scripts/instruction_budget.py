#!/usr/bin/env python3
"""Measure always-loaded guidance and enforce explicit size budgets."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Measurement:
    path: str
    lines: int
    words: int
    bytes: int


@dataclass(frozen=True)
class Violation:
    path: str
    metric: str
    actual: int
    limit: int


def measure_file(path: Path) -> Measurement:
    content = path.read_bytes()
    text = content.decode("utf-8")
    return Measurement(
        path=str(path),
        lines=len(text.splitlines()),
        words=len(text.split()),
        bytes=len(content),
    )


def check_budget(
    paths: list[Path],
    *,
    max_lines: int | None = None,
    max_words: int | None = None,
    max_bytes: int | None = None,
) -> list[Violation]:
    violations: list[Violation] = []
    for path in sorted(paths, key=lambda item: str(item)):
        measurement = measure_file(path)
        limits = (
            ("lines", measurement.lines, max_lines),
            ("words", measurement.words, max_words),
            ("bytes", measurement.bytes, max_bytes),
        )
        for metric, actual, limit in limits:
            if limit is not None and actual > limit:
                violations.append(Violation(str(path), metric, actual, limit))
    return violations


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-lines", type=int)
    parser.add_argument("--max-words", type=int)
    parser.add_argument("--max-bytes", type=int)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("paths", nargs="+", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        measurements = [measure_file(path) for path in sorted(args.paths, key=lambda item: str(item))]
        violations = check_budget(
            args.paths,
            max_lines=args.max_lines,
            max_words=args.max_words,
            max_bytes=args.max_bytes,
        )
    except (OSError, UnicodeError) as error:
        print(f"instruction budget rejected input: {error}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps({"measurements": [asdict(item) for item in measurements], "violations": [asdict(item) for item in violations]}, indent=2))
    else:
        for item in measurements:
            print(f"{item.path}: lines={item.lines} words={item.words} bytes={item.bytes}")
        for violation in violations:
            print(f"OVER BUDGET {violation.path}: {violation.metric}={violation.actual} > {violation.limit}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
