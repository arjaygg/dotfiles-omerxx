"""Manifest coverage checks for the generated skill router.

Two directions, both failures:
  - a manifest row naming a skill that does not exist  -> manifest-unknown-skill
  - an enabled skill absent from the manifest          -> manifest-missing-skill

"Enabled" means a directory under `ai/skills/` with a `SKILL.md` that is not marked `"off"` in
`.claude/settings.json`'s `skillOverrides`. Disabled skills may appear in the manifest or not;
they are never required.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

COLUMNS = ["skill", "phase", "preceded-by", "followed-by", "output-location", "outputs"]


def read_manifest(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Return (rows, errors). A malformed header is an error, not an exception."""
    if not path.is_file():
        return [], [f"{path}: manifest not found"]
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            return [], [f"{path}: expected columns {COLUMNS}, got {reader.fieldnames}"]
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
    return rows, []


def enabled_skills(repo_root: Path) -> set[str]:
    skills_dir = repo_root / "ai" / "skills"
    present = {p.name for p in skills_dir.iterdir() if (p / "SKILL.md").is_file()}
    settings = repo_root / ".claude" / "settings.json"
    off: set[str] = set()
    if settings.is_file():
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        off = {k for k, v in data.get("skillOverrides", {}).items() if v == "off"}
    return present - off


def check_manifest(repo_root: Path) -> list[tuple[str, str]]:
    """Return a list of (rule, message) pairs. Empty means the manifest is consistent."""
    manifest_path = repo_root / "ai" / "skills" / "manifest.csv"
    rows, errors = read_manifest(manifest_path)
    issues = [("manifest-malformed", message) for message in errors]
    if errors:
        return issues

    skills_dir = repo_root / "ai" / "skills"
    existing = {p.name for p in skills_dir.iterdir() if (p / "SKILL.md").is_file()}
    listed = set()

    for row in rows:
        name = row["skill"]
        listed.add(name)
        if name not in existing:
            issues.append(
                ("manifest-unknown-skill", f"manifest row names a nonexistent skill: {name}")
            )
        for column in ("preceded-by", "followed-by"):
            neighbour = row[column]
            if neighbour and neighbour not in existing:
                issues.append(
                    (
                        "manifest-unknown-skill",
                        f"{name}: {column} names a nonexistent skill: {neighbour}",
                    )
                )

    for name in sorted(enabled_skills(repo_root) - listed):
        issues.append(
            ("manifest-missing-skill", f"enabled skill absent from the manifest: {name}")
        )

    return issues
