#!/usr/bin/env python3
"""Summarize tracked base, runtime, and overlay ownership from ai/config/manifest.json."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class InventoryRow:
    name: str
    format: str
    base: str
    runtime: str
    overlay: str
    base_scope: str
    source_status: str
    format_status: str
    runtime_scope: str
    overlay_scope: str


FORMAT_SUFFIXES = {
    "json": ".json",
    "toml": ".toml",
}


def _has_parent_traversal(path: str) -> bool:
    return ".." in Path(path).parts


def _base_scope(path: str) -> str:
    if path.startswith("~/"):
        return "user-base-path"
    if path.startswith("/") or _has_parent_traversal(path):
        return "unsafe-base-path"
    if path.startswith("ai/config/"):
        return "tracked-portable-base"
    return "tracked-non-config-base"


def _runtime_scope(path: str) -> str:
    if path.startswith("~/"):
        return "user-runtime"
    if path.startswith("/"):
        return "absolute-runtime-path"
    return "tracked-runtime-path"


def _overlay_scope(path: str) -> str:
    if path.startswith("~/.config/dotfiles-ai/"):
        return "ignored-local-overlay"
    if path.startswith("~/"):
        return "user-overlay"
    if path.startswith("/"):
        return "absolute-overlay-path"
    return "tracked-overlay-path"


def _format_status(format_name: str, *paths: str) -> str:
    suffix = FORMAT_SUFFIXES.get(format_name)
    if suffix is None:
        return "unsupported-format"
    if all(path.endswith(suffix) for path in paths):
        return "format-ok"
    return "format-mismatch"


def build_inventory(root: Path, manifest_path: Path | None = None) -> list[InventoryRow]:
    manifest = manifest_path or root / "ai/config/manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    rows: list[InventoryRow] = []
    for client in data.get("clients", []):
        base = str(client["base"])
        runtime = str(client["runtime"])
        overlay = str(client["overlay"])
        rows.append(
            InventoryRow(
                name=str(client["name"]),
                format=str(client["format"]),
                base=base,
                runtime=runtime,
                overlay=overlay,
                base_scope=_base_scope(base),
                source_status="present" if (root / base).is_file() else "missing",
                format_status=_format_status(str(client["format"]), base, runtime, overlay),
                runtime_scope=_runtime_scope(runtime),
                overlay_scope=_overlay_scope(overlay),
            )
        )
    return rows


def summarize_inventory(rows: Sequence[InventoryRow]) -> dict[str, object]:
    def counts(attr: str) -> dict[str, int]:
        result: dict[str, int] = {}
        for row in rows:
            value = str(getattr(row, attr))
            result[value] = result.get(value, 0) + 1
        return dict(sorted(result.items()))

    return {
        "total": len(rows),
        "by_base_scope": counts("base_scope"),
        "by_source_status": counts("source_status"),
        "by_format_status": counts("format_status"),
        "by_runtime_scope": counts("runtime_scope"),
        "by_overlay_scope": counts("overlay_scope"),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--summary", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    rows = build_inventory(root, args.manifest)
    if args.summary:
        print(json.dumps(summarize_inventory(rows), indent=2))
    elif args.as_json:
        print(json.dumps([asdict(row) for row in rows], indent=2))
    else:
        for row in rows:
            print(
                f"{row.name}: base={row.source_status} runtime={row.runtime_scope} "
                f"overlay={row.overlay_scope} format={row.format_status}"
            )
    return (
        1
        if any(
            row.source_status != "present"
            or row.base_scope != "tracked-portable-base"
            or row.format_status != "format-ok"
            or row.runtime_scope != "user-runtime"
            or row.overlay_scope != "ignored-local-overlay"
            for row in rows
        )
        else 0
    )


if __name__ == "__main__":
    sys.exit(main())
