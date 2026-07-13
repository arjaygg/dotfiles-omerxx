#!/usr/bin/env python3
"""Build deterministic, proposal-only configuration bundles for every client."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

try:
    from scripts.config_generate import (
        TemplateValidationError,
        _parse_variables,
        deep_merge,
        expand_placeholders,
    )
    from scripts.public_hygiene_check import scan_text
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.config_generate import (
        TemplateValidationError,
        _parse_variables,
        deep_merge,
        expand_placeholders,
    )
    from scripts.public_hygiene_check import scan_text


_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
SUPPORTED_FORMATS = frozenset({"json", "toml"})


def _safe_path(root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise TemplateValidationError(f"manifest path must remain inside root: {value}")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise TemplateValidationError(f"manifest path escapes root: {value}") from error
    return resolved


def _load_manifest(root: Path) -> list[dict[str, str]]:
    path = root / "ai/config/manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise TemplateValidationError(f"invalid config manifest: {error}") from error
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise TemplateValidationError("config manifest version must be 1")
    clients = manifest.get("clients")
    if not isinstance(clients, list):
        raise TemplateValidationError("config manifest clients must be an array")
    normalized: list[dict[str, str]] = []
    for index, client in enumerate(clients):
        if not isinstance(client, dict) or not all(isinstance(client.get(key), str) for key in ("name", "format", "base", "runtime")):
            raise TemplateValidationError(f"manifest client {index} has invalid required fields")
        if client["format"] not in SUPPORTED_FORMATS:
            raise TemplateValidationError(f"manifest client {client['name']} has unsupported format")
        normalized.append({key: client[key] for key in ("name", "format", "base", "runtime")})
    return normalized


def _load_document(path: Path, kind: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    findings = scan_text(path.as_posix(), text)
    if findings:
        summary = ", ".join(f"{finding.rule}@{finding.line}" for finding in findings)
        raise TemplateValidationError(f"{path}: non-portable findings: {summary}")
    try:
        value = json.loads(text) if kind == "json" else tomllib.loads(text)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        raise TemplateValidationError(f"{path}: invalid {kind}: {error}") from error
    if not isinstance(value, dict):
        raise TemplateValidationError(f"{path}: root must be an object/table")
    return value


def _toml_key(value: str) -> str:
    return value if _KEY.fullmatch(value) else json.dumps(value)


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        if any(isinstance(item, dict) for item in value):
            raise TemplateValidationError("TOML arrays of tables are not supported by the proposal renderer")
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TemplateValidationError(f"unsupported TOML value: {type(value).__name__}")


def _render_toml_table(value: dict[str, Any], prefix: tuple[str, ...] = ()) -> list[str]:
    lines: list[str] = []
    scalars = {key: child for key, child in value.items() if not isinstance(child, dict)}
    tables = {key: child for key, child in value.items() if isinstance(child, dict)}
    if prefix:
        lines.append("[" + ".".join(_toml_key(part) for part in prefix) + "]")
    for key in sorted(scalars):
        lines.append(f"{_toml_key(key)} = {_toml_value(scalars[key])}")
    for key in sorted(tables):
        if lines:
            lines.append("")
        lines.extend(_render_toml_table(tables[key], prefix + (key,)))
    return lines


def _render(value: dict[str, Any], kind: str) -> str:
    if kind == "json":
        return json.dumps(value, indent=2, sort_keys=True) + "\n"
    rendered = "\n".join(_render_toml_table(value)) + "\n"
    try:
        tomllib.loads(rendered)
    except tomllib.TOMLDecodeError as error:
        raise TemplateValidationError(f"rendered TOML is invalid: {error}") from error
    return rendered


def build_proposals(
    root: Path,
    *,
    clients: set[str] | None = None,
    overlay_dir: Path | None = None,
    variables: dict[str, str] | None = None,
) -> dict[str, dict[str, str]]:
    """Return client proposals without writing bases, overlays, or runtime files."""

    root = root.resolve()
    selected = clients
    proposals: dict[str, dict[str, str]] = {}
    for client in _load_manifest(root):
        if selected is not None and client["name"] not in selected:
            continue
        kind = client["format"]
        base_path = _safe_path(root, client["base"])
        merged = _load_document(base_path, kind)
        if overlay_dir is not None:
            overlay_path = overlay_dir.expanduser() / f"{client['name']}.overlay.{kind}"
            if overlay_path.is_file():
                merged = deep_merge(merged, _load_document(overlay_path, kind))
        rendered = _render(expand_placeholders(copy.deepcopy(merged), variables or {}), kind)
        findings = scan_text(f"<proposal:{client['name']}>", rendered)
        if findings:
            summary = ", ".join(f"{finding.rule}@{finding.line}" for finding in findings)
            raise TemplateValidationError(f"proposal {client['name']}: non-portable findings: {summary}")
        proposals[client["name"]] = {
            "format": kind,
            "runtime": client["runtime"],
            "content": rendered,
        }
    if selected is not None:
        missing = selected - proposals.keys()
        if missing:
            raise TemplateValidationError(f"unknown manifest clients: {', '.join(sorted(missing))}")
    return proposals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--client", action="append", dest="clients")
    parser.add_argument("--overlay-dir", type=Path)
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    args = parser.parse_args(argv)
    try:
        bundle = build_proposals(
            args.root,
            clients=set(args.clients) if args.clients else None,
            overlay_dir=args.overlay_dir,
            variables=_parse_variables(args.set),
        )
        print(json.dumps({"proposals": bundle}, indent=2, sort_keys=True))
    except (OSError, UnicodeError, TemplateValidationError) as error:
        print(f"config proposals rejected: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
