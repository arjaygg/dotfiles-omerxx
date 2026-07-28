#!/usr/bin/env python3
"""Generate the skill router (`ai/skills/using-my-skills/SKILL.md`) from `ai/skills/manifest.csv`.

The router's decision tree is generated, never hand-written: the manifest is the single source
of truth for which skill runs in which phase and what precedes or follows it. Regeneration is
idempotent — running this twice produces a byte-identical file.

    python3 scripts/generate_router.py            # write the router
    python3 scripts/generate_router.py --check    # exit 1 if the router is stale
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "ai/skills/manifest.csv"
ROUTER = ROOT / "ai/skills/using-my-skills/SKILL.md"

COLUMNS = ["skill", "phase", "preceded-by", "followed-by", "output-location", "outputs"]

# Phases in execution order. A phase absent from the manifest is simply not rendered.
PHASE_ORDER = ["orient", "diagnose", "plan", "implement", "review", "ship", "operate"]

PHASE_QUESTION = {
    "orient": "Do I understand the code and have the right tool for the lookup?",
    "diagnose": "Is something broken, and do I know why?",
    "plan": "Is the intended outcome written down where it survives this session?",
    "implement": "Am I making the change?",
    "review": "Has the change been checked by something other than the author?",
    "ship": "Is it committed, reviewed, green, and merged?",
    "operate": "Does this need to keep running after the session ends?",
}

BANNER = """<!-- GENERATED FILE — DO NOT EDIT.
     Source: ai/skills/manifest.csv
     Regenerate: python3 scripts/generate_router.py
     Any edit here is overwritten on the next regeneration. -->"""

FRONTMATTER = """---
name: using-my-skills
description: >
  Skill router and core operating behaviors. Names which skill owns each phase of a task —
  orient, diagnose, plan, implement, review, ship, operate — what precedes and follows it, and
  where its output lands. Injected once per session; consult it when unsure which skill applies.
triggers:
  - which skill should I use
  - what skill handles this
  - skill router
version: 1.0.0
model: sonnet
allowed-tools:
  - Read
---"""

BEHAVIORS = """## Core operating behaviors

These six sit above every individual skill and are **non-negotiable**. They apply whether or not
any skill is invoked.

1. **Surface assumptions.** State them before non-trivial work: "correct me now or I proceed."
2. **Manage confusion actively.** On an inconsistency: stop, name it, present the tradeoff, wait.
   Do not resolve it silently by guessing.
3. **Push back when warranted.** Quantify the downside — "adds ~200 ms latency", not "might be
   slower." Sycophancy is a failure mode, not politeness.
4. **Enforce simplicity.** If you build 1000 lines and 100 would suffice, you have failed.
5. **Maintain scope discipline.** Surgical precision, not unsolicited renovation.
6. **Verify, don't assume.** Evidence, never "seems right." Run the check and show its output."""

VERIFICATION = """## Verification

- The phase you routed to answers the question actually asked, not an adjacent one.
- The skill you picked appears in the manifest for that phase — you did not invent a route.
- Any skill named in `preceded-by` either already ran or was deliberately skipped, and you said which."""


def read_manifest(path: Path = MANIFEST) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise SystemExit(
                f"{path}: expected columns {COLUMNS}, got {reader.fieldnames}"
            )
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def render(rows: list[dict[str, str]]) -> str:
    by_phase: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_phase.setdefault(row["phase"], []).append(row)

    unknown = sorted(set(by_phase) - set(PHASE_ORDER))
    if unknown:
        raise SystemExit(f"{MANIFEST}: unknown phase(s): {', '.join(unknown)}")

    parts = [FRONTMATTER, "", BANNER, "", "# Using My Skills", ""]
    parts.append(
        "Routing table generated from `ai/skills/manifest.csv`. Work the phases in order; "
        "within a phase, pick the row whose output you actually need."
    )
    parts.append("")

    for phase in PHASE_ORDER:
        entries = by_phase.get(phase)
        if not entries:
            continue
        parts.append(f"## {phase.capitalize()} — {PHASE_QUESTION[phase]}")
        parts.append("")
        parts.append("| Skill | After | Before | Output | Lands in |")
        parts.append("|---|---|---|---|---|")
        for row in sorted(entries, key=lambda r: r["skill"]):
            after = f"`{row['preceded-by']}`" if row["preceded-by"] else "—"
            before = f"`{row['followed-by']}`" if row["followed-by"] else "—"
            location = f"`{row['output-location']}`" if row["output-location"] else "—"
            parts.append(
                f"| `{row['skill']}` | {after} | {before} | {row['outputs']} | {location} |"
            )
        parts.append("")

    parts.append(BEHAVIORS)
    parts.append("")
    parts.append(VERIFICATION)
    parts.append("")
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the router is stale")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--out", type=Path, default=ROUTER)
    args = parser.parse_args(argv)

    generated = render(read_manifest(args.manifest))

    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.is_file() else ""
        if current != generated:
            print(
                f"{args.out} is stale — run: python3 scripts/generate_router.py",
                file=sys.stderr,
            )
            return 1
        print(f"{args.out}: up to date")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(generated, encoding="utf-8")
    print(f"wrote {args.out} ({len(generated.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
