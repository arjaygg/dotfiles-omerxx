#!/usr/bin/env python3
"""Validate core autonomous skill contracts stay reachable and role-distinct."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


CORE_SKILLS = ("cap", "stark", "fury", "ironman", "hawk", "strange")

ROLE_NEEDLES = {
    "cap": ("orchestrator", "stark", "fury", "ironman", "hawk", "portable", "workflow"),
    "stark": ("plan", "architect", "not for: writing code", "writing tests"),
    "fury": ("test", "failing test", "tdd", "test-first"),
    "ironman": ("implement", "tests pass", "minimal", "tdd"),
    "hawk": ("review", "findings", "architecture", "security"),
    "strange": ("reproduce", "hypothesize", "verify", "fix"),
}

COMMON_NEEDLES = ("triggers:", "model:")


@dataclass(frozen=True)
class SkillContractResult:
    rule: str
    path: str
    status: str
    message: str = ""


def _ok(rule: str, path: str) -> SkillContractResult:
    return SkillContractResult(rule, path, "ok")


def _fail(rule: str, path: str, message: str) -> SkillContractResult:
    return SkillContractResult(rule, path, "fail", message)


def _skill_path(root: Path, skill: str) -> Path:
    return root / "ai" / "skills" / skill / "SKILL.md"


def _contains(text: str, needle: str) -> bool:
    return needle.lower() in text.lower()


def check_autonomous_skills(
    root: Path, required_skills: Sequence[str] = CORE_SKILLS
) -> list[SkillContractResult]:
    results: list[SkillContractResult] = []
    for skill in required_skills:
        path = _skill_path(root, skill)
        rel = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        if not path.is_file():
            results.append(_fail(f"{skill}-skill-file", rel, "missing core autonomous skill"))
            continue

        text = path.read_text(encoding="utf-8")
        results.append(_ok(f"{skill}-skill-file", rel))
        name_needle = f"name: {skill}"
        results.append(
            _ok(f"{skill}-name", rel)
            if _contains(text, name_needle)
            else _fail(f"{skill}-name", rel, f"missing {name_needle!r}")
        )
        results.append(
            _ok(f"{skill}-description", rel)
            if _contains(text, "description:") or _contains(text, "desc:")
            else _fail(f"{skill}-description", rel, "missing description/desc metadata")
        )
        for needle in COMMON_NEEDLES:
            rule = f"{skill}-{needle.rstrip(':').replace('-', '_')}"
            results.append(
                _ok(rule, rel)
                if _contains(text, needle)
                else _fail(rule, rel, f"missing {needle!r}")
            )
        for needle in ROLE_NEEDLES.get(skill, ()):
            rule = f"{skill}-orchestrates-{needle}" if skill == "cap" and needle in CORE_SKILLS else f"{skill}-role-{needle.replace(' ', '-')}"
            results.append(
                _ok(rule, rel)
                if _contains(text, needle)
                else _fail(rule, rel, f"missing role contract {needle!r}")
            )
    return results


def summarize_results(results: Sequence[SkillContractResult]) -> dict[str, object]:
    return {
        "total": len(results),
        "by_status": dict(sorted(Counter(result.status for result in results).items())),
        "by_skill": dict(sorted(Counter(result.path.split("/")[2] for result in results).items())),
        "by_rule": dict(sorted(Counter(result.rule for result in results).items())),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    results = check_autonomous_skills(args.root.resolve())
    if args.summary:
        print(json.dumps(summarize_results(results), indent=2))
    else:
        print(json.dumps([asdict(result) for result in results], indent=2))
    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
