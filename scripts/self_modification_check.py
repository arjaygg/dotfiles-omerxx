#!/usr/bin/env python3
"""Report tracked policy/state files that hook scripts may mutate automatically."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class SelfModificationIssue:
    path: str
    line: int
    target: str
    rule: str
    message: str


TRACKED_POLICY_TARGETS = (
    "hook-config.yaml",
    "hook-graduation-state.json",
    ".claude/settings.json",
    "AGENTS.md",
    "CLAUDE.md",
)


def check_self_modification(root: Path) -> list[SelfModificationIssue]:
    issues: list[SelfModificationIssue] = []
    for path in _candidate_scripts(root):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        variable_targets = _variable_targets(lines)
        for index, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for target in TRACKED_POLICY_TARGETS:
                references_target = target in stripped or any(
                    _references_variable(stripped, variable)
                    for variable, variable_target in variable_targets.items()
                    if variable_target == target
                )
                if references_target and _looks_like_mutation(stripped):
                    issues.append(
                        SelfModificationIssue(
                            path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix(),
                            index,
                            target,
                            "tracked-policy-mutation",
                            "script appears to mutate tracked policy/state",
                        )
                    )
    return issues


def _candidate_scripts(root: Path) -> list[Path]:
    hooks = root / ".claude/hooks"
    if not hooks.is_dir():
        return []
    return [
        path
        for path in sorted(hooks.rglob("*"))
        if path.is_file() and path.suffix in {".sh", ".py", ".js", ".rs"} and "archive" not in path.parts
    ]


def _variable_targets(lines: Sequence[str]) -> dict[str, str]:
    targets: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        name = name.strip()
        if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", name):
            continue
        for target in TRACKED_POLICY_TARGETS:
            if target in value:
                targets[name] = target
    return targets


def _references_variable(line: str, variable: str) -> bool:
    return f"${variable}" in line or f"${{{variable}}}" in line


def _looks_like_mutation(line: str) -> bool:
    # Ignore explicit dry-run/proposal-only text or read-only tests.
    lowered = line.lower()
    if "dry-run" in lowered and "dry_run" not in lowered:
        return False
    return bool(
        re.search(r"(^|[;&|])\s*sed\s+-i\b", line)
        or re.search(r"(^|[;&|])\s*(mv|cp)\b", line)
        or re.search(r"(^|[;&|])\s*tee\b", line)
        or (_has_file_redirect(line) and re.search(r"(^|[;&|])\s*(jq|python|cat|printf|echo)\b", line))
    )


def _has_file_redirect(line: str) -> bool:
    return bool(re.search(r"(^|[^0-9])>{1,2}\s*[^&]", line))


def summarize_issues(issues: Sequence[SelfModificationIssue]) -> dict[str, object]:
    return {
        "total": len(issues),
        "by_target": dict(sorted(Counter(issue.target for issue in issues).items())),
        "by_path": dict(sorted(Counter(issue.path for issue in issues).items())),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true", dest="as_json")
    output_group.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    try:
        issues = check_self_modification(args.root.resolve())
    except OSError as error:
        print(f"invalid self-modification input: {error}", file=sys.stderr)
        return 2
    if args.as_json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    elif args.summary:
        print(json.dumps(summarize_issues(issues), indent=2))
    else:
        for issue in issues:
            print(f"{issue.path}:{issue.line}: {issue.target}: {issue.rule}: {issue.message}")
        if not issues:
            print("self-modification check passed")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
