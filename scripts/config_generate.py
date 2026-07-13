#!/usr/bin/env python3
"""Build a validated configuration proposal without writing runtime files."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.public_hygiene_check import scan_text
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.public_hygiene_check import scan_text


class TemplateValidationError(ValueError):
    """Raised when a base or overlay contains non-portable content."""


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Return a recursively merged copy; overlay values replace base values."""
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_template(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    findings = scan_text(path.as_posix(), text)
    if findings:
        summary = ", ".join(f"{finding.rule}@{finding.line}" for finding in findings)
        raise TemplateValidationError(f"{path}: non-portable template findings: {summary}")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise TemplateValidationError(f"{path}: template root must be a JSON object")
    return value


def build_proposal(base_path: Path, overlay_path: Path | None = None) -> str:
    """Return merged JSON for review; never writes either input or runtime files."""
    base = _load_template(base_path)
    overlay = _load_template(overlay_path) if overlay_path else {}
    proposal = deep_merge(base, overlay)
    rendered = json.dumps(proposal, indent=2, sort_keys=True) + "\n"
    findings = scan_text("<proposal>", rendered)
    if findings:
        summary = ", ".join(f"{finding.rule}@{finding.line}" for finding in findings)
        raise TemplateValidationError(f"proposal: non-portable findings: {summary}")
    return rendered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("--overlay", type=Path)
    args = parser.parse_args(argv)
    try:
        sys.stdout.write(build_proposal(args.base, args.overlay))
    except (OSError, UnicodeError, json.JSONDecodeError, TemplateValidationError) as error:
        print(f"config proposal rejected: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
