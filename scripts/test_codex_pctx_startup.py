import json
import os
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACKED_CONFIG = ROOT / ".codex" / "config.toml"
PORTABLE_CONFIG = ROOT / "ai" / "config" / "codex" / "config.base.toml"
OBSOLETE_SHIM = ROOT / "ai" / "bin" / "pctx-mcp-stdio-shim.py"


class CodexPctxStartupTests(unittest.TestCase):
    def test_tracked_codex_config_uses_pctx_jsonl_transport_directly(self):
        config = tomllib.loads(TRACKED_CONFIG.read_text(encoding="utf-8"))

        server = config["mcp_servers"]["pctx"]
        self.assertEqual(server["command"], "pctx")
        self.assertNotIn("pctx-mcp-stdio-shim", " ".join([server["command"], *server["args"]]))

    def test_portable_codex_config_uses_pctx_jsonl_transport_directly(self):
        config = tomllib.loads(PORTABLE_CONFIG.read_text(encoding="utf-8"))

        server = config["mcp_servers"]["pctx"]
        self.assertEqual(server["command"], "pctx")
        self.assertEqual(
            server["args"],
            ["mcp", "start", "--stdio", "-c", "${PCTX_CONFIG}"],
        )

    def test_content_length_adapter_is_retired(self):
        self.assertFalse(
            OBSOLETE_SHIM.exists(),
            "Codex and pctx both use newline-delimited JSON; do not reintroduce the Content-Length adapter",
        )

    def test_configured_command_round_trips_codex_jsonl_initialize(self):
        config = tomllib.loads(TRACKED_CONFIG.read_text(encoding="utf-8"))
        server = config["mcp_servers"]["pctx"]
        request = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        }

        with tempfile.TemporaryDirectory() as directory:
            fake_pctx = Path(directory) / "pctx"
            fake_pctx.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "request = json.loads(sys.stdin.readline())\n"
                "print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], "
                "'result': {'protocolVersion': '2025-06-18'}}), flush=True)\n",
                encoding="utf-8",
            )
            fake_pctx.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{directory}{os.pathsep}{env.get('PATH', '')}"

            process = subprocess.run(
                [server["command"], *server["args"]],
                input=json.dumps(request).encode() + b"\n",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
        response = json.loads(process.stdout.splitlines()[0])
        self.assertEqual(response["id"], request["id"])
        self.assertEqual(response["result"]["protocolVersion"], "2025-06-18")


if __name__ == "__main__":
    unittest.main()
