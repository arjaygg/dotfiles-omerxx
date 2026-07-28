#!/usr/bin/env python3
"""Summarize privacy-safe context-routing JSONL metrics."""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def summarize_metrics(metrics: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(metrics)
    decisions = Counter(str(row.get("decision", "unknown")) for row in rows)
    read_reason_codes = {
        "small-read",
        "medium-unscoped-read",
        "large-unscoped-read",
        "huge-native-full-read",
        "focused-read",
        "focused-native-read",
        "exactness-escape",
        "ctx-read",
        "ctx-read-missing-mode",
    }
    read_rows = [row for row in rows if row.get("reason_code") in read_reason_codes]
    focused = sum(
        1
        for row in read_rows
        if row.get("requested_mode") in {"task", "reference"}
        or str(row.get("requested_mode") or "").startswith("lines:")
        or row.get("reason_code") in {"focused-read", "focused-native-read"}
    )
    exact = sum(row.get("reason_code") == "exactness-escape" for row in rows)
    returned = [
        int(row["returned_tokens"])
        for row in rows
        if isinstance(row.get("returned_tokens"), int)
    ]
    cache_rows = [row for row in rows if "cache_hit" in row]
    cache_hits = sum(bool(row.get("cache_hit")) for row in cache_rows)
    denied = decisions.get("deny", 0)
    false_positive_blocks = sum(
        row.get("reason_code") == "false-positive" for row in rows
    )
    dead_ends = sum(row.get("reason_code") == "dead-end" for row in rows)
    return {
        "events": len(rows),
        "reads": {"full": len(read_rows) - focused, "focused": focused},
        "decisions": dict(sorted(decisions.items())),
        "escape_hatches": exact,
        "returned_tokens": {
            "count": len(returned),
            "p50": _percentile(returned, 0.50),
            "p95": _percentile(returned, 0.95),
            "max": max(returned, default=0),
        },
        "cache": {
            "hits": cache_hits,
            "misses": len(cache_rows) - cache_hits,
            "hit_rate": round(cache_hits / len(cache_rows), 4) if cache_rows else 0.0,
        },
        "false_positive_blocks": false_positive_blocks,
        "false_positive_rate": (
            round(false_positive_blocks / denied, 4) if denied else 0.0
        ),
        "dead_ends": dead_ends,
        "dead_end_rate": round(dead_ends / denied, 4) if denied else 0.0,
        "unexpandable_references": sum(
            row.get("reason_code") == "unexpandable-reference" for row in rows
        ),
    }


def _default_metrics_path() -> Path:
    state_home = Path(
        os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
    )
    return state_home / "context-routing" / "metrics.jsonl"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=_default_metrics_path())
    args = parser.parse_args(argv)
    rows: list[dict[str, Any]] = []
    if args.path.is_file():
        for line in args.path.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    print(json.dumps(summarize_metrics(rows), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
