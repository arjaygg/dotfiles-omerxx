#!/usr/bin/env python3
"""Resolve a skill's customization layers into one merged config.

Skills are symlinked from `ai/skills/` into every consumer, so per-project or personal
customization would otherwise mean editing the shared source of truth. This resolver reads
three layers in order and merges them, leaving the shipped file untouched:

  1. {skill-root}/customize.toml              shipped defaults (DO NOT EDIT)
  2. .claude/custom/<skill>.toml              team
  3. .claude/custom/<skill>.user.toml         personal

Merge rules (later layer wins):
  - scalars                                   override
  - tables                                    deep-merge
  - arrays of tables keyed by `code` or `id`  replace on matching key, append on new
  - all other arrays                          append

A value prefixed `file:` is a path or glob, resolved relative to the layer file's own
directory, whose contents are loaded in its place. If a `file:` value cannot be read, the
failed path is named in the output header and resolution continues — partial failure is
reported, never silent.

Usage:
    python3 scripts/resolve_customization.py <skill> [--skills-dir DIR] [--custom-dir DIR]
    python3 scripts/resolve_customization.py <skill> --json
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILLS_DIR = ROOT / "ai/skills"
DEFAULT_CUSTOM_DIR = ROOT / ".claude/custom"

KEYED_BY = ("code", "id")


class Resolution:
    """Merged config plus the diagnostics a caller must surface."""

    def __init__(self) -> None:
        self.config: dict[str, Any] = {}
        self.layers: list[str] = []
        self.missing_files: list[str] = []

    def header(self) -> str:
        lines = [f"layers applied: {', '.join(self.layers) if self.layers else '(none)'}"]
        for path in self.missing_files:
            lines.append(f"file: value could not be read, skipped: {path}")
        return "\n".join(lines)


def _is_table_array(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, dict) for v in value)


def _key_field(array: list[dict[str, Any]]) -> str | None:
    """Return the keying field if every element carries the same one."""
    for field in KEYED_BY:
        if all(field in element for element in array):
            return field
    return None


def merge_arrays_of_tables(base: list[Any], incoming: list[Any]) -> list[Any]:
    """Replace elements whose key matches, append the rest. Order follows base, then new."""
    field = _key_field(base) if _is_table_array(base) else None
    if field is None or _key_field(incoming) != field:
        return base + incoming

    merged = [dict(element) for element in base]
    index = {element[field]: position for position, element in enumerate(merged)}
    for element in incoming:
        key = element[field]
        if key in index:
            merged[index[key]] = dict(element)
        else:
            index[key] = len(merged)
            merged.append(dict(element))
    return merged


def merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Apply the four merge rules, returning a new dict."""
    result = dict(base)
    for key, value in incoming.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = merge(existing, value)
        elif isinstance(existing, list) and isinstance(value, list):
            if _is_table_array(existing) and _is_table_array(value):
                result[key] = merge_arrays_of_tables(existing, value)
            else:
                result[key] = existing + value
        else:
            result[key] = value
    return result


def expand_file_values(
    value: Any, base_dir: Path, missing: list[str]
) -> Any:
    """Replace `file:` scalars with the referenced contents, recursively."""
    if isinstance(value, dict):
        return {k: expand_file_values(v, base_dir, missing) for k, v in value.items()}
    if isinstance(value, list):
        return [expand_file_values(v, base_dir, missing) for v in value]
    if not isinstance(value, str) or not value.startswith("file:"):
        return value

    pattern = value[len("file:") :].strip()
    matches = sorted(glob.glob(str(base_dir / pattern)))
    if not matches:
        missing.append(pattern)
        return value

    contents = []
    for match in matches:
        try:
            contents.append(Path(match).read_text(encoding="utf-8"))
        except OSError:
            missing.append(match)
    if not contents:
        return value
    return contents[0] if len(contents) == 1 else contents


def load_layer(path: Path, missing: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    return expand_file_values(data, path.parent, missing)


def resolve(
    skill: str,
    skills_dir: Path = DEFAULT_SKILLS_DIR,
    custom_dir: Path = DEFAULT_CUSTOM_DIR,
) -> Resolution:
    resolution = Resolution()
    layer_paths = [
        skills_dir / skill / "customize.toml",
        custom_dir / f"{skill}.toml",
        custom_dir / f"{skill}.user.toml",
    ]
    for path in layer_paths:
        data = load_layer(path, resolution.missing_files)
        if data is None:
            continue
        resolution.layers.append(str(path))
        resolution.config = merge(resolution.config, data)
    return resolution


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("skill")
    parser.add_argument("--skills-dir", type=Path, default=DEFAULT_SKILLS_DIR)
    parser.add_argument("--custom-dir", type=Path, default=DEFAULT_CUSTOM_DIR)
    parser.add_argument("--json", action="store_true", help="emit config as JSON only")
    args = parser.parse_args(argv)

    resolution = resolve(args.skill, args.skills_dir, args.custom_dir)
    if not resolution.layers:
        print(f"no customization layers found for {args.skill!r}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(resolution.config, indent=2, sort_keys=True))
    else:
        print(resolution.header())
        print()
        print(json.dumps(resolution.config, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
