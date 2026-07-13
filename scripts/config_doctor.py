#!/usr/bin/env python3
"""Validate tracked AI client configuration without changing any files."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from scripts.public_hygiene_check import Finding, scan_text


CONFIG_SPECS: tuple[tuple[str, str], ...] = (
    (".claude/settings.json", "json"),
    (".codex/config.toml", "toml"),
    (".gemini/settings.json", "json"),
    (".gemini/mcp.json", "json"),
    (".cursor/cli-config.json", "json"),
    (".windsurf/mcp_config.json", "json"),
    ("mcp.json", "json"),
)


@dataclass(frozen=True)
class Issue:
    path: str
    rule: str
    severity: str
    message: str


def _issue_from_finding(finding: Finding) -> Issue:
    severity = "error" if finding.rule in {"secret-assignment", "private-key"} else "warning"
    return Issue(
        finding.path,
        finding.rule,
        severity,
        f"line {finding.line}: {finding.excerpt}",
    )


def _parse_config(text: str, kind: str) -> object:
    if kind == "json":
        return json.loads(text)
    if kind == "toml":
        return tomllib.loads(text)
    raise ValueError(f"unsupported config kind: {kind}")


def compare_runtime_file(source: Path, runtime: Path) -> list[Issue]:
    """Report source/runtime drift without copying either file."""

    try:
        source_bytes = source.read_bytes()
        runtime_bytes = runtime.read_bytes()
    except FileNotFoundError as error:
        return [Issue(str(runtime), "runtime-missing", "warning", str(error))]
    except OSError as error:
        return [Issue(str(runtime), "runtime-unreadable", "error", str(error))]
    if source_bytes == runtime_bytes:
        return []
    return [
        Issue(
            str(runtime),
            "runtime-drift",
            "warning",
            f"runtime differs from tracked source {source}; review before applying either side",
        )
    ]


def run_doctor(root: Path) -> list[Issue]:
    """Return configuration issues; never writes to ``root``."""

    issues: list[Issue] = []
    for relative_path, kind in CONFIG_SPECS:
        path = root / relative_path
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            issues.append(Issue(relative_path, "unreadable-config", "error", str(error)))
            continue
        try:
            parsed = _parse_config(text, kind)
        except (tomllib.TOMLDecodeError, json.JSONDecodeError, ValueError) as error:
            issues.append(Issue(relative_path, "invalid-config", "error", str(error)))
            continue

        issues.extend(_issue_from_finding(finding) for finding in scan_text(relative_path, text))
        if relative_path == ".claude/settings.json" and isinstance(parsed, dict):
            if parsed.get("skipDangerousModePermissionPrompt") is True:
                issues.append(
                    Issue(
                        relative_path,
                        "unsafe-bypass",
                        "error",
                        "skipDangerousModePermissionPrompt must not be enabled in tracked source",
                    )
                )

    guard_path = root / ".claude/hooks/settings-symlink-guard.sh"
    if guard_path.is_file():
        try:
            guard_text = guard_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            issues.append(Issue(str(guard_path.relative_to(root)), "unreadable-hook", "error", str(error)))
        else:
            if 'cp "$LIVE" "$SRC"' in guard_text:
                issues.append(
                    Issue(
                        ".claude/hooks/settings-symlink-guard.sh",
                        "runtime-copyback",
                        "error",
                        "live settings are copied back into tracked source",
                    )
                )
    return issues


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--live-settings", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.root.resolve()
    issues = run_doctor(root)
    if args.live_settings:
        issues.extend(compare_runtime_file(root / ".claude/settings.json", args.live_settings))
    if args.as_json:
        print(json.dumps([asdict(issue) for issue in issues], indent=2))
    else:
        for issue in issues:
            print(f"[{issue.severity}] {issue.path}: {issue.rule}: {issue.message}")
        if not issues:
            print("config doctor passed")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
