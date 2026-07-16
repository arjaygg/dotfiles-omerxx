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
    for relative in [".mcp.json", ".cursor/mcp.json", ".gemini/mcp.json"]:
        write(root / relative, json.dumps(client))
    write(
        root / ".windsurf/mcp_config.json",
        json.dumps(
            {
                "mcpServers": {
                    "pctx": client["mcpServers"]["pctx"],
                    "lean-ctx": {"command": "lean-ctx", "env": {"LEAN_CTX_FULL_TOOLS": "1"}},
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
                    {"name": "qmd", "command": "qmd"},
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


if __name__ == "__main__":
    unittest.main()
