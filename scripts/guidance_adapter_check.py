#!/usr/bin/env python3
"""Validate thin agent adapters still point at neutral shared guidance."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class GuidanceResult:
    rule: str
    path: str
    status: str
    message: str = ""


REQUIRED_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "docs/agent-configuration-architecture.md",
    "ai/rules/agent-user-global.md",
    "ai/rules/tool-priority.md",
    "ai/rules/context-and-compaction.md",
    ".claude/CLAUDE.md",
    ".gemini/GEMINI.md",
    ".codex/config.toml",
    ".gemini/settings.json",
    ".cursor/rules.md",
]

REQUIRED_TEXT = [
    ("root-claude-imports-agents", "CLAUDE.md", "@AGENTS.md"),
    ("claude-imports-global", ".claude/CLAUDE.md", "@../ai/rules/agent-user-global.md"),
    ("claude-imports-tool-priority", ".claude/CLAUDE.md", "@../ai/rules/tool-priority.md"),
    (
        "claude-imports-context-compaction",
        ".claude/CLAUDE.md",
        "@../ai/rules/context-and-compaction.md",
    ),
    ("gemini-imports-global", ".gemini/GEMINI.md", "@../ai/rules/agent-user-global.md"),
    ("gemini-imports-tool-priority", ".gemini/GEMINI.md", "@../ai/rules/tool-priority.md"),
    ("cursor-imports-global", ".cursor/rules.md", "@../ai/rules/agent-user-global.md"),
    ("cursor-imports-tool-priority", ".cursor/rules.md", "@../ai/rules/tool-priority.md"),
    (
        "cursor-imports-context-compaction",
        ".cursor/rules.md",
        "@../ai/rules/context-and-compaction.md",
    ),
]


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()


def _ok(rule: str, path: str) -> GuidanceResult:
    return GuidanceResult(rule, path, "ok")


def _fail(rule: str, path: str, message: str) -> GuidanceResult:
    return GuidanceResult(rule, path, "fail", message)


def check_guidance_adapters(root: Path) -> list[GuidanceResult]:
    results: list[GuidanceResult] = []
    for relative in REQUIRED_FILES:
        path = root / relative
        if path.is_file():
            results.append(_ok("required-file", relative))
        else:
            results.append(_fail("required-file", relative, "missing required guidance/config file"))

    for rule, relative, needle in REQUIRED_TEXT:
        path = root / relative
        if not path.is_file():
            results.append(_fail(rule, relative, "file missing"))
            continue
        text = path.read_text(encoding="utf-8")
        if needle in text:
            results.append(_ok(rule, relative))
        else:
            results.append(_fail(rule, relative, f"missing {needle!r}"))

    codex_path = root / ".codex/config.toml"
    if codex_path.is_file():
        try:
            codex = tomllib.loads(codex_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as error:
            results.append(_fail("codex-config-parse", _rel(root, codex_path), str(error)))
        else:
            expected = "~/.dotfiles/ai/rules/agent-user-global.md"
            actual = codex.get("model_instructions_file")
            results.append(
                _ok("codex-loads-global", _rel(root, codex_path))
                if actual == expected
                else _fail("codex-loads-global", _rel(root, codex_path), f"got {actual!r}")
            )
            fallback = codex.get("project_doc_fallback_filenames", [])
            results.append(
                _ok("codex-discovers-agents", _rel(root, codex_path))
                if "AGENTS.md" in fallback
                else _fail("codex-discovers-agents", _rel(root, codex_path), "AGENTS.md missing")
            )

    gemini_path = root / ".gemini/settings.json"
    if gemini_path.is_file():
        try:
            gemini = json.loads(gemini_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            results.append(_fail("gemini-settings-parse", _rel(root, gemini_path), str(error)))
        else:
            filenames = gemini.get("context", {}).get("fileName", [])
            results.append(
                _ok("gemini-discovers-agents", _rel(root, gemini_path))
                if "AGENTS.md" in filenames
                else _fail("gemini-discovers-agents", _rel(root, gemini_path), "AGENTS.md missing")
            )

    return results


def summarize_results(results: Sequence[GuidanceResult]) -> dict[str, object]:
    return {
        "total": len(results),
        "by_status": dict(sorted(Counter(result.status for result in results).items())),
        "by_rule": dict(sorted(Counter(result.rule for result in results).items())),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    results = check_guidance_adapters(args.root.resolve())
    if args.summary:
        print(json.dumps(summarize_results(results), indent=2))
    else:
        print(json.dumps([asdict(result) for result in results], indent=2))
    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
