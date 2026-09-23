#!/usr/bin/env python3
"""Validate whether the repository's legacy coding-agent harness is active or quarantined."""

from __future__ import annotations

import argparse
import json
import stat
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


DISABLED_SENTINELS = (
    "README.txt",
    "repo/ai/config/manifest.json",
    "repo/.claude/CLAUDE.md",
    "repo/.claude/hooks/pre-tool-gate-v2.sh",
    "repo/.codex/config.toml",
    "repo/.gemini/settings.json",
    "repo/.cursor/rules.md",
)
ENABLED_REQUIRED_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "ai/config/manifest.json",
    ".claude/CLAUDE.md",
    ".codex/config.toml",
    ".gemini/settings.json",
    ".cursor/rules.md",
)
DISABLED_ABSENT_PATHS = (
    "AGENTS.md",
    "CLAUDE.md",
    ".cursorrules",
    ".windsurfrules",
    ".mcp.json",
    ".mcp.example.json",
    ".claude-global",
    ".codex",
    ".cursor",
    ".gemini",
    ".windsurf",
    "ai",
)
DISABLED_CLAUDE_ALLOWED_CHILDREN = frozenset({"claude-statusline"})


@dataclass(frozen=True)
class HarnessStateResult:
    rule: str
    path: str
    status: str
    message: str = ""


def _entry_type(path: Path) -> str:
    """Return an lstat-based entry type without following a symlink."""
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return "missing"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISDIR(mode):
        return "directory"
    return "other"


def _result(rule: str, path: str, status: str, message: str = "") -> HarnessStateResult:
    return HarnessStateResult(rule, path, status, message)


def _check_file(root: Path, relative: str, rule: str) -> HarnessStateResult:
    actual = _entry_type(root / relative)
    if actual == "file":
        return _result(rule, relative, "ok")
    return _result(rule, relative, "fail", f"expected regular file, found {actual}")


def _check_archived_file(root: Path, relative: str) -> HarnessStateResult:
    parent = root
    for segment in Path(relative).parts[:-1]:
        parent /= segment
        actual = _entry_type(parent)
        if actual != "directory":
            return _result(
                "disabled-archive-directory",
                parent.relative_to(root).as_posix(),
                "fail",
                f"expected real archive directory, found {actual}",
            )
    return _check_file(root, relative, "disabled-archive-sentinel")


def _check_enabled(root: Path) -> tuple[str, list[HarnessStateResult]]:
    results = [
        _check_file(root, relative, "enabled-required-file")
        for relative in ENABLED_REQUIRED_FILES
    ]
    state = "enabled" if all(result.status == "ok" for result in results) else "inconsistent"
    return state, results


def _check_disabled(root: Path) -> tuple[str, list[HarnessStateResult]]:
    results: list[HarnessStateResult] = []
    marker = root / ".harness-disabled"
    if _entry_type(marker) != "directory":
        return "inconsistent", [
            _result(
                "disabled-marker",
                ".harness-disabled",
                "fail",
                "expected a real quarantine directory",
            )
        ]

    results.append(_result("disabled-marker", ".harness-disabled", "ok"))
    for relative in DISABLED_SENTINELS:
        results.append(_check_archived_file(marker, relative))

    readme = marker / "README.txt"
    if _entry_type(readme) == "file":
        text = readme.read_text(encoding="utf-8")
        if "AI coding-agent harness disabled." in text and "ai-harness-toggle.sh enable" in text:
            results.append(_result("disabled-readme", ".harness-disabled/README.txt", "ok"))
        else:
            results.append(
                _result(
                    "disabled-readme",
                    ".harness-disabled/README.txt",
                    "fail",
                    "missing the quarantine and explicit restore guidance",
                )
            )

    for relative in DISABLED_ABSENT_PATHS:
        actual = _entry_type(root / relative)
        if actual == "missing":
            results.append(_result("disabled-absent-path", relative, "ok"))
        else:
            results.append(
                _result(
                    "disabled-absent-path",
                    relative,
                    "fail",
                    f"quarantined path is active as {actual}",
                )
            )

    claude = root / ".claude"
    claude_type = _entry_type(claude)
    if claude_type != "directory":
        results.append(
            _result(
                "disabled-claude-directory",
                ".claude",
                "fail",
                f"expected restored statusline directory, found {claude_type}",
            )
        )
    else:
        statusline = claude / "claude-statusline"
        if _entry_type(statusline) != "directory":
            results.append(
                _result(
                    "disabled-claude-allowed-path",
                    ".claude/claude-statusline",
                    "fail",
                    "expected the separately restored statusline directory",
                )
            )
        for child in sorted(claude.iterdir(), key=lambda path: path.name):
            relative = f".claude/{child.name}"
            if child.name in DISABLED_CLAUDE_ALLOWED_CHILDREN and _entry_type(child) == "directory":
                results.append(_result("disabled-claude-allowed-path", relative, "ok"))
            else:
                results.append(
                    _result(
                        "disabled-claude-allowed-path",
                        relative,
                        "fail",
                        "only the restored claude-statusline directory may remain active",
                    )
                )

    state = "disabled" if all(result.status == "ok" for result in results) else "inconsistent"
    return state, results


def check_harness_state(root: Path) -> tuple[str, list[HarnessStateResult]]:
    """Return the valid harness state and checks for a repository root."""
    marker_type = _entry_type(root / ".harness-disabled")
    if marker_type == "missing":
        return _check_enabled(root)
    return _check_disabled(root)


def summarize_results(state: str, results: Sequence[HarnessStateResult]) -> dict[str, object]:
    return {
        "state": state,
        "total": len(results),
        "by_status": dict(sorted(Counter(result.status for result in results).items())),
        "by_rule": dict(sorted(Counter(result.rule for result in results).items())),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)

    state, results = check_harness_state(args.root.resolve())
    if args.summary:
        print(json.dumps(summarize_results(state, results), indent=2))
    else:
        print(json.dumps([asdict(result) for result in results], indent=2))

    success = state in {"enabled", "disabled"}
    if success and args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"state={state}\n")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
