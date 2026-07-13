#!/usr/bin/env python3
"""Validate reviewable, non-self-promoting policy-evolution proposals."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional local convenience
    yaml = None


REQUIRED_FIELDS = (
    "id",
    "owner",
    "problem",
    "evidence",
    "recurrence",
    "current_behavior",
    "proposed_destination",
    "proposed_change",
    "expected_effect",
    "risks",
    "conflicts",
    "context_cost",
    "evaluation",
    "review_after",
    "evidence_class",
)
DESTINATIONS = frozenset({"AGENTS.md", "CLAUDE.md", "rule", "skill", "hook", "CI", "docs", "memory"})
EVIDENCE_CLASSES = frozenset({"recurrence", "security", "compliance", "production", "data_loss", "cost", "deterministic"})
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]+$")
OWNER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@:+-]{0,127}$")
CONDITION_PREFIX = "condition:"
TEXT_FIELDS = (
    "problem",
    "current_behavior",
    "proposed_change",
    "expected_effect",
    "risks",
    "conflicts",
    "context_cost",
    "evaluation",
    "review_after",
)


def validate_proposal(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["proposal must be an object"]
    errors = [f"missing required field: {field}" for field in REQUIRED_FIELDS if field not in value]
    if errors:
        return errors
    if not isinstance(value["id"], str) or not ID_PATTERN.fullmatch(value["id"]):
        errors.append("id must use lowercase letters, digits, dots, underscores, or hyphens")
    if not isinstance(value["owner"], str) or not OWNER_PATTERN.fullmatch(value["owner"]):
        errors.append("owner must use portable owner characters and be at most 128 characters")
    for field in TEXT_FIELDS:
        if not isinstance(value[field], str) or not value[field].strip():
            errors.append(f"{field} must be a non-empty string")
    review_after = value["review_after"]
    valid_date = False
    if isinstance(review_after, str):
        try:
            date.fromisoformat(review_after)
            valid_date = True
        except ValueError:
            valid_date = review_after.startswith(CONDITION_PREFIX) and bool(review_after[len(CONDITION_PREFIX) :].strip())
    if not valid_date:
        errors.append("review_after must be an ISO date or condition:<description>")
    evidence = value["evidence"]
    if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) and item.strip() for item in evidence):
        errors.append("evidence must be a non-empty list of strings")
    recurrence = value["recurrence"]
    if isinstance(recurrence, bool) or not isinstance(recurrence, int) or recurrence < 1:
        errors.append("recurrence must be a positive integer")
    destination = value["proposed_destination"]
    if destination not in DESTINATIONS:
        errors.append(f"unsupported proposed_destination: {destination}")
    evidence_class = value["evidence_class"]
    if evidence_class not in EVIDENCE_CLASSES:
        errors.append(f"unsupported evidence_class: {evidence_class}")
    elif evidence_class == "recurrence" and isinstance(recurrence, int) and not isinstance(recurrence, bool) and recurrence < 2:
        errors.append("recurrence evidence requires recurrence >= 2")
    if value.get("auto_promote") is True:
        errors.append("auto_promote must not be true")
    if value.get("auto_apply") is True:
        errors.append("auto_apply must not be true")
    return errors


def _metric_values(value: Any, label: str) -> dict[str, int | float]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"{label} metrics must be a non-empty object")
    metrics: dict[str, int | float] = {}
    for name, metric in value.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{label} metric names must be non-empty strings")
        if isinstance(metric, bool) or not isinstance(metric, (int, float)) or not math.isfinite(metric):
            raise ValueError(f"{label} metrics must contain finite numbers")
        metrics[name] = metric
    return metrics


def build_review_report(
    proposal: Any,
    baseline: Any,
    candidate: Any,
) -> dict[str, Any]:
    proposal_errors = validate_proposal(proposal)
    if proposal_errors:
        raise ValueError("proposal invalid: " + "; ".join(proposal_errors))
    baseline_metrics = _metric_values(baseline, "baseline")
    candidate_metrics = _metric_values(candidate, "candidate")
    if set(baseline_metrics) != set(candidate_metrics):
        raise ValueError("baseline and candidate metric names must match")

    metrics: dict[str, dict[str, int | float | bool]] = {}
    for name in sorted(baseline_metrics):
        before = baseline_metrics[name]
        after = candidate_metrics[name]
        metrics[name] = {
            "baseline": before,
            "candidate": after,
            "delta": after - before,
            "changed": before != after,
        }
    status = "changed" if any(metric["changed"] for metric in metrics.values()) else "unchanged"
    return {
        "proposal_id": proposal["id"],
        "owner": proposal["owner"],
        "decision": "review-required",
        "auto_promote": False,
        "evidence_gate": {
            "recurrence": proposal["recurrence"],
            "evidence_class": proposal["evidence_class"],
        },
        "review_after": proposal["review_after"],
        "evaluation": {"status": status, "metrics": metrics},
    }


def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    if yaml is None:
        raise ValueError("YAML input requires PyYAML; use JSON, which is YAML-compatible")
    return yaml.safe_load(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a YAML or JSON proposal")
    validate.add_argument("path", type=Path)
    review = subparsers.add_parser("review", help="compare a proposal's baseline and candidate metrics")
    review.add_argument("proposal", type=Path)
    review.add_argument("--baseline", type=Path, required=True)
    review.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "review":
            report = build_review_report(
                _load(args.proposal),
                _load(args.baseline),
                _load(args.candidate),
            )
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        value = _load(args.path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"valid": False, "errors": [str(error)]}, indent=2))
        return 2
    errors = validate_proposal(value)
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
