#!/usr/bin/env python3
"""Build a validated configuration proposal without writing runtime files."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
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


@dataclass(frozen=True)
class ProposalComparison:
    changed_paths: list[str]
    proposal_sha256: str
    target_sha256: str


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


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        if not value:
            return {prefix: value}
        flattened: dict[str, Any] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            flattened.update(_flatten(child, child_prefix))
        return flattened
    if isinstance(value, list):
        if not value:
            return {prefix: value}
        flattened = {}
        for index, child in enumerate(value):
            flattened.update(_flatten(child, f"{prefix}[{index}]"))
        return flattened
    return {prefix: value}


def compare_proposal(
    base_path: Path, overlay_path: Path | None, target_path: Path
) -> ProposalComparison:
    """Compare a proposal with a target without printing target contents."""
    proposal_text = build_proposal(base_path, overlay_path)
    target_bytes = target_path.read_bytes()
    target = json.loads(target_bytes)
    if not isinstance(target, dict):
        raise TemplateValidationError(f"{target_path}: target root must be a JSON object")
    proposal = json.loads(proposal_text)
    proposal_values = _flatten(proposal)
    target_values = _flatten(target)
    changed_paths = sorted(
        path
        for path in proposal_values.keys() | target_values.keys()
        if proposal_values.get(path) != target_values.get(path)
    )
    return ProposalComparison(
        changed_paths=changed_paths,
        proposal_sha256=hashlib.sha256(proposal_text.encode("utf-8")).hexdigest(),
        target_sha256=hashlib.sha256(target_bytes).hexdigest(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--compare-against", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.compare_against:
            print(json.dumps(asdict(compare_proposal(args.base, args.overlay, args.compare_against))))
        else:
            sys.stdout.write(build_proposal(args.base, args.overlay))
    except (OSError, UnicodeError, json.JSONDecodeError, TemplateValidationError) as error:
        print(f"config proposal rejected: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
