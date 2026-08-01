import json
import os
import re
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACKED_CONFIG = ROOT / ".codex" / "config.toml"
PORTABLE_CONFIG = ROOT / "ai" / "config" / "codex" / "config.base.toml"
OBSOLETE_SHIM = ROOT / "ai" / "bin" / "pctx-mcp-stdio-shim.py"
HOOKS_CONFIG = ROOT / ".codex" / "hooks.json"
PRE_TOOL_GUARD = ROOT / ".codex" / "hooks" / "pre-bash-guard.sh"
LEAN_CTX_WRAPPER = ROOT / ".local" / "bin" / "lean_ctx_wrapper.sh"
SERENA_WRAPPER = ROOT / ".local" / "bin" / "serena_wrapper.sh"
PCTX_WRAPPER = ROOT / ".local" / "bin" / "pctx_wrapper.sh"
FOCUSED_LEAN_CTX_TOOLS = [
    "ctx_compose",
    "ctx_read",
    "ctx_search",
    "ctx_tree",
    "ctx_expand",
]


class CodexPctxStartupTests(unittest.TestCase):
    def run_context_hook(
        self,
        home: Path,
        payload: dict | str,
    ) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "HOME": str(home),
            "CONTEXT_ROUTING_ROLLOUT": "block",
            "XDG_STATE_HOME": str(home / "state"),
        }
        input_text = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run(
            ["bash", str(PRE_TOOL_GUARD)],
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=5,
            check=False,
        )

    def test_tracked_codex_config_uses_pctx_wrapper_contract(self):
        config = tomllib.loads(TRACKED_CONFIG.read_text(encoding="utf-8"))

        server = config["mcp_servers"]["pctx"]
        self.assertEqual(server["type"], "stdio")
        self.assertEqual(server["command"], "bash")
        self.assertEqual(
            server["args"],
            [
                "-c",
                'exec "$HOME/.dotfiles/.local/bin/pctx_wrapper.sh" mcp start --stdio -c "$HOME/.config/pctx/pctx.json"',
            ],
        )
        self.assertNotIn("pctx-mcp-stdio-shim", " ".join(server["args"]))

    def test_portable_codex_config_uses_pctx_jsonl_transport_directly(self):
        config = tomllib.loads(PORTABLE_CONFIG.read_text(encoding="utf-8"))

        server = config["mcp_servers"]["pctx"]
        self.assertEqual(server["command"], "pctx")
        self.assertEqual(
            server["args"],
            ["mcp", "start", "--stdio", "-c", "${PCTX_CONFIG}"],
        )

    def test_runtime_and_template_serena_launchers_support_both_binary_homes(self):
        for config_path in (TRACKED_CONFIG, PORTABLE_CONFIG):
            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
            server = config["mcp_servers"]["serena"]
            for binary_relative in (".local/bin/serena", ".cargo/bin/serena"):
                with self.subTest(config=config_path, binary=binary_relative):
                    with tempfile.TemporaryDirectory() as directory:
                        home = Path(directory)
                        wrapper = home / ".dotfiles" / ".local" / "bin" / "serena_wrapper.sh"
                        wrapper.parent.mkdir(parents=True)
                        wrapper.symlink_to(SERENA_WRAPPER)
                        fake_binary = home / binary_relative
                        fake_binary.parent.mkdir(parents=True, exist_ok=True)
                        fake_binary.write_text(
                            "#!/usr/bin/env python3\n"
                            "import json, sys\n"
                            "print(json.dumps(sys.argv[1:]), flush=True)\n",
                            encoding="utf-8",
                        )
                        fake_binary.chmod(0o755)
                        env = {**os.environ, "HOME": str(home)}

                        process = subprocess.run(
                            [server["command"], *server["args"]],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            env=env,
                            timeout=5,
                            check=False,
                        )

                    self.assertEqual(
                        process.returncode,
                        0,
                        process.stderr.decode(errors="replace"),
                    )
                    self.assertEqual(
                        json.loads(process.stdout),
                        [
                            "start-mcp-server",
                            "--context",
                            "claude-code",
                            "--project-from-cwd",
                            "--log-level",
                            "ERROR",
                        ],
                    )

    def test_runtime_and_template_have_distinct_expected_server_sets(self):
        expected_by_config = {
            TRACKED_CONFIG: {
                "pctx",
                "notebooklm",
                "chrome-devtools",
                "serena",
                "lean-ctx",
            },
            PORTABLE_CONFIG: {"pctx", "notebooklm", "chrome-devtools", "serena"},
        }
        for config_path, expected in expected_by_config.items():
            with self.subTest(config=config_path):
                config = tomllib.loads(config_path.read_text(encoding="utf-8"))
                self.assertEqual(set(config["mcp_servers"]), expected)

    def test_runtime_standalone_lean_ctx_exposes_only_focused_tools(self):
        runtime = tomllib.loads(TRACKED_CONFIG.read_text(encoding="utf-8"))
        lean_ctx = runtime["mcp_servers"]["lean-ctx"]

        self.assertEqual(lean_ctx["enabled_tools"], FOCUSED_LEAN_CTX_TOOLS)
        self.assertEqual(set(lean_ctx["tools"]), set(FOCUSED_LEAN_CTX_TOOLS))
        for tool in FOCUSED_LEAN_CTX_TOOLS:
            self.assertEqual(lean_ctx["tools"][tool]["approval_mode"], "approve")

        portable = tomllib.loads(PORTABLE_CONFIG.read_text(encoding="utf-8"))
        self.assertNotIn("lean-ctx", portable["mcp_servers"])

    def test_runtime_and_template_do_not_define_project_local_provider(self):
        for config_path in (TRACKED_CONFIG, PORTABLE_CONFIG):
            with self.subTest(config=config_path):
                text = config_path.read_text(encoding="utf-8")
                config = tomllib.loads(text)
                self.assertNotIn("model_provider", config)
                self.assertNotIn("model_providers", config)
                self.assertNotIn("headroom", config["mcp_servers"])

    def test_portable_template_rejects_absolute_home_paths(self):
        text = PORTABLE_CONFIG.read_text(encoding="utf-8")

        self.assertNotRegex(text, r"/Users/[^/\"'\s]+")

    def test_tracked_config_rejects_stale_absolute_project_paths(self):
        text = TRACKED_CONFIG.read_text(encoding="utf-8")

        self.assertIn('[projects."~/git/ai-native"]', text)
        self.assertEqual(text.count('[projects."~/.dotfiles"]'), 1)
        self.assertNotRegex(text, r'\[projects\."/Users/[^"]+"\]')

    def test_codex_hook_matcher_covers_shell_and_native_read_tools(self):
        config = json.loads(HOOKS_CONFIG.read_text(encoding="utf-8"))
        matcher = re.compile(config["hooks"]["PreToolUse"][0]["matcher"])
        for tool in (
            "Bash",
            "shell_command",
            "exec_command",
            "Read",
            "read_file",
            "read_text_file",
        ):
            with self.subTest(tool=tool):
                self.assertIsNotNone(matcher.fullmatch(tool))

    def test_codex_context_hook_blocks_full_reads_and_surfaces_warnings(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / ".dotfiles").symlink_to(ROOT, target_is_directory=True)
            huge = home / "generated.lock"
            huge.write_text("generated\n", encoding="utf-8")
            medium = home / "medium.md"
            medium.write_text("line\n" * 300, encoding="utf-8")

            for payload in (
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": f"cat {huge}"},
                },
                {
                    "tool_name": "read_file",
                    "tool_input": {"path": str(huge)},
                },
            ):
                with self.subTest(payload=payload):
                    blocked = self.run_context_hook(home, payload)
                    self.assertEqual(blocked.returncode, 2)
                    self.assertIn("CODEX CONTEXT BLOCK", blocked.stderr)

            warned = self.run_context_hook(
                home,
                {
                    "tool_name": "read_text_file",
                    "tool_input": {"file_path": str(medium)},
                },
            )
            self.assertEqual(warned.returncode, 0)
            self.assertIn("CODEX CONTEXT WARNING", warned.stderr)
            self.assertIn(
                "CODEX CONTEXT WARNING",
                json.loads(warned.stdout)["systemMessage"],
            )

    def test_codex_context_hook_fails_open_for_bad_or_unrelated_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / ".dotfiles").symlink_to(ROOT, target_is_directory=True)
            for payload in (
                "{",
                {
                    "tool_name": "Bash",
                    "tool_input": {"command": "printf ok"},
                },
            ):
                with self.subTest(payload=payload):
                    process = self.run_context_hook(home, payload)
                    self.assertEqual(process.returncode, 0)
                    self.assertEqual(process.stdout, "")

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
            home = Path(directory)
            wrapper = home / ".dotfiles" / ".local" / "bin" / "pctx_wrapper.sh"
            wrapper.parent.mkdir(parents=True)
            wrapper.symlink_to(PCTX_WRAPPER)
            fake_pctx = home / ".local" / "bin" / "pctx"
            fake_pctx.parent.mkdir(parents=True)
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
            env["HOME"] = str(home)

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
