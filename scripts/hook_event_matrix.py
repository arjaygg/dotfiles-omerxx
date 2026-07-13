#!/usr/bin/env python3
"""Validate representative payload coverage for configured hook events."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class Issue:
    event: str
    rule: str
    message: str


def settings_events(settings: dict[str, Any]) -> set[str]:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict) or not all(isinstance(event, str) for event in hooks):
        raise ValueError("settings.hooks must be an object keyed by event name")
    return set(hooks)


def load_matrix(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("hook event matrix must be an array")
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, case in enumerate(value):
        if not isinstance(case, dict) or not isinstance(case.get("event"), str) or not case["event"]:
            raise ValueError(f"matrix entry {index} requires a non-empty event")
        event = case["event"]
        if event in seen:
            raise ValueError(f"duplicate matrix event: {event}")
        seen.add(event)
        if not isinstance(case.get("payload"), dict) or not case["payload"]:
            raise ValueError(f"{event}: payload must be a non-empty object")
        required = case.get("required", [])
        if not isinstance(required, list) or not all(isinstance(key, str) and key for key in required):
            raise ValueError(f"{event}: required must be an array of non-empty strings")
        missing = sorted(set(required) - set(case["payload"]))
        if missing:
            raise ValueError(f"{event}: payload is missing required keys: {', '.join(missing)}")
        cases.append(case)
    return cases


def check_matrix(settings: dict[str, Any], cases: list[dict[str, Any]]) -> list[Issue]:
    configured = settings_events(settings)
    covered = {case["event"] for case in cases}
    issues: list[Issue] = []
    for event in sorted(configured - covered):
        issues.append(Issue(event, "missing-event", "configured hook event has no representative payload"))
    for event in sorted(covered - configured):
        issues.append(Issue(event, "stale-event", "matrix event is not configured in settings"))
    return issues


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("settings", type=Path)
    parser.add_argument("matrix", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        settings = json.loads(args.settings.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            raise ValueError("settings root must be an object")
        cases = load_matrix(args.matrix)
        issues = check_matrix(settings, cases)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"hook event matrix rejected input: {error}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2, sort_keys=True))
    else:
        for issue in issues:
            print(f"{issue.event}: {issue.rule}: {issue.message}")
        if not issues:
            print("hook event matrix check passed")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
