#!/usr/bin/env python3
"""Tests for scripts/mcp_topology_check.py."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from mcp_topology_check import check_mcp_topology, summarize_results


SERENA = {"command": "serena_wrapper.sh", "args": []}
LEAN_CTX = {"command": "lean-ctx", "args": []}

TRACKED_CLIENTS = (
    ".mcp.json",
    ".cursor/mcp.json",
    ".gemini/mcp.json",
    ".gemini/settings.json",
    ".gemini/config/mcp_config.json",
    ".windsurf/mcp_config.json",
)


def _write(root: Path, relative: str, payload: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_client_set(root: Path, servers: dict) -> None:
    """Populate every tracked client config with the same server set."""
    for relative in TRACKED_CLIENTS:
        _write(root, relative, {"mcpServers": servers})
    codex = root / ".codex/config.toml"
    codex.parent.mkdir(parents=True, exist_ok=True)
    codex.write_text(
        "\n".join(f'[mcp_servers.{name}]\ncommand = "x"\nargs = []\n' for name in servers),
        encoding="utf-8",
    )


def _failures(results) -> list[str]:
    return [r.rule for r in results if r.status == "fail"]


class TopologyCheckTests(unittest.TestCase):
    def test_direct_topology_passes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_client_set(root, {"serena": SERENA, "lean-ctx": LEAN_CTX})
            self.assertEqual(_failures(check_mcp_topology(root)), [])

    def test_retired_gateway_server_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_client_set(root, {"serena": SERENA, "pctx": {"command": "pctx"}})
            self.assertIn("client-retired-server", _failures(check_mcp_topology(root)))

    def test_missing_serena_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_client_set(root, {"lean-ctx": LEAN_CTX})
            self.assertIn("client-has-serena", _failures(check_mcp_topology(root)))

    def test_serena_fallback_satisfies_serena_rule(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, ".mcp.json", {"mcpServers": {"serena-fallback": SERENA}})
            results = [r for r in check_mcp_topology(root) if r.path == ".mcp.json"]
            self.assertNotIn("client-has-serena", _failures(results))

    def test_unapproved_server_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_client_set(root, {"serena": SERENA, "rogue": {"command": "x"}})
            self.assertIn("client-unapproved-server", _failures(check_mcp_topology(root)))

    def test_missing_config_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            results = check_mcp_topology(Path(tmp))
            self.assertIn("client-config-present", _failures(results))
            self.assertIn("codex-config-present", _failures(results))

    def test_summary_counts_statuses(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_client_set(root, {"serena": SERENA})
            summary = summarize_results(check_mcp_topology(root))
            self.assertNotIn("fail", summary["by_status"])
            self.assertGreater(summary["total"], 0)


if __name__ == "__main__":
    unittest.main()
