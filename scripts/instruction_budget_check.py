#!/usr/bin/env python3
"""Check always-loaded instruction files against deterministic size budgets."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


DEFAULT_BUDGETS = {
    "CLAUDE.md": 1_500,
    "AGENTS.md": 8_000,
    "ai/rules/agent-user-global.md": 13_000,
    "ai/rules/tool-priority.md": 11_000,
}


@dataclass(frozen=True)
class BudgetResult:
    path: str
    limit_bytes: int
    actual_bytes: int
    status: str


def check_instruction_budgets(
    root: Path,
    budgets: dict[str, int] | None = None,
) -> list[BudgetResult]:
    results: list[BudgetResult] = []
    for relative_path, limit in sorted((budgets or DEFAULT_BUDGETS).items()):
        path = root / relative_path
        if not path.is_file():
            results.append(BudgetResult(relative_path, limit, 0, "missing"))
            continue
        actual = len(path.read_bytes())
        results.append(
            BudgetResult(
                path=relative_path,
                limit_bytes=limit,
                actual_bytes=actual,
                status="ok" if actual <= limit else "over-budget",
            )
        )
    return results


def summarize_results(results: Sequence[BudgetResult]) -> dict[str, object]:
    by_status: dict[str, int] = {}
    for result in results:
        by_status[result.status] = by_status.get(result.status, 0) + 1
    return {
        "total": len(results),
        "by_status": dict(sorted(by_status.items())),
        "max_overage_bytes": max(
            [max(0, result.actual_bytes - result.limit_bytes) for result in results],
            default=0,
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    results = check_instruction_budgets(args.root.resolve())
    if args.summary:
        print(json.dumps(summarize_results(results), indent=2))
    else:
        print(json.dumps([asdict(result) for result in results], indent=2))
    return 1 if any(result.status != "ok" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
