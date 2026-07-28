"""Core lint logic for ai/skills/*/SKILL.md and ai/agents/*.md frontmatter."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
TRIGGER_HINT_RE = re.compile(
    r"(use when|use for|use if|not for|triggers\s*:)", re.IGNORECASE
)
MAX_SKILL_LINES = 500


@dataclass(frozen=True)
class Issue:
    rule: str
    path: str
    message: str

    def key(self) -> str:
        return f"{self.rule}:{self.path}"


def _split_frontmatter(text: str) -> tuple[dict, str] | tuple[None, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    raw = match.group(1)
    fields: dict[str, str] = {}
    current_key = None
    for line in raw.split("\n"):
        key_match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if key_match:
            current_key = key_match.group(1)
            fields[current_key] = key_match.group(2)
        elif current_key is not None and line.startswith((" ", "\t")):
            fields[current_key] += "\n" + line.strip()
    return fields, text[match.end():]


def _has_verification_section(body: str, skill_dir: Path) -> bool:
    if re.search(r"^#+\s*Verification\b", body, re.IGNORECASE | re.MULTILINE):
        return True
    step_file_refs = re.findall(r"([\w./-]+\.md)", body)
    for ref in step_file_refs:
        candidate = (skill_dir / ref).resolve()
        if candidate.is_file():
            try:
                text = candidate.read_text(encoding="utf-8")
            except OSError:
                continue
            if re.search(r"^#+\s*Verification\b", text, re.IGNORECASE | re.MULTILINE):
                return True
    return False


def lint_skill_file(path: Path, rel_path: str | None = None) -> list[Issue]:
    issues: list[Issue] = []
    rel = rel_path if rel_path is not None else str(path)
    text = path.read_text(encoding="utf-8")
    fields, body = _split_frontmatter(text)

    if fields is None:
        issues.append(Issue("frontmatter-missing", rel, "no frontmatter block found"))
        return issues

    name = fields.get("name", "").strip()
    dir_name = path.parent.name
    if name != dir_name:
        issues.append(
            Issue(
                "name-mismatch",
                rel,
                f"frontmatter name '{name}' does not match directory '{dir_name}'",
            )
        )

    description = fields.get("description", "")
    triggers_present = "triggers" in fields
    if not description.strip():
        issues.append(Issue("description-missing", rel, "no description field"))
    elif not (TRIGGER_HINT_RE.search(description) or triggers_present):
        issues.append(
            Issue(
                "description-no-trigger",
                rel,
                "description lacks a 'Use when/for' trigger phrase and no triggers: list present",
            )
        )

    line_count = text.count("\n") + 1
    if line_count > MAX_SKILL_LINES:
        issues.append(
            Issue("too-long", rel, f"{line_count} lines exceeds {MAX_SKILL_LINES} max")
        )

    if not _has_verification_section(body, path.parent):
        issues.append(
            Issue(
                "verification-missing",
                rel,
                "no Verification section inline or in a declared step file",
            )
        )

    return issues


def lint_agent_file(path: Path, rel_path: str | None = None) -> list[Issue]:
    rel = rel_path if rel_path is not None else str(path)
    text = path.read_text(encoding="utf-8")
    fields, _ = _split_frontmatter(text)
    if fields is None or "tools" not in fields:
        return [Issue("agent-missing-tools", rel, "missing 'tools:' frontmatter key")]
    return []


def lint_repo(
    skills_glob: Iterable[Path],
    agents_glob: Iterable[Path],
    repo_root: Path | None = None,
) -> list[Issue]:
    issues: list[Issue] = []
    for skill_path in skills_glob:
        rel = str(skill_path.relative_to(repo_root)) if repo_root else None
        issues.extend(lint_skill_file(skill_path, rel))
    for agent_path in agents_glob:
        rel = str(agent_path.relative_to(repo_root)) if repo_root else None
        issues.extend(lint_agent_file(agent_path, rel))
    return issues
