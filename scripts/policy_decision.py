#!/usr/bin/env python3
"""Record explicit human decisions for policy proposals without applying them."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

try:
    from scripts.policy_proposal import _load, validate_proposal
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.policy_proposal import _load, validate_proposal


DECISIONS = frozenset({"accept", "reject", "defer"})


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _load_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"ledger line {line_number} must be an object")
        entries.append(value)
    return entries


def record_decision(
    proposal_path: Path,
    ledger_path: Path,
    *,
    decision: str,
    rationale: str,
    decided_at: str,
) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of: {', '.join(sorted(DECISIONS))}")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("rationale must be non-empty")
    try:
        date.fromisoformat(decided_at)
    except (TypeError, ValueError) as error:
        raise ValueError("decided_at must be an ISO date") from error

    raw = proposal_path.read_bytes()
    proposal = _load(proposal_path)
    errors = validate_proposal(proposal)
    if errors:
        raise ValueError("proposal invalid: " + "; ".join(errors))
    review_after = proposal["review_after"]
    if decision == "accept" and not review_after.startswith("condition:"):
        if date.fromisoformat(decided_at) > date.fromisoformat(review_after):
            raise ValueError("accept decision is past the proposal review deadline")
    entry: dict[str, Any] = {
        "proposal_id": proposal["id"],
        "proposal_sha256": hashlib.sha256(raw).hexdigest(),
        "decision": decision,
        "rationale": rationale.strip(),
        "decided_at": decided_at,
        "review_after": review_after,
        "recorded_by": "human",
        "applied": False,
    }
    entries = _load_ledger(ledger_path)
    if entry in entries:
        raise ValueError("identical decision is already recorded")
    content = "\n".join(json.dumps(item, sort_keys=True) for item in [*entries, entry]) + "\n"
    _atomic_write(ledger_path, content)
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposal", type=Path)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--decision", required=True, choices=sorted(DECISIONS))
    parser.add_argument("--rationale", required=True)
    parser.add_argument("--decided-at", required=True)
    args = parser.parse_args(argv)
    try:
        entry = record_decision(
            args.proposal,
            args.ledger,
            decision=args.decision,
            rationale=args.rationale,
            decided_at=args.decided_at,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"recorded": False, "error": str(error)}, indent=2))
        return 2
    print(json.dumps({"recorded": entry, "ledger": str(args.ledger)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
