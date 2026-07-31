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
    # Gemini's always-loaded guidance file. Added 2026-07-28: it was the only always-loaded
    # adapter with no ceiling, and it carries a "## Gemini Added Memories" section that the tool
    # appends to, so its growth is agent-driven and otherwise unbounded. 1,711 bytes at the time
    # of writing; 4,000 leaves room for real guidance while still failing on runaway memory.
    ".gemini/GEMINI.md": 4_000,
}


@dataclass(frozen=True)
class BudgetResult:
    path: str
    limit_bytes: int
    actual_bytes: int
    status: str


@dataclass(frozen=True)
class ClientBudgetResult:
    client: str
    entrypoint: str
    files: int
    actual_bytes: int
    estimated_tokens: int


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


_DEFAULT_CLIENT_ENTRYPOINTS = {
    "claude": ".claude/CLAUDE.md",
    "codex": ".codex/AGENTS.md",
    "cursor": ".cursor/rules.md",
    "agy": ".gemini/GEMINI.md",
}


def _import_targets(path: Path) -> list[str]:
    targets: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return targets
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("@") and not stripped.startswith("@@"):
            target = stripped[1:].strip().split(maxsplit=1)[0]
            if target:
                targets.append(target)
    return targets


def _transitive_instruction_paths(entrypoint: Path) -> list[Path]:
    ordered: list[Path] = []
    visited: set[Path] = set()

    def visit(path: Path) -> None:
        try:
            canonical = path.resolve()
        except OSError:
            canonical = path.absolute()
        if canonical in visited or not canonical.is_file():
            return
        visited.add(canonical)
        ordered.append(canonical)
        for target in _import_targets(canonical):
            visit((canonical.parent / target).resolve())

    visit(entrypoint)
    return ordered


def check_client_instruction_budgets(
    root: Path,
    entrypoints: dict[str, str] | None = None,
) -> list[ClientBudgetResult]:
    results: list[ClientBudgetResult] = []
    for client, relative_path in sorted(
        (entrypoints or _DEFAULT_CLIENT_ENTRYPOINTS).items()
    ):
        paths = _transitive_instruction_paths(root / relative_path)
        actual_bytes = sum(len(path.read_bytes()) for path in paths)
        results.append(
            ClientBudgetResult(
                client=client,
                entrypoint=relative_path,
                files=len(paths),
                actual_bytes=actual_bytes,
                estimated_tokens=(actual_bytes + 3) // 4,
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
        summary = summarize_results(results)
        summary["clients"] = [
            asdict(result)
            for result in check_client_instruction_budgets(args.root.resolve())
        ]
        print(json.dumps(summary, indent=2))
    else:
        print(json.dumps([asdict(result) for result in results], indent=2))
    return 1 if any(result.status != "ok" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
