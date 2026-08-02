import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from scripts.headroom_hardening import (
    HEADROOM_EXCLUDED_TOOLS,
    LEANCTX_CONTEXT_TOOLS,
    NATIVE_CONTEXT_TOOLS,
    PCTX_GATEWAY_TOOLS,
    audit_ccr_database,
    detect_recursive_ccr,
    docker_containers,
    hardening_environment,
    recover_ccr_bytes,
    remove_headroom_mcp_server,
    stop_orphan_containers,
    summarize_containers,
)

ROOT = Path(__file__).resolve().parents[1]


class HeadroomHardeningTests(unittest.TestCase):
    @staticmethod
    def shell_headroom_environment(path: Path) -> dict[str, str]:
        environment: dict[str, str] = {}
        pattern = re.compile(
            r"""^\s*(?:export\s+)?(HEADROOM_[A-Z_]+)=(?:"([^"]*)"|'([^']*)'|([^\s#]+))"""
        )
        for line in path.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line)
            if match:
                environment[match.group(1)] = next(
                    value for value in match.groups()[1:] if value is not None
                )
        return environment

    @staticmethod
    def nushell_headroom_environment(path: Path) -> dict[str, str]:
        environment: dict[str, str] = {}
        pattern = re.compile(r'^\s*\$env\.(HEADROOM_[A-Z_]+)\s*=\s*"([^"]*)"\s*$')
        for line in path.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line)
            if match:
                environment[match.group(1)] = match.group(2)
        return environment

    @staticmethod
    def make_ccr_database(path: Path, rows: list[tuple[str, str]]) -> None:
        connection = sqlite3.connect(path)
        connection.execute(
            "create table ccr_entries "
            "(hash text primary key, entry_json text not null, "
            "created_at real not null, ttl integer not null)"
        )
        connection.executemany(
            "insert into ccr_entries values (?, ?, 0, 60)",
            rows,
        )
        connection.commit()
        connection.close()

    def test_native_leanctx_and_pctx_tools_are_exactly_named_exclusions(self):
        required_native = {
            "bash",
            "exec_command",
            "shell_command",
            "run_shell_command",
            "read",
            "read_file",
            "read_text_file",
            "grep",
            "glob",
            "search_file_content",
            "codebase_search",
            "grep_search",
            "view_file",
        }
        required_leanctx = {
            "ctx_call",
            "ctx_compose",
            "ctx_expand",
            "ctx_glob",
            "ctx_read",
            "ctx_search",
            "ctx_session",
            "ctx_shell",
            "ctx_tree",
            "shell",
        }
        required_pctx = {
            "mcp__pctx__execute_typescript",
            "mcp__pctx__get_function_details",
            "mcp__pctx__list_functions",
        }
        required_prefixed = {
            "mcp__lean_ctx__ctx_call",
            "mcp__lean_ctx__ctx_read",
            "mcp__lean_ctx__ctx_compose",
            "mcp__lean_ctx__ctx_glob",
            "mcp__lean_ctx__ctx_session",
            "mcp__lean_ctx__ctx_shell",
            "mcp__lean_ctx__shell",
        }
        self.assertTrue(required_native.issubset(NATIVE_CONTEXT_TOOLS))
        self.assertEqual(LEANCTX_CONTEXT_TOOLS, required_leanctx)
        self.assertEqual(PCTX_GATEWAY_TOOLS, required_pctx)
        self.assertTrue(
            (
                required_native
                | required_leanctx
                | required_pctx
                | required_prefixed
            ).issubset(HEADROOM_EXCLUDED_TOOLS)
        )
        self.assertTrue(all(name == name.lower() for name in HEADROOM_EXCLUDED_TOOLS))
        self.assertFalse(
            any(any(character in name for character in "*?[]") for name in HEADROOM_EXCLUDED_TOOLS)
        )
        env = hardening_environment()
        self.assertEqual(env["HEADROOM_DISABLE_KOMPRESS"], "1")
        self.assertEqual(
            env["HEADROOM_EXCLUDE_TOOLS"].split(","),
            sorted(HEADROOM_EXCLUDED_TOOLS),
        )

    def test_all_tracked_environment_copies_exactly_match_canonical_environment(self):
        expected = hardening_environment()
        template = json.loads(
            (ROOT / "ai/config/claude/settings.base.json").read_text(encoding="utf-8")
        )["env"]
        copies = {
            "ai/config/claude/settings.base.json": {
                key: value for key, value in template.items() if key.startswith("HEADROOM_")
            },
            "setup.sh": self.shell_headroom_environment(ROOT / "setup.sh"),
            "zshrc/.zshrc": self.shell_headroom_environment(ROOT / "zshrc/.zshrc"),
            "nushell/env.nu": self.nushell_headroom_environment(ROOT / "nushell/env.nu"),
        }
        runtime_settings = ROOT / ".claude/settings.json"
        if runtime_settings.exists():
            runtime = json.loads(runtime_settings.read_text(encoding="utf-8"))["env"]
            copies[".claude/settings.json"] = {
                key: value for key, value in runtime.items() if key.startswith("HEADROOM_")
            }
        for path, actual in copies.items():
            with self.subTest(path=path):
                self.assertEqual(actual, expected)

    def test_project_codex_config_keeps_provider_settings_user_scoped(self):
        codex = tomllib.loads(
            (ROOT / ".codex/config.toml").read_text(encoding="utf-8")
        )
        self.assertNotIn("model_provider", codex)
        self.assertNotIn("model_providers", codex)
        self.assertNotIn("headroom", codex["mcp_servers"])

    def test_recursive_and_self_referential_ccr_are_rejected(self):
        self.assertEqual(detect_recursive_ccr("plain content", "abc123"), [])
        recursive = detect_recursive_ccr("prefix <<ccr:def456,string,1KB>>", "abc123")
        self.assertIn("nested-ccr", recursive)
        self_ref = detect_recursive_ccr("prefix <<ccr:abc123,string,1KB>>", "abc123")
        self.assertIn("self-referential-ccr", self_ref)

    def test_codex_cleanup_removes_mcp_server_but_preserves_provider_proxy(self):
        source = """
[mcp_servers.headroom]
command = "headroom"
args = ["mcp", "serve"]

[model_providers.headroom]
name = "Headroom"
base_url = "http://127.0.0.1:8787/v1"
"""
        cleaned = remove_headroom_mcp_server(source)
        self.assertNotIn("[mcp_servers.headroom]", cleaned)
        self.assertIn("[model_providers.headroom]", cleaned)

    def test_container_summary_requires_one_healthy_persistent_proxy(self):
        rows = [
            {"name": "headroom-default", "health": "healthy", "kind": "persistent"},
            {"name": "orphan", "health": "unhealthy", "kind": "mcp"},
            {"name": "stale", "health": "unknown", "kind": "orphan"},
        ]
        summary = summarize_containers(rows)
        self.assertEqual(summary["persistent_healthy"], 1)
        self.assertEqual(summary["orphan_mcp"], 2)
        self.assertFalse(summary["ok"])

    @mock.patch("scripts.headroom_hardening.subprocess.run")
    def test_cleanup_stops_only_mcp_and_orphan_containers(self, run):
        run.return_value.returncode = 0
        rows = [
            {"name": "headroom-default", "health": "healthy", "kind": "persistent"},
            {"name": "disposable-mcp", "health": "unhealthy", "kind": "mcp"},
            {"name": "stale-headroom", "health": "unknown", "kind": "orphan"},
            {"name": "", "health": "unknown", "kind": "mcp"},
        ]

        stopped = stop_orphan_containers(rows)

        self.assertEqual(stopped, ["disposable-mcp", "stale-headroom"])
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ["docker", "stop", "disposable-mcp"],
                ["docker", "stop", "stale-headroom"],
            ],
        )
        self.assertNotIn(
            "headroom-default",
            [argument for call in run.call_args_list for argument in call.args[0]],
        )

    @mock.patch("scripts.headroom_hardening.subprocess.run")
    def test_docker_discovery_preserves_default_and_recognizes_orphans(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = "\n".join(
            [
                json.dumps(
                    {
                        "Names": "headroom-default",
                        "Command": '"headroom proxy --host 0.0.0.0"',
                        "Status": "Up 2 hours (healthy)",
                    }
                ),
                json.dumps(
                    {
                        "Names": "disposable-mcp",
                        "Command": '"headroom mcp serve"',
                        "Status": "Up 2 minutes (unhealthy)",
                    }
                ),
                json.dumps(
                    {
                        "Names": "stale-headroom",
                        "Command": '"headroom proxy"',
                        "Status": "Up 1 hour",
                    }
                ),
            ]
        )

        rows = docker_containers()

        self.assertEqual(
            [(row["name"], row["kind"]) for row in rows],
            [
                ("headroom-default", "persistent"),
                ("disposable-mcp", "mcp"),
                ("stale-headroom", "orphan"),
            ],
        )

    @mock.patch("scripts.headroom_hardening.subprocess.run")
    def test_docker_unavailable_is_safe_and_selects_nothing(self, run):
        run.side_effect = FileNotFoundError("docker")

        self.assertEqual(docker_containers(), [])
        self.assertEqual(
            stop_orphan_containers(
                [{"name": "disposable-mcp", "health": "unknown", "kind": "mcp"}]
            ),
            [],
        )

    def test_ccr_database_audit_finds_and_can_delete_recursive_entries(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ccr.db"
            connection = sqlite3.connect(path)
            connection.execute(
                "create table ccr_entries "
                "(hash text primary key, entry_json text not null, "
                "created_at real not null, ttl integer not null)"
            )
            connection.executemany(
                "insert into ccr_entries values (?, ?, 0, 60)",
                [
                    (
                        "safe123",
                        json.dumps(
                            {
                                "hash": "safe123",
                                "original_content": "safe content",
                            }
                        ),
                    ),
                    (
                        "bad123",
                        json.dumps(
                            {
                                "hash": "bad123",
                                "original_content": "<<ccr:bad123,string,1KB>>",
                            }
                        ),
                    ),
                ],
            )
            connection.commit()
            connection.close()

            report = audit_ccr_database(path, delete_invalid=True)

            self.assertEqual(report["invalid"], 1)
            self.assertEqual(report["deleted"], 1)
            connection = sqlite3.connect(path)
            try:
                self.assertEqual(
                    connection.execute(
                        "select count(*) from ccr_entries"
                    ).fetchone()[0],
                    1,
                )
            finally:
                connection.close()

    def test_ccr_recovery_preserves_exact_final_newline_behavior(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ccr.db"
            self.make_ccr_database(
                path,
                [
                    (
                        "without-newline",
                        json.dumps({"original_content": "alpha"}),
                    ),
                    (
                        "with-newline",
                        json.dumps({"original_content": "βeta\n"}),
                    ),
                ],
            )

            self.assertEqual(recover_ccr_bytes(path, "without-newline"), b"alpha")
            self.assertEqual(
                recover_ccr_bytes(path, "with-newline"),
                "βeta\n".encode(),
            )
            for content_hash, expected in (
                ("without-newline", b"alpha"),
                ("with-newline", "βeta\n".encode()),
            ):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts/headroom_hardening.py"),
                        "recover-ccr",
                        str(path),
                        content_hash,
                    ],
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, expected)
                self.assertEqual(result.stderr, b"")

    def test_ccr_recovery_rejects_missing_malformed_and_recursive_entries(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ccr.db"
            self.make_ccr_database(
                path,
                [
                    ("malformed-json", "{broken"),
                    ("missing-content", json.dumps({"original_content": 42})),
                    (
                        "nested-safe",
                        json.dumps(
                            {"original_content": "<<ccr:def456,string,1KB>>"}
                        ),
                    ),
                    (
                        "abc123",
                        json.dumps(
                            {"original_content": "<<ccr:abc123,string,1KB>>"}
                        ),
                    ),
                ],
            )

            cases = {
                "not-found": b"not found",
                "malformed-json": b"malformed",
                "missing-content": b"malformed",
                "nested-safe": b"unsafe",
                "abc123": b"unsafe",
            }
            for content_hash, expected_error in cases.items():
                with self.subTest(content_hash=content_hash):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(ROOT / "scripts/headroom_hardening.py"),
                            "recover-ccr",
                            str(path),
                            content_hash,
                        ],
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, b"")
                    self.assertIn(b"headroom_hardening:", result.stderr)
                    self.assertIn(expected_error, result.stderr)


if __name__ == "__main__":
    unittest.main()
