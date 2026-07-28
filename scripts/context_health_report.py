#!/usr/bin/env python3
"""Combine routing, instruction, LeanCtx, and Headroom health metrics."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.context_routing_report import summarize_metrics
from scripts.headroom_hardening import (
    audit_ccr_database,
    docker_containers,
    summarize_containers,
)
from scripts.instruction_budget_check import check_client_instruction_budgets


def _jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def leanctx_summary(binary: Path) -> dict[str, Any]:
    result = subprocess.run(
        [str(binary), "gain", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"available": False}
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"available": False}
    summary = report.get("summary", {})
    bridge = report.get("bridge", {})
    return {
        "available": True,
        "tokens_saved": summary.get("tokens_saved", 0),
        "gain_rate_pct": summary.get("gain_rate_pct", 0),
        "injected_overhead_tokens_per_turn": summary.get(
            "injected_overhead_tokens_per_turn", 0
        ),
        "advertised_tool_count": bridge.get("tool_count", 0),
    }


def build_report(
    root: Path,
    metrics: list[dict[str, Any]],
    *,
    lean_summary: dict[str, Any],
    containers: list[dict[str, str]],
    ccr: dict[str, Any],
) -> dict[str, Any]:
    return {
        "routing": summarize_metrics(metrics),
        "instructions": [
            asdict(result) for result in check_client_instruction_budgets(root)
        ],
        "leanctx": lean_summary,
        "headroom": {
            "containers": summarize_containers(containers),
            "ccr": ccr,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument(
        "--metrics",
        type=Path,
        default=Path(
            os.environ.get(
                "XDG_STATE_HOME",
                str(Path.home() / ".local" / "state"),
            )
        )
        / "context-routing"
        / "metrics.jsonl",
    )
    parser.add_argument(
        "--lean-ctx",
        type=Path,
        default=Path.home() / ".local" / "bin" / "lean-ctx",
    )
    parser.add_argument(
        "--ccr-db",
        type=Path,
        default=Path.home() / ".headroom" / "ccr_store.db",
    )
    args = parser.parse_args(argv)
    ccr = (
        audit_ccr_database(args.ccr_db)
        if args.ccr_db.is_file()
        else {"total": 0, "invalid": 0, "deleted": 0, "ok": True}
    )
    report = build_report(
        args.root.resolve(),
        _jsonl(args.metrics),
        lean_summary=leanctx_summary(args.lean_ctx),
        containers=docker_containers(),
        ccr=ccr,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
