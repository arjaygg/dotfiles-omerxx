#!/usr/bin/env python3
"""Validate tracked MCP client topology without touching live runtime files.

Every client registers its MCP servers directly; there is no gateway process.
The checks below assert that each tracked config parses, names only approved
servers, reaches Serena somehow, and does not reintroduce a `pctx` entry.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


# Servers retired with the gateway. Their presence in any client is a failure.
FORBIDDEN_SERVERS = {"pctx"}

# Any one of these satisfies the "client can reach Serena" rule.
SERENA_ALIASES = {"serena", "serena-fallback"}

CLIENT_JSON_CONFIGS = {
    ".mcp.json": {"serena", "serena-fallback", "lean-ctx", "repomix", "graphify"},
    ".cursor/mcp.json": {"serena", "lean-ctx", "repomix", "graphify", "notebooklm", "chrome-devtools"},
    ".gemini/mcp.json": {"serena", "lean-ctx", "repomix", "graphify", "notebooklm", "chrome-devtools"},
    ".gemini/settings.json": {"serena", "lean-ctx", "repomix", "graphify", "notebooklm", "chrome-devtools"},
    ".gemini/config/mcp_config.json": {"serena", "lean-ctx", "repomix", "graphify", "notebooklm", "chrome-devtools"},
    ".windsurf/mcp_config.json": {"serena", "lean-ctx", "repomix", "graphify"},
}
CODEX_ALLOWED_SERVERS = {
    "serena",
    "lean-ctx",
    "repomix",
    "graphify",
    "notebooklm",
    "chrome-devtools",
}


@dataclass(frozen=True)
class TopologyResult:
    rule: str
    path: str
    status: str
    message: str = ""


def _ok(rule: str, path: str) -> TopologyResult:
    return TopologyResult(rule, path, "ok")


def _fail(rule: str, path: str, message: str) -> TopologyResult:
    return TopologyResult(rule, path, "fail", message)


def _load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as error:
        return None, str(error)


def _client_servers(config: object) -> set[str]:
    if not isinstance(config, dict):
        return set()
    servers = config.get("mcpServers", {})
    return set(servers) if isinstance(servers, dict) else set()


def _check_server_set(relative: str, servers: set[str], allowed: set[str]) -> list[TopologyResult]:
    results: list[TopologyResult] = []
    for server in sorted(servers & FORBIDDEN_SERVERS):
        results.append(_fail("client-retired-server", relative, f"retired server {server!r} is still registered"))
    results.append(
        _ok("client-has-serena", relative)
        if servers & SERENA_ALIASES
        else _fail("client-has-serena", relative, "no serena server registered")
    )
    for server in sorted(servers - allowed):
        results.append(_fail("client-unapproved-server", relative, f"unapproved server {server!r}"))
    for server in sorted(servers & allowed):
        results.append(_ok(f"client-approved-server-{server}", relative))
    return results


def _check_json_client(root: Path, relative: str, allowed: set[str]) -> list[TopologyResult]:
    path = root / relative
    if not path.is_file():
        return [_fail("client-config-present", relative, "missing MCP client config")]
    config, error = _load_json(path)
    if error:
        return [_fail("client-config-parse", relative, error)]
    results = [_ok("client-config-present", relative)]
    results.extend(_check_server_set(relative, _client_servers(config), allowed))
    return results


def _check_codex(root: Path) -> list[TopologyResult]:
    relative = ".codex/config.toml"
    path = root / relative
    if not path.is_file():
        return [_fail("codex-config-present", relative, "missing Codex config")]
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        return [_fail("codex-config-parse", relative, str(error))]

    servers = config.get("mcp_servers", {})
    names = set(servers) if isinstance(servers, dict) else set()
    results = [_ok("codex-config-present", relative)]
    results.extend(_check_server_set(relative, names, CODEX_ALLOWED_SERVERS))
    return results


def check_mcp_topology(root: Path) -> list[TopologyResult]:
    results: list[TopologyResult] = []
    for relative, allowed in CLIENT_JSON_CONFIGS.items():
        results.extend(_check_json_client(root, relative, allowed))
    results.extend(_check_codex(root))
    return results


def summarize_results(results: Sequence[TopologyResult]) -> dict[str, object]:
    return {
        "total": len(results),
        "by_status": dict(sorted(Counter(result.status for result in results).items())),
        "by_rule": dict(sorted(Counter(result.rule for result in results).items())),
        "by_path": dict(sorted(Counter(result.path for result in results).items())),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    results = check_mcp_topology(args.root.resolve())
    if args.summary:
        print(json.dumps(summarize_results(results), indent=2))
    else:
        print(json.dumps([asdict(result) for result in results], indent=2))
    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
