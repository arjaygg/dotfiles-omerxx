#!/usr/bin/env python3
"""Measure effective, always-loaded guidance chains without changing any files."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any, Iterable


METRICS = ("lines", "words", "bytes")
IMPORT_LINE = re.compile(r"^\s*@([^\s#]+)\s*$", re.MULTILINE)


def _label(root: Path, path: Path) -> str:
    """Return a report-safe path label relative to root."""

    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return "<outside-root>"


def _inside(root: Path, path: Path) -> Path | None:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


class _Resolver:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.files: list[Path] = []
        self._seen: set[Path] = set()
        self.missing: list[str] = []
        self.cycles: list[list[str]] = []
        self.outside_root: list[str] = []
        self.invalid: list[str] = []

    @staticmethod
    def _append_once(items: list[str], value: str) -> None:
        if value not in items:
            items.append(value)

    def visit(self, path: Path, stack: tuple[Path, ...] = ()) -> None:
        safe_path = _inside(self.root, path)
        if safe_path is None:
            self._append_once(self.outside_root, "<outside-root>")
            return
            return
        label = _label(self.root, safe_path)
        if safe_path in stack:
            start = stack.index(safe_path)
            cycle = [_label(self.root, item) for item in stack[start:]] + [label]
            if cycle not in self.cycles:
                self.cycles.append(cycle)
            return
        if safe_path in self._seen:
            return
        if not safe_path.is_file():
            self._append_once(self.missing, label)
            return

        self._seen.add(safe_path)
        self.files.append(safe_path)
        try:
            text = safe_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            self._append_once(self.invalid, label)
            return

        next_stack = stack + (safe_path,)
        for imported in IMPORT_LINE.findall(text):
            self.visit(safe_path.parent / imported, next_stack)

    def result(self) -> dict[str, Any]:
        return {
            "files": [_label(self.root, path) for path in self.files],
            "missing": list(self.missing),
            "cycles": [list(cycle) for cycle in self.cycles],
            "outside_root": list(self.outside_root),
            "invalid": list(self.invalid),
        }


def resolve_markdown_chain(root: Path, entry: Path) -> dict[str, Any]:
    """Resolve one markdown entrypoint and its line-oriented ``@`` imports."""

    resolver = _Resolver(root)
    resolver.visit((root / entry) if not entry.is_absolute() else entry)
    return resolver.result()


def _resolve_entries(root: Path, entries: Iterable[Path]) -> dict[str, Any]:
    resolver = _Resolver(root)
    for entry in entries:
        resolver.visit((root / entry) if not entry.is_absolute() else entry)
    return resolver.result()


def _measure(root: Path, labels: Iterable[str]) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    measurements: list[dict[str, Any]] = []
    totals = {metric: 0 for metric in METRICS}
    invalid: list[str] = []
    for label in labels:
        path = root / label
        try:
            content = path.read_bytes()
            text = content.decode("utf-8")
        except (OSError, UnicodeError):
            invalid.append(label)
            continue
        measurement = {
            "path": label,
            "lines": len(text.splitlines()),
            "words": len(text.split()),
            "bytes": len(content),
        }
        measurements.append(measurement)
        for metric in METRICS:
            totals[metric] += measurement[metric]
    return measurements, totals, invalid


def _path_from_config(root: Path, value: str) -> Path | None:
    if value.startswith("~/.dotfiles/"):
        return root / value.removeprefix("~/.dotfiles/")
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def _codex_entries(root: Path, issues: list[str]) -> list[Path]:
    config_path = root / "ai/config/codex/config.base.toml"
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        issues.append(f"codex config: {error}")
        return [Path("ai/rules/agent-user-global.md"), Path("AGENTS.md")]

    entries: list[Path] = []
    instructions = config.get("model_instructions_file")
    if isinstance(instructions, str):
        path = _path_from_config(root, instructions)
        if path is not None:
            entries.append(path)
    else:
        issues.append("codex config: model_instructions_file is missing or not a string")

    fallback = config.get("project_doc_fallback_filenames", [])
    if not isinstance(fallback, list) or not all(isinstance(item, str) for item in fallback):
        issues.append("codex config: project_doc_fallback_filenames must be a string array")
    else:
        entries.extend(_path_from_config(root, item) for item in fallback if _path_from_config(root, item) is not None)
    return entries


def _gemini_entries(root: Path, issues: list[str]) -> list[Path]:
    config_path = root / ".gemini/settings.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        issues.append(f"gemini config: {error}")
        return [Path("AGENTS.md")]

    context = config.get("context", {}) if isinstance(config, dict) else {}
    filenames = context.get("fileName", []) if isinstance(context, dict) else []
    if isinstance(filenames, str):
        filenames = [filenames]
    if not isinstance(filenames, list) or not all(isinstance(item, str) for item in filenames):
        issues.append("gemini config: context.fileName must be a string or string array")
        return [Path("AGENTS.md")]
    return [Path(item) for item in filenames] or [Path("AGENTS.md")]


def _summary(root: Path, resolution: dict[str, Any]) -> dict[str, Any]:
    measurements, totals, invalid = _measure(root, resolution["files"])
    resolution = dict(resolution)
    resolution["invalid"] = sorted(set(resolution["invalid"]) | set(invalid))
    resolution["measurements"] = measurements
    resolution["metrics"] = totals
    return resolution


def build_report(root: Path) -> dict[str, Any]:
    """Build a deterministic report for repository, Claude, Codex, and Gemini chains."""

    root = root.resolve()
    config_issues: list[str] = []
    entry_sets = {
        "repository": [Path("AGENTS.md")],
        "claude": [Path("CLAUDE.md")],
        "codex": _codex_entries(root, config_issues),
        "gemini": _gemini_entries(root, config_issues),
    }
    clients = {
        name: _summary(root, _resolve_entries(root, entries))
        for name, entries in entry_sets.items()
    }

    unique_files = sorted({path for summary in clients.values() for path in summary["files"]})
    _, aggregate_metrics, aggregate_invalid = _measure(root, unique_files)
    aggregate = {
        "files": unique_files,
        "metrics": aggregate_metrics,
        "invalid": aggregate_invalid,
    }
    return {
        "schema": 1,
        "root": ".",
        "clients": clients,
        "aggregate": aggregate,
        "config_issues": config_issues,
        "budget_violations": [],
    }


def _budget_violations(report: dict[str, Any], limits: dict[str, int | None]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    scopes = [(f"client:{name}", summary["metrics"]) for name, summary in report["clients"].items()]
    scopes.append(("aggregate", report["aggregate"]["metrics"]))
    for scope, metrics in scopes:
        for metric in METRICS:
            limit = limits[metric]
            if limit is not None and metrics[metric] > limit:
                violations.append({"scope": scope, "metric": metric, "actual": metrics[metric], "limit": limit})
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--max-lines", type=int)
    parser.add_argument("--max-words", type=int)
    parser.add_argument("--max-bytes", type=int)
    args = parser.parse_args(argv)
    try:
        report = build_report(args.root)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"effective context rejected input: {error}", file=sys.stderr)
        return 2
    report["budget_violations"] = _budget_violations(
        report,
        {"lines": args.max_lines, "words": args.max_words, "bytes": args.max_bytes},
    )
    print(json.dumps(report, indent=2))
    return 1 if report["budget_violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
