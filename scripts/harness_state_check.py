#!/usr/bin/env python3
"""Validate whether the repository's legacy coding-agent harness is active or quarantined."""

from __future__ import annotations

import argparse
import json
import shlex
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
    ".gemini",
    ".windsurf",
    "ai",
)
DISABLED_CURSOR_ALLOWED_CHILDREN = {
    "cli-config.json": "file",
    "cursor-statusline": "directory",
}
DISABLED_CURSOR_STATUSLINE_ALLOWED_CHILDREN = {"statusline.sh": "file"}
DISABLED_CLAUDE_ALLOWED_CHILDREN = {
    "claude-statusline": "directory",
    "tdd-guard": "directory",
}
DISABLED_TDD_GUARD_ALLOWED_CHILDREN = {"data": "directory"}
DISABLED_TDD_GUARD_DATA_ALLOWED_CHILDREN = {"test.json": "file"}


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


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"nonstandard JSON constant: {value}")


def _load_strict_json(path: Path) -> object:
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_nonstandard_json_constant,
    )


def _check_allowed_children(
    directory: Path,
    relative: str,
    *,
    allowed: dict[str, str],
    required: frozenset[str],
    rule: str,
    purpose: str,
) -> list[HarnessStateResult]:
    """Validate an exact, lstat-based allowlist for a local non-harness directory."""
    results: list[HarnessStateResult] = []
    seen: set[str] = set()
    for child in sorted(directory.iterdir(), key=lambda path: path.name):
        child_relative = f"{relative}/{child.name}"
        actual = _entry_type(child)
        expected = allowed.get(child.name)
        seen.add(child.name)
        if expected == actual:
            results.append(_result(rule, child_relative, "ok"))
        elif expected is None:
            results.append(
                _result(
                    rule,
                    child_relative,
                    "fail",
                    f"unexpected entry in {purpose}",
                )
            )
        else:
            results.append(
                _result(
                    rule,
                    child_relative,
                    "fail",
                    f"expected real {expected}, found {actual}",
                )
            )

    for name in sorted(required - seen):
        results.append(
            _result(
                rule,
                f"{relative}/{name}",
                "fail",
                f"expected real {allowed[name]}, found missing",
            )
        )
    return results


def _check_disabled_cursor(root: Path) -> list[HarnessStateResult]:
    """Allow only the independently scoped Cursor CLI statusline configuration."""
    cursor = root / ".cursor"
    actual = _entry_type(cursor)
    if actual == "missing":
        return [_result("disabled-cursor-directory", ".cursor", "ok")]
    if actual != "directory":
        return [
            _result(
                "disabled-cursor-directory",
                ".cursor",
                "fail",
                f"expected missing or real local configuration directory, found {actual}",
            )
        ]

    results = [_result("disabled-cursor-directory", ".cursor", "ok")]
    results.extend(
        _check_allowed_children(
            cursor,
            ".cursor",
            allowed=DISABLED_CURSOR_ALLOWED_CHILDREN,
            required=frozenset(DISABLED_CURSOR_ALLOWED_CHILDREN),
            rule="disabled-cursor-allowed-path",
            purpose="the standalone Cursor statusline configuration",
        )
    )
    config = cursor / "cli-config.json"
    if _entry_type(config) == "file":
        mode = config.lstat().st_mode
        if mode & 0o111:
            results.append(
                _result(
                    "disabled-cursor-config",
                    ".cursor/cli-config.json",
                    "fail",
                    "standalone Cursor configuration must not be executable",
                )
            )
        else:
            try:
                parsed = _load_strict_json(config)
            except (OSError, UnicodeDecodeError, ValueError):
                results.append(
                    _result(
                        "disabled-cursor-config",
                        ".cursor/cli-config.json",
                        "fail",
                        "standalone Cursor configuration must be strict JSON",
                    )
                )
            else:
                expected_script = (cursor / "cursor-statusline/statusline.sh").absolute()
                permissions = parsed.get("permissions") if isinstance(parsed, dict) else None
                status_line = parsed.get("statusLine") if isinstance(parsed, dict) else None
                command = status_line.get("command") if isinstance(status_line, dict) else None
                command_target: Path | None = None
                command_parts: list[str] = []
                try:
                    if isinstance(command, str):
                        command_parts = shlex.split(command)
                        if len(command_parts) == 1:
                            command_target = Path(command_parts[0]).expanduser().absolute()
                except (RuntimeError, ValueError):
                    pass
                valid = (
                    isinstance(parsed, dict)
                    and set(parsed) == {"permissions", "statusLine"}
                    and isinstance(permissions, dict)
                    and set(permissions) == {"allow", "deny"}
                    and permissions["allow"] == []
                    and permissions["deny"] == []
                    and isinstance(status_line, dict)
                    and set(status_line) == {
                        "type",
                        "command",
                        "padding",
                        "updateIntervalMs",
                        "timeoutMs",
                    }
                    and status_line["type"] == "command"
                    and len(command_parts) == 1
                    and command_target == expected_script
                    and type(status_line["padding"]) is int
                    and status_line["padding"] >= 0
                    and type(status_line["updateIntervalMs"]) is int
                    and status_line["updateIntervalMs"] > 0
                    and type(status_line["timeoutMs"]) is int
                    and status_line["timeoutMs"] > 0
                )
                results.append(
                    _result(
                        "disabled-cursor-config",
                        ".cursor/cli-config.json",
                        "ok" if valid else "fail",
                        "" if valid else "unexpected standalone Cursor configuration",
                    )
                )
    statusline = cursor / "cursor-statusline"
    if _entry_type(statusline) == "directory":
        results.extend(
            _check_allowed_children(
                statusline,
                ".cursor/cursor-statusline",
                allowed=DISABLED_CURSOR_STATUSLINE_ALLOWED_CHILDREN,
                required=frozenset({"statusline.sh"}),
                rule="disabled-cursor-statusline-path",
                purpose="the standalone Cursor statusline configuration",
            )
        )
        script = statusline / "statusline.sh"
        if _entry_type(script) == "file":
            status = "ok" if script.lstat().st_mode & 0o111 else "fail"
            results.append(
                _result(
                    "disabled-cursor-statusline-script",
                    ".cursor/cursor-statusline/statusline.sh",
                    status,
                    "" if status == "ok" else "statusline script must be executable",
                )
            )
    return results


def _check_tdd_guard_data(tdd_guard: Path) -> list[HarnessStateResult]:
    """Allow only the ignored TDD-Guard test-results cache, never active hook files."""
    results = _check_allowed_children(
        tdd_guard,
        ".claude/tdd-guard",
        allowed=DISABLED_TDD_GUARD_ALLOWED_CHILDREN,
        required=frozenset({"data"}),
        rule="disabled-tdd-guard-path",
        purpose="the ignored TDD-Guard test-results cache",
    )
    data = tdd_guard / "data"
    if _entry_type(data) == "directory":
        results.extend(
            _check_allowed_children(
                data,
                ".claude/tdd-guard/data",
                allowed=DISABLED_TDD_GUARD_DATA_ALLOWED_CHILDREN,
                required=frozenset({"test.json"}),
                rule="disabled-tdd-guard-data-path",
                purpose="the ignored TDD-Guard test-results cache",
            )
        )
        test_results = data / "test.json"
        if _entry_type(test_results) == "file":
            mode = test_results.lstat().st_mode
            if mode & 0o111:
                results.append(
                    _result(
                        "disabled-tdd-guard-results-data",
                        ".claude/tdd-guard/data/test.json",
                        "fail",
                        "test-results data must not be executable",
                    )
                )
            else:
                try:
                    parsed = _load_strict_json(test_results)
                except (OSError, UnicodeDecodeError, ValueError):
                    results.append(
                        _result(
                            "disabled-tdd-guard-results-data",
                            ".claude/tdd-guard/data/test.json",
                            "fail",
                            "test-results data must be valid JSON",
                        )
                    )
                else:
                    status = "ok" if isinstance(parsed, dict) else "fail"
                    message = "" if status == "ok" else "test-results data must be a JSON object"
                    results.append(
                        _result(
                            "disabled-tdd-guard-results-data",
                            ".claude/tdd-guard/data/test.json",
                            status,
                            message,
                        )
                    )
    return results


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

    results.extend(_check_disabled_cursor(root))

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
            expected = DISABLED_CLAUDE_ALLOWED_CHILDREN.get(child.name)
            actual = _entry_type(child)
            if expected == actual:
                results.append(_result("disabled-claude-allowed-path", relative, "ok"))
                if child.name == "tdd-guard":
                    results.extend(_check_tdd_guard_data(child))
            else:
                results.append(
                    _result(
                        "disabled-claude-allowed-path",
                    relative,
                    "fail",
                    "only the restored statusline and exact ignored TDD-Guard test cache may remain active",
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
