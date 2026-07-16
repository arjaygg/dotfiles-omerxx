#!/usr/bin/env python3
"""Parse tracked config/policy files with available syntax parsers."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence


try:
    import yaml  # type: ignore[import-untyped]
except ModuleNotFoundError:  # pragma: no cover - depends on local environment
    yaml = None  # type: ignore[assignment]


@dataclass(frozen=True)
class SyntaxResult:
    path: str
    kind: str
    status: str
    message: str = ""


def _parse_json(text: str) -> None:
    json.loads(text)


def _parse_toml(text: str) -> None:
    tomllib.loads(text)


def _parse_yaml(text: str) -> None:
    if yaml is None:
        raise RuntimeError("yaml parser unavailable")
    yaml.safe_load(text)


PARSERS: dict[str, Callable[[str], None]] = {
    "json": _parse_json,
    "toml": _parse_toml,
    "yaml": _parse_yaml,
}


def candidate_files(root: Path) -> list[tuple[Path, str]]:
    candidates: list[tuple[Path, str]] = []
    for path in [
        root / ".claude/settings.json",
        root / ".github/workflows/claude-auto-gates.yml",
        root / "ai/config/manifest.json",
    ]:
        if path.is_file():
            candidates.append((path, "yaml" if path.suffix in {".yml", ".yaml"} else "json"))
    manifest = root / "ai/config/manifest.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        for client in data.get("clients", []):
            base = root / str(client["base"])
            if base.is_file():
                candidates.append((base, str(client["format"])))
    return sorted(set(candidates), key=lambda item: item[0].as_posix())


def check_syntax(root: Path, files: Sequence[tuple[Path, str]] | None = None) -> list[SyntaxResult]:
    results: list[SyntaxResult] = []
    for path, kind in files or candidate_files(root):
        relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        parser = PARSERS.get(kind)
        if parser is None:
            results.append(SyntaxResult(relative, kind, "unsupported-kind"))
            continue
        try:
            parser(path.read_text(encoding="utf-8"))
        except RuntimeError as error:
            results.append(SyntaxResult(relative, kind, "parser-unavailable", str(error)))
        except (OSError, UnicodeError, json.JSONDecodeError, tomllib.TOMLDecodeError, Exception) as error:
            if kind == "yaml" and yaml is not None:
                # PyYAML raises classes not available without importing its concrete exception type.
                results.append(SyntaxResult(relative, kind, "invalid", str(error)))
            elif not isinstance(error, RuntimeError):
                results.append(SyntaxResult(relative, kind, "invalid", str(error)))
        else:
            results.append(SyntaxResult(relative, kind, "ok"))
    return results


def summarize_results(results: Sequence[SyntaxResult]) -> dict[str, object]:
    return {
        "total": len(results),
        "by_kind": dict(sorted(Counter(result.kind for result in results).items())),
        "by_status": dict(sorted(Counter(result.status for result in results).items())),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    results = check_syntax(args.root.resolve())
    if args.summary:
        print(json.dumps(summarize_results(results), indent=2))
    else:
        print(json.dumps([asdict(result) for result in results], indent=2))
    return 1 if any(result.status in {"invalid", "unsupported-kind"} for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
