#!/usr/bin/env python3
"""Record privacy-preserving learning signals without applying policy changes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


SIGNAL_TYPES = frozenset(
    {
        "user_correction",
        "hook_block",
        "block_retry",
        "block_recovery",
        "pr_review",
        "reverted_change",
        "tool_routing_error",
        "ignored_instruction",
        "context_regression",
        "stale_rule",
        "contradictory_rule",
        "dead_reference",
        "successful_workflow",
    }
)
EVIDENCE_CLASSES = frozenset(
    {"recurrence", "security", "compliance", "production", "data_loss", "cost", "deterministic"}
)
SIGNAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
INPUT_FIELDS = frozenset(
    {
        "signal_id",
        "signal_type",
        "occurred_at",
        "session_ref",
        "event_ref",
        "recurrence_key",
        "evidence_class",
        "recurrence_count",
    }
)


class SignalValidationError(ValueError):
    """Raised when an untrusted signal cannot be safely recorded."""


def _string(value: Any, field: str, *, max_length: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length or "\x00" in value:
        raise SignalValidationError(f"{field} must be a non-empty bounded string")
    return value


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sanitize_signal(value: Any) -> dict[str, Any]:
    """Validate and reduce a signal to metadata safe for an external JSONL ledger."""

    if not isinstance(value, dict):
        raise SignalValidationError("signal must be an object")
    unknown = set(value) - INPUT_FIELDS
    if unknown:
        raise SignalValidationError(f"unsupported or unsafe signal fields: {', '.join(sorted(unknown))}")
    missing = INPUT_FIELDS - set(value)
    if missing:
        raise SignalValidationError(f"signal missing fields: {', '.join(sorted(missing))}")

    signal_id = _string(value["signal_id"], "signal_id", max_length=128)
    if not SIGNAL_ID.fullmatch(signal_id):
        raise SignalValidationError("signal_id must use portable identifier characters")
    signal_type = _string(value["signal_type"], "signal_type", max_length=64)
    if signal_type not in SIGNAL_TYPES:
        raise SignalValidationError(f"unsupported signal_type: {signal_type}")
    occurred_at = _string(value["occurred_at"], "occurred_at", max_length=64)
    try:
        parsed_time = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise SignalValidationError("occurred_at must be an ISO-8601 timestamp") from error
    if parsed_time.tzinfo is None:
        raise SignalValidationError("occurred_at must include a timezone")
    evidence_class = _string(value["evidence_class"], "evidence_class", max_length=32)
    if evidence_class not in EVIDENCE_CLASSES:
        raise SignalValidationError(f"unsupported evidence_class: {evidence_class}")
    recurrence_count = value["recurrence_count"]
    if isinstance(recurrence_count, bool) or not isinstance(recurrence_count, int) or recurrence_count < 1:
        raise SignalValidationError("recurrence_count must be a positive integer")

    return {
        "schema": 1,
        "signal_id": signal_id,
        "signal_type": signal_type,
        "occurred_at": occurred_at,
        "session_ref_sha256": _sha256(_string(value["session_ref"], "session_ref")),
        "event_ref_sha256": _sha256(_string(value["event_ref"], "event_ref")),
        "recurrence_key_sha256": _sha256(_string(value["recurrence_key"], "recurrence_key")),
        "evidence_class": evidence_class,
        "recurrence_count": recurrence_count,
        "raw_evidence_stored": False,
        "auto_promote": False,
        "promotion_status": "review-required",
        "applied": False,
    }


def _read_existing(path: Path) -> bytes:
    if not path.exists():
        return b""
    content = path.read_bytes()
    if content and not content.endswith(b"\n"):
        raise SignalValidationError("signal ledger must contain newline-delimited JSON")
    for line in content.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as error:
            raise SignalValidationError("signal ledger contains invalid JSON") from error
        if not isinstance(entry, dict):
            raise SignalValidationError("signal ledger entries must be objects")
    return content


def record_signal(root: Path, ledger_path: Path, signal: Any) -> dict[str, Any]:
    """Atomically append sanitized metadata to an explicitly external ledger."""

    root = root.resolve()
    ledger = ledger_path.expanduser().resolve()
    try:
        ledger.relative_to(root)
    except ValueError:
        pass
    else:
        raise SignalValidationError("signal ledger must remain outside the repository")

    sanitized = sanitize_signal(signal)
    existing = _read_existing(ledger)
    for line in existing.splitlines():
        entry = json.loads(line)
        if entry.get("signal_id") == sanitized["signal_id"]:
            raise SignalValidationError(f"signal_id already recorded: {sanitized['signal_id']}")
    encoded = (json.dumps(sanitized, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=ledger.parent, prefix=f".{ledger.name}.", delete=False
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(existing)
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, ledger)
    finally:
        if temporary_name is not None and Path(temporary_name).exists():
            Path(temporary_name).unlink()
    return sanitized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        signal = json.loads(args.input.read_text(encoding="utf-8"))
        result = record_signal(args.root, args.ledger, signal)
    except (OSError, UnicodeError, json.JSONDecodeError, SignalValidationError) as error:
        print(f"learning signal rejected: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
