#!/usr/bin/env python3
"""Ratcheted lint over ai/skills/*/SKILL.md and ai/agents/*.md frontmatter."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.manifest_lint import check_manifest  # noqa: E402
from lib.skill_lint import Issue, lint_repo  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = Path(__file__).resolve().parent / "skill_lint_baseline.json"


def summarize_issues(issues: list[Issue]) -> dict:
    by_rule: dict[str, int] = {}
    for issue in issues:
        by_rule[issue.rule] = by_rule.get(issue.rule, 0) + 1
    return {"total": len(issues), "by_rule": by_rule}


def load_baseline(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("allowed_violations", []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--json", action="store_true")
    output_group.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    skills_glob = sorted((args.repo_root / "ai" / "skills").glob("*/SKILL.md"))
    agents_glob = sorted((args.repo_root / "ai" / "agents").glob("*.md"))

    all_issues = lint_repo(skills_glob, agents_glob, repo_root=args.repo_root)
    baseline = load_baseline(args.baseline)
    new_issues = [issue for issue in all_issues if issue.key() not in baseline]

    # Manifest coverage is not ratcheted: the router is generated from the manifest, so a
    # manifest that names a missing skill (or omits an enabled one) makes the router wrong.
    manifest_issues = [
        Issue(rule, "ai/skills/manifest.csv", message)
        for rule, message in check_manifest(args.repo_root)
    ]
    new_issues.extend(issue for issue in manifest_issues if issue.key() not in baseline)

    if args.json:
        print(json.dumps([issue.__dict__ for issue in new_issues], indent=2))
    elif args.summary:
        print(json.dumps(summarize_issues(new_issues), indent=2))
    else:
        for issue in new_issues:
            print(f"{issue.rule}: {issue.path}: {issue.message}")
        if not new_issues:
            print("skill lint: no new violations")

    return 1 if new_issues else 0


if __name__ == "__main__":
    sys.exit(main())
