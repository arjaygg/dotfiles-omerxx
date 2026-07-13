#!/usr/bin/env python3
"""Prove deterministic all-client generation and isolated staging without live writes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

try:
    from scripts.ai_config import stage_proposals
    from scripts.config_generate import TemplateValidationError, _parse_variables
    from scripts.config_generate_all import build_proposals
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.ai_config import stage_proposals
    from scripts.config_generate import TemplateValidationError, _parse_variables
    from scripts.config_generate_all import build_proposals


DEFAULT_VARIABLES = {
    "PCTX_CONFIG": "~/.config/pctx/pctx.json",
    "USER_NAME": "portable-user",
}


def verify_bootstrap(root: Path, *, variables: dict[str, str] | None = None) -> dict[str, object]:
    """Prove deterministic generation and isolated staging without live writes."""

    root = root.resolve()
    values = dict(DEFAULT_VARIABLES if variables is None else variables)
    first = build_proposals(root, variables=values)
    second = build_proposals(root, variables=values)
    clients: dict[str, dict[str, object]] = {}
    for name in sorted(first):
        proposal = first[name]
        content = proposal["content"].encode("utf-8")
        clients[name] = {
            "format": proposal["format"],
            "runtime": proposal["runtime"],
            "proposal_sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        }
    with tempfile.TemporaryDirectory(prefix="ai-bootstrap-") as directory:
        staging_root = Path(directory)
        (staging_root / ".ai-config-staging").touch()
        cache_files = {
            staging_root / ".codex/cache/bootstrap-cache": b"codex-cache",
            staging_root / ".gemini/cache/bootstrap-cache": b"gemini-cache",
        }
        for cache_path, content in cache_files.items():
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(content)
        first_stage = stage_proposals(root, staging_root, variables=values)
        first_hashes = {
            path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in first_stage["written"]
        }
        second_stage = stage_proposals(root, staging_root, variables=values, replace=True)
        second_hashes = {
            path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in second_stage["written"]
        }
        staged_cache_preserved = all(
            cache_path.read_bytes() == content for cache_path, content in cache_files.items()
        )
    return {
        "schema": 1,
        "root": ".",
        "client_count": len(clients),
        "clients": clients,
        "variable_names": sorted(values),
        "idempotent": first == second,
        "staged_client_count": len(first_stage["written"]),
        "staged_idempotent": first_hashes == second_hashes,
        "staged_cache_preserved": staged_cache_preserved,
        "temporary_stage_writes": True,
        "writes_performed": False,
        "runtime_writes": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    args = parser.parse_args(argv)
    try:
        variables = _parse_variables(args.set) if args.set else DEFAULT_VARIABLES
        report = verify_bootstrap(args.root, variables=variables)
    except (OSError, UnicodeError, ValueError, TemplateValidationError) as error:
        print(f"bootstrap check rejected input: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["idempotent"] and report["staged_idempotent"] and report["staged_cache_preserved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
