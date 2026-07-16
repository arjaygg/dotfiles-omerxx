#!/usr/bin/env python3
"""Validate tracked MCP gateway topology without touching live runtime files."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


EXPECTED_PCTX_BACKENDS = {"serena", "qmd", "lean-ctx", "repomix", "graphify"}
CLIENT_JSON_CONFIGS = {
    ".mcp.json": {"pctx"},
    ".cursor/mcp.json": {"pctx"},
    ".gemini/mcp.json": {"pctx"},
    ".windsurf/mcp_config.json": {"pctx", "lean-ctx"},
}


@dataclass(frozen=True)
class GatewayResult:
    rule: str
    path: str
    status: str
    message: str = ""


def _ok(rule: str, path: str) -> GatewayResult:
    return GatewayResult(rule, path, "ok")


def _fail(rule: str, path: str, message: str) -> GatewayResult:
    return GatewayResult(rule, path, "fail", message)


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


def _has_pctx_stdio(config: object) -> bool:
    if not isinstance(config, dict):
        return False
    servers = config.get("mcpServers", {})
    if not isinstance(servers, dict):
        return False
    pctx = servers.get("pctx", {})
    if not isinstance(pctx, dict):
        return False
    command = str(pctx.get("command", ""))
    args = pctx.get("args", [])
    return command.endswith("pctx") and isinstance(args, list) and "mcp" in args and "start" in args


def _check_json_client(root: Path, relative: str, allowed: set[str]) -> list[GatewayResult]:
    path = root / relative
    results: list[GatewayResult] = []
    if not path.is_file():
        return [_fail("client-config-present", relative, "missing MCP client config")]
    config, error = _load_json(path)
    if error:
        return [_fail("client-config-parse", relative, error)]

    servers = _client_servers(config)
    results.append(_ok("client-config-present", relative))
    results.append(
        _ok("client-has-pctx", relative)
        if "pctx" in servers
        else _fail("client-has-pctx", relative, "pctx server missing")
    )
    results.append(
        _ok("client-pctx-stdio", relative)
        if _has_pctx_stdio(config)
        else _fail("client-pctx-stdio", relative, "pctx does not invoke `pctx mcp start`")
    )
    for server in sorted(servers - allowed):
        results.append(_fail("client-unapproved-server", relative, f"unapproved direct server {server!r}"))
    for server in sorted(servers & allowed):
        results.append(_ok(f"client-approved-server-{server}", relative))
    return results


def _check_codex(root: Path) -> list[GatewayResult]:
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
    results.append(
        _ok("codex-has-pctx", relative)
        if "pctx" in names
        else _fail("codex-has-pctx", relative, "pctx server missing")
    )
    pctx = servers.get("pctx", {}) if isinstance(servers, dict) else {}
    args = pctx.get("args", []) if isinstance(pctx, dict) else []
    command = str(pctx.get("command", "")) if isinstance(pctx, dict) else ""
    results.append(
        _ok("codex-pctx-stdio", relative)
        if command.endswith("pctx") and isinstance(args, list) and "mcp" in args and "start" in args
        else _fail("codex-pctx-stdio", relative, "pctx does not invoke `pctx mcp start`")
    )
    for server in sorted(names - {"pctx", "lean-ctx"}):
        results.append(_fail("codex-unapproved-server", relative, f"unapproved direct server {server!r}"))
    for server in sorted(names & {"pctx", "lean-ctx"}):
        results.append(_ok(f"codex-approved-server-{server}", relative))
    return results


def _check_pctx(root: Path) -> list[GatewayResult]:
    relative = ".config/pctx/pctx.json"
    path = root / relative
    if not path.is_file():
        return [_fail("pctx-config-present", relative, "missing pctx gateway config")]
    config, error = _load_json(path)
    if error:
        return [_fail("pctx-config-parse", relative, error)]
    servers = config.get("servers", []) if isinstance(config, dict) else []
    names = {
        str(server.get("name"))
        for server in servers
        if isinstance(server, dict) and server.get("name") is not None
    }
    results = [_ok("pctx-config-present", relative)]
    for name in sorted(EXPECTED_PCTX_BACKENDS - names):
        results.append(_fail("pctx-missing-server", relative, f"missing backend {name!r}"))
    for name in sorted(names - EXPECTED_PCTX_BACKENDS):
        results.append(_fail("pctx-unexpected-server", relative, f"unexpected backend {name!r}"))
    for name in sorted(names & EXPECTED_PCTX_BACKENDS):
        results.append(_ok(f"pctx-server-{name}", relative))
    return results


def check_mcp_gateway(root: Path) -> list[GatewayResult]:
    results: list[GatewayResult] = []
    for relative, allowed in CLIENT_JSON_CONFIGS.items():
        results.extend(_check_json_client(root, relative, allowed))
    results.extend(_check_codex(root))
    results.extend(_check_pctx(root))
    return results


def summarize_results(results: Sequence[GatewayResult]) -> dict[str, object]:
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

    results = check_mcp_gateway(args.root.resolve())
    if args.summary:
        print(json.dumps(summarize_results(results), indent=2))
    else:
        print(json.dumps([asdict(result) for result in results], indent=2))
    return 1 if any(result.status == "fail" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
