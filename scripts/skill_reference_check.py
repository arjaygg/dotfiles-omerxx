#!/usr/bin/env python3
"""Find references to missing shared skills or slash commands."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


SKILL_PATH_RE = re.compile(r"(?:~/.dotfiles/|\.?/)?ai/skills/([A-Za-z0-9_.-]+)(?:/|\b)")
SLASH_REF_RE = re.compile(r"`/([A-Za-z][A-Za-z0-9_.-]+)`")
BUILTIN_SLASH_REFERENCES = frozenset(
    {
        "compact",
        "context",
        "dev",
        "effort",
        "fast",
        "loop",
        "model",
        "plan",
        "schedule",
        "tasks",
        "tmp",
        "workflows",
    }
)


@dataclass(frozen=True)
class ReferenceIssue:
    path: str
    line: int
    scope: str
    kind: str
    name: str


def discover_skills(root: Path) -> set[str]:
    skills_dir = root / "ai/skills"
    if not skills_dir.is_dir():
        return set()
    return {
        child.name
        for child in skills_dir.iterdir()
        if child.is_dir() and ((child / "SKILL.md").is_file() or (child / "skill.md").is_file())
    }


def discover_commands(root: Path) -> set[str]:
    commands_dir = root / "ai/commands"
    if not commands_dir.is_dir():
        return set()
    return {path.stem for path in commands_dir.glob("*.md")}


def candidate_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = root / name
        if path.is_file():
            files.append(path)
    for directory in ("ai/rules", "ai/commands", "decisions", "docs", "plans"):
        base = root / directory
        if base.is_dir():
            files.extend(sorted(path for path in base.rglob("*.md") if path.is_file()))
    skills_dir = root / "ai/skills"
    if skills_dir.is_dir():
        for child in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
            skill_md = child / "SKILL.md"
            fallback = child / "skill.md"
            if skill_md.is_file():
                files.append(skill_md)
            elif fallback.is_file():
                files.append(fallback)
    return sorted(set(files))


def source_scope(relative_path: str) -> str:
    if relative_path in {"AGENTS.md", "CLAUDE.md"}:
        return "entrypoint-guidance"
    if relative_path.startswith(("ai/rules/", "ai/commands/", "ai/skills/")):
        return "ai-primitives"
    if relative_path.startswith(("docs/", "decisions/")):
        return "durable-docs"
    if relative_path in {
        "plans/active-context.md",
        "plans/progress.md",
        "plans/decisions.md",
        "plans/2026-07-14-agentic-loop-optimization.md",
    }:
        return "active-plans"
    if relative_path.startswith("plans/"):
        return "historical-plans"
    return "other"


def check_references(
    root: Path,
    files: Iterable[Path] | None = None,
) -> list[ReferenceIssue]:
    skills = discover_skills(root)
    commands = discover_commands(root)
    issues: list[ReferenceIssue] = []
    for path in files or candidate_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(root).as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in SKILL_PATH_RE.finditer(line):
                name = match.group(1)
                if name not in skills:
                    issues.append(
                        ReferenceIssue(relative, line_number, source_scope(relative), "skill-path", name)
                    )
            for match in SLASH_REF_RE.finditer(line):
                name = match.group(1)
                if name not in BUILTIN_SLASH_REFERENCES and name not in skills and name not in commands:
                    issues.append(
                        ReferenceIssue(relative, line_number, source_scope(relative), "slash-ref", name)
                    )
    return issues


def summarize_issues(issues: Sequence[ReferenceIssue]) -> dict[str, object]:
    return {
        "total": len(issues),
        "by_scope": dict(sorted(Counter(issue.scope for issue in issues).items())),
        "by_kind": dict(sorted(Counter(issue.kind for issue in issues).items())),
        "by_name": dict(sorted(Counter(issue.name for issue in issues).items())),
        "by_path": dict(sorted(Counter(issue.path for issue in issues).items())),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    issues = check_references(args.root.resolve())
    if args.summary:
        print(json.dumps(summarize_issues(issues), indent=2))
    else:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
