import json
import tempfile
import unittest
from pathlib import Path

from scripts.mcp_gateway_check import check_mcp_gateway, summarize_results


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_valid_gateway_tree(root: Path) -> None:
    client = {
        "mcpServers": {
            "pctx": {
                "command": "pctx",
                "args": ["mcp", "start", "--stdio", "-c", "~/.config/pctx/pctx.json"],
            }
        }
    }
    for relative in [".mcp.json", ".cursor/mcp.json"]:
        write(root / relative, json.dumps(client))
    agy_client = {
        "mcpServers": {
            "pctx": {
                "command": "agy-mcp-legacy-shim.py",
                "args": ["--", "pctx", "mcp", "start", "--stdio", "-c", "~/.config/pctx/pctx.json"],
            }
        }
    }
    for relative in [".gemini/mcp.json", ".gemini/settings.json", ".gemini/config/mcp_config.json"]:
        write(root / relative, json.dumps(agy_client))
    write(root / ".local/bin/agy-mcp-legacy-shim.py", "#!/usr/bin/env python3\n")
    write(
        root / ".windsurf/mcp_config.json",
        json.dumps(
            {
                "mcpServers": {
                    "pctx": client["mcpServers"]["pctx"],
                    "serena": {"command": "serena"},
                }
            }
        ),
    )
    write(
        root / ".codex/config.toml",
        '\n'.join(
            [
                "[mcp_servers.pctx]",
                'type = "stdio"',
                'command = "pctx"',
                'args = ["mcp", "start", "--stdio", "-c", "~/.config/pctx/pctx.json"]',
            ]
        ),
    )
    write(
        root / ".config/pctx/pctx.json",
        json.dumps(
            {
                "servers": [
                    {"name": "serena", "command": "serena"},
                    {"name": "lean-ctx", "command": "lean-ctx"},
                    {"name": "repomix", "command": "repomix"},
                    {"name": "graphify", "command": "graphify"},
                ]
            }
        ),
    )


class McpGatewayCheckTests(unittest.TestCase):
    def test_valid_gateway_tree_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_valid_gateway_tree(root)

            results = check_mcp_gateway(root)

        self.assertFalse([result for result in results if result.status == "fail"])
        summary = summarize_results(results)
        self.assertEqual(summary["by_status"], {"ok": summary["total"]})

    def test_direct_stale_client_server_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_valid_gateway_tree(root)
            cursor = {
                "mcpServers": {
                    "pctx": {"command": "pctx", "args": ["mcp", "start", "--stdio"]},
                    "sequential-thinking": {"command": "npx"},
                }
            }
            write(root / ".cursor/mcp.json", json.dumps(cursor))

            results = check_mcp_gateway(root)

        self.assertIn(
            ("client-unapproved-server", ".cursor/mcp.json", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_direct_serena_is_approved_for_standalone_exposure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_valid_gateway_tree(root)
            path = root / ".gemini/config/mcp_config.json"
            config = json.loads(path.read_text(encoding="utf-8"))
            config["mcpServers"]["serena"] = {"command": "serena"}
            write(path, json.dumps(config))

            results = check_mcp_gateway(root)

        self.assertNotIn(
            ("client-unapproved-server", ".gemini/config/mcp_config.json", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_direct_lean_ctx_is_approved_for_windsurf(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_valid_gateway_tree(root)
            path = root / ".windsurf/mcp_config.json"
            config = json.loads(path.read_text(encoding="utf-8"))
            config["mcpServers"]["lean-ctx"] = {"command": "lean-ctx"}
            write(path, json.dumps(config))

            results = check_mcp_gateway(root)

        self.assertNotIn(
            ("client-unapproved-server", ".windsurf/mcp_config.json", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_serena_fallback_is_approved_for_root_mcp_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_valid_gateway_tree(root)
            path = root / ".mcp.json"
            config = json.loads(path.read_text(encoding="utf-8"))
            config["mcpServers"]["serena-fallback"] = {"command": "serena"}
            write(path, json.dumps(config))

            results = check_mcp_gateway(root)

        self.assertNotIn(
            ("client-unapproved-server", ".mcp.json", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_codex_direct_tool_servers_are_approved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_valid_gateway_tree(root)
            config = '\n'.join(
                [
                    "[mcp_servers.pctx]",
                    'command = "pctx"',
                    'args = ["mcp", "start", "--stdio"]',
                    "[mcp_servers.lean-ctx]",
                    'command = "lean-ctx"',
                    "[mcp_servers.notebooklm]",
                    'command = "notebooklm-mcp"',
                    "[mcp_servers.chrome-devtools]",
                    'command = "chrome-devtools-mcp"',
                ]
            )
            write(root / ".codex/config.toml", config)

            results = check_mcp_gateway(root)

        self.assertNotIn(
            ("codex-unapproved-server", ".codex/config.toml", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_agy_missing_legacy_shim_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_valid_gateway_tree(root)
            (root / ".local/bin/agy-mcp-legacy-shim.py").unlink()

            results = check_mcp_gateway(root)

        self.assertIn(
            ("client-legacy-shim-present", ".gemini/config/mcp_config.json", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_pctx_missing_expected_backend_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_valid_gateway_tree(root)
            pctx = {"servers": [{"name": "serena"}, {"name": "qmd"}]}
            write(root / ".config/pctx/pctx.json", json.dumps(pctx))

            results = check_mcp_gateway(root)

        self.assertIn(
            ("pctx-missing-server", ".config/pctx/pctx.json", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_current_repo_gateway_shape_passes(self):
        root = Path(__file__).resolve().parents[1]
        results = check_mcp_gateway(root)

        self.assertFalse([result for result in results if result.status == "fail"])

    def test_current_gemini_configs_use_direct_pctx_and_standalone_serena(self):
        root = Path(__file__).resolve().parents[1]
        for relative in [
            ".gemini/mcp.json",
            ".gemini/settings.json",
            ".gemini/config/mcp_config.json",
        ]:
            config = json.loads((root / relative).read_text(encoding="utf-8"))
            pctx = config["mcpServers"]["pctx"]

            invocation = " ".join([str(pctx["command"]), *map(str, pctx["args"])])
            self.assertIn("pctx", invocation)
            self.assertIn("mcp", invocation)
            self.assertIn("start", invocation)
            if relative != ".gemini/config/mcp_config.json":
                self.assertIn("serena", config["mcpServers"])


if __name__ == "__main__":
    unittest.main()
