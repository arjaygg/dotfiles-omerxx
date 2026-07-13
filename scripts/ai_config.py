#!/usr/bin/env python3
"""Read-only generate, diff, and doctor commands for portable AI configuration."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any

try:
    from scripts.config_doctor import run_doctor
    from scripts.config_generate import TemplateValidationError, _flatten, _parse_variables
    from scripts.config_generate_all import build_proposals
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.config_doctor import run_doctor
    from scripts.config_generate import TemplateValidationError, _flatten, _parse_variables
    from scripts.config_generate_all import build_proposals


def _runtime_path(runtime_root: Path, runtime: str) -> Path:
    if not runtime.startswith("~/"):
        raise TemplateValidationError(f"manifest runtime must use ~/ portability form: {runtime}")
    relative = Path(runtime[2:])
    if relative.is_absolute() or ".." in relative.parts:
        raise TemplateValidationError(f"manifest runtime escapes its root: {runtime}")
    return runtime_root.resolve() / relative


def _parse_rendered(content: str, kind: str) -> dict[str, Any]:
    value = json.loads(content) if kind == "json" else tomllib.loads(content)
    if not isinstance(value, dict):
        raise TemplateValidationError(f"rendered {kind} proposal must be an object/table")
    return value


def compare_proposals(
    root: Path,
    runtime_root: Path,
    *,
    clients: set[str] | None = None,
    overlay_dir: Path | None = None,
    variables: dict[str, str] | None = None,
) -> dict[str, dict[str, object]]:
    """Compare proposals with explicit runtime files without emitting target content."""

    proposals = build_proposals(
        root,
        clients=clients,
        overlay_dir=overlay_dir,
        variables=variables,
    )
    results: dict[str, dict[str, object]] = {}
    for name, proposal in proposals.items():
        target_path = _runtime_path(runtime_root, proposal["runtime"])
        proposal_bytes = proposal["content"].encode("utf-8")
        result: dict[str, object] = {
            "format": proposal["format"],
            "runtime": proposal["runtime"],
            "proposal_sha256": hashlib.sha256(proposal_bytes).hexdigest(),
            "changed_paths": [],
        }
        if not target_path.is_file():
            result["status"] = "missing"
            results[name] = result
            continue
        target_bytes = target_path.read_bytes()
        result["target_sha256"] = hashlib.sha256(target_bytes).hexdigest()
        try:
            proposal_value = _parse_rendered(proposal["content"], proposal["format"])
            target_text = target_bytes.decode("utf-8")
            target_value = _parse_rendered(target_text, proposal["format"])
        except (UnicodeError, json.JSONDecodeError, tomllib.TOMLDecodeError, TemplateValidationError) as error:
            result["status"] = "invalid-target"
            result["error"] = str(error)
            results[name] = result
            continue
        proposal_values = _flatten(proposal_value)
        target_values = _flatten(target_value)
        changed_paths = sorted(
            path
            for path in proposal_values.keys() | target_values.keys()
            if proposal_values.get(path) != target_values.get(path)
        )
        result["changed_paths"] = changed_paths
        result["status"] = "drift" if changed_paths else "match"
        results[name] = result
    return results


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _write_temporary(path: Path, content: str) -> Path:
    """Write and fsync a same-directory temporary file without replacing a target."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        return Path(temporary)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def stage_proposals(
    root: Path,
    output_root: Path,
    *,
    clients: set[str] | None = None,
    overlay_dir: Path | None = None,
    variables: dict[str, str] | None = None,
    replace: bool = False,
) -> dict[str, list[str]]:
    """Atomically write proposals below an explicitly marked staging root."""

    output_root = output_root.expanduser().resolve()
    if not (output_root / ".ai-config-staging").is_file():
        raise TemplateValidationError("staging root must contain a .ai-config-staging marker file")
    proposals = build_proposals(
        root,
        clients=clients,
        overlay_dir=overlay_dir,
        variables=variables,
    )
    targets = {
        name: (_runtime_path(output_root, proposal["runtime"]), proposal["content"])
        for name, proposal in proposals.items()
    }
    existed_before = {str(target): target.exists() for target, _content in targets.values()}
    backups: dict[str, Path] = {}
    temporary_paths: dict[str, Path] = {}
    replaced: list[Path] = []
    for target, _content in targets.values():
        if target.exists() and not replace:
            raise TemplateValidationError(f"staging target exists; pass --replace explicitly: {target}")
        backup = target.with_name(target.name + ".bak")
        if target.exists() and backup.exists():
            raise TemplateValidationError(f"staging backup already exists; refusing to overwrite: {backup}")
        if target.exists():
            backups[str(target)] = backup

    try:
        for target, content in targets.values():
            temporary_paths[str(target)] = _write_temporary(target, content)
        for target, _content in targets.values():
            if target.exists() != existed_before[str(target)]:
                raise TemplateValidationError(f"staging target changed during preflight: {target}")
            if target.exists():
                shutil.copy2(target, backups[str(target)])
        for target, _content in targets.values():
            os.replace(temporary_paths[str(target)], target)
            replaced.append(target)
    except BaseException:
        for target in reversed(replaced):
            backup = backups.get(str(target))
            if backup is not None:
                shutil.copy2(backup, target)
            else:
                target.unlink(missing_ok=True)
        for backup in backups.values():
            backup.unlink(missing_ok=True)
        raise
    finally:
        for temporary in temporary_paths.values():
            temporary.unlink(missing_ok=True)
    return {
        "written": [str(target) for target, _content in targets.values()],
        "backups": [str(backups[str(target)]) for target, _content in targets.values() if str(target) in backups],
    }


def _add_proposal_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--client", action="append", dest="clients")
    parser.add_argument("--overlay-dir", type=Path)
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="emit proposal content")
    _add_proposal_args(generate)

    diff = subparsers.add_parser("diff", help="report drift without target content")
    _add_proposal_args(diff)
    diff.add_argument("--runtime-root", type=Path, required=True)

    stage = subparsers.add_parser("stage", help="atomically write below a marked staging root")
    _add_proposal_args(stage)
    stage.add_argument("--output-root", type=Path, required=True)
    stage.add_argument("--replace", action="store_true")

    doctor = subparsers.add_parser("doctor", help="emit the read-only configuration report")
    doctor.add_argument("--root", type=Path, default=Path.cwd())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "doctor":
            issues = run_doctor(args.root.resolve())
            print(json.dumps([asdict(issue) for issue in issues], indent=2))
            return 1 if issues else 0
        variables = _parse_variables(args.set)
        clients = set(args.clients) if args.clients else None
        if args.command == "generate":
            print(
                json.dumps(
                    {
                        "proposals": build_proposals(
                            args.root,
                            clients=clients,
                            overlay_dir=args.overlay_dir,
                            variables=variables,
                        )
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "stage":
            result = stage_proposals(
                args.root,
                args.output_root,
                clients=clients,
                overlay_dir=args.overlay_dir,
                variables=variables,
                replace=args.replace,
            )
            print(json.dumps({"stage": result}, indent=2, sort_keys=True))
            return 0
        result = compare_proposals(
            args.root,
            args.runtime_root,
            clients=clients,
            overlay_dir=args.overlay_dir,
            variables=variables,
        )
        print(json.dumps({"diff": result}, indent=2, sort_keys=True))
        return 1 if any(item["status"] != "match" for item in result.values()) else 0
    except (OSError, UnicodeError, json.JSONDecodeError, tomllib.TOMLDecodeError, TemplateValidationError) as error:
        print(f"ai-config rejected request: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
