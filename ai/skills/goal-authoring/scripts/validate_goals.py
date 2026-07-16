#!/usr/bin/env python3
"""Validate a repository's goals/ directory against the goal-authoring convention.

Checks:
- goal filenames follow YYYY-MM-DD-NN-slug.md;
- goals/00-index.md lists every goal exactly once with a valid status;
- at most one goal is active;
- if one goal is active, plans/active-context.md points at it;
- every goal contains required headings in order.

Copy this file to <project-root>/scripts/validate_goals.py — it resolves its
own project root from its own location (parents[1]), so it must live exactly
one directory below the root it validates.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOALS = ROOT / "goals"
INDEX = GOALS / "00-index.md"
ACTIVE_CONTEXT = ROOT / "plans" / "active-context.md"

GOAL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-(\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
INDEX_ROW_RE = re.compile(
    r"^\|\s*(?P<seq>\d{2})\s*\|\s*(?P<status>pending|active|blocked|done|superseded)\s*\|\s*`(?P<file>[^`]+)`\s*\|",
    re.IGNORECASE,
)
VALID_STATUSES = {"pending", "active", "blocked", "done", "superseded"}
REQUIRED_HEADINGS = [
    "## Objective",
    "## Why",
    "## Current state",
    "## Non-goals",
    "## Steps",
    "## Acceptance criteria",
    "## Evidence to update",
    "## Stop and ask if",
]

ERRORS: list[str] = []


def error(msg: str) -> None:
    ERRORS.append(msg)
    print(f"ERROR: {msg}", file=sys.stderr)


def read(path: Path) -> str | None:
    try:
        return path.read_text()
    except FileNotFoundError:
        error(f"missing required file: {path.relative_to(ROOT)}")
        return None


def parse_index() -> dict[str, str]:
    text = read(INDEX)
    entries: dict[str, str] = {}
    if text is None:
        return entries
    for line in text.splitlines():
        match = INDEX_ROW_RE.match(line)
        if not match:
            continue
        status = match.group("status").lower()
        filename = match.group("file")
        seq = match.group("seq")
        entries[filename] = status
        if not GOAL_RE.match(Path(filename).name):
            error(f"index entry has invalid goal filename: {filename}")
            continue
        file_seq = Path(filename).name.split("-", 4)[3]
        if file_seq != seq:
            error(f"index seq {seq} does not match filename seq {file_seq}: {filename}")
        if status not in VALID_STATUSES:
            error(f"invalid status {status!r} for {filename}")
    if not entries:
        error("goals/00-index.md contains no status table rows")
    return entries


def validate_goal_file(path: Path) -> None:
    if not GOAL_RE.match(path.name):
        error(f"invalid goal filename: {path.relative_to(ROOT)}")
        return
    text = read(path)
    if text is None:
        return
    expected_title_prefix = f"# Goal {path.name.split('-', 4)[3]} — "
    if not any(line.startswith(expected_title_prefix) for line in text.splitlines()[:3]):
        error(f"{path.relative_to(ROOT)} title must start with {expected_title_prefix!r}")
    pos = -1
    for heading in REQUIRED_HEADINGS:
        idx = text.find(heading)
        if idx <= pos:
            error(f"{path.relative_to(ROOT)} missing/out-of-order heading: {heading}")
        pos = idx


def active_context_goal() -> str | None:
    if not ACTIVE_CONTEXT.exists():
        return None
    for line in ACTIVE_CONTEXT.read_text().splitlines():
        if line.startswith("goal: "):
            return line.split("goal: ", 1)[1].strip()
    return None


def main() -> int:
    if not GOALS.exists():
        print("OK: no goals/ directory")
        return 0

    goal_files = sorted(p for p in GOALS.glob("*.md") if p.name not in {"README.md", "00-index.md"})
    index_entries = parse_index()

    listed = set(index_entries)
    actual = {p.name for p in goal_files}
    for missing in sorted(actual - listed):
        error(f"goal file not listed in goals/00-index.md: {missing}")
    for stale in sorted(listed - actual):
        error(f"index lists missing goal file: {stale}")

    seqs: set[str] = set()
    for path in goal_files:
        validate_goal_file(path)
        if GOAL_RE.match(path.name):
            seq = path.name.split("-", 4)[3]
            if seq in seqs:
                error(f"duplicate sequence number: {seq}")
            seqs.add(seq)

    active = [name for name, status in index_entries.items() if status == "active"]
    if len(active) > 1:
        error(f"multiple active goals: {', '.join(active)}")
    if len(active) == 1:
        expected = f"goals/{active[0]}"
        actual_goal = active_context_goal()
        if actual_goal != expected:
            error(f"active goal mismatch: index={expected}, plans/active-context.md={actual_goal!r}")

    if ERRORS:
        print(f"FAIL: {len(ERRORS)} goal validation error(s)", file=sys.stderr)
        return 1

    print(f"PASS: {len(goal_files)} goal file(s) validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
