#!/usr/bin/env python3
"""Prove all-client configuration generation is deterministic and proposal-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    from scripts.config_generate import TemplateValidationError, _parse_variables
    from scripts.config_generate_all import build_proposals
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.config_generate import TemplateValidationError, _parse_variables
    from scripts.config_generate_all import build_proposals


DEFAULT_VARIABLES = {
    "PCTX_CONFIG": "~/.config/pctx/pctx.json",
    "USER_NAME": "portable-user",
}


def verify_bootstrap(root: Path, *, variables: dict[str, str] | None = None) -> dict[str, object]:
    """Render all manifest clients twice without writing any repository/runtime files."""

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
    return {
        "schema": 1,
        "root": ".",
        "client_count": len(clients),
        "clients": clients,
        "variable_names": sorted(values),
        "idempotent": first == second,
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
    return 0 if report["idempotent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
