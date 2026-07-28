import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContextHookAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        (self.home / ".dotfiles").symlink_to(ROOT, target_is_directory=True)
        self.small = self.home / "small.md"
        self.small.write_text("small\n", encoding="utf-8")
        self.huge = self.home / "generated.lock"
        self.huge.write_text("generated\n", encoding="utf-8")
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "CONTEXT_ROUTING_ROLLOUT": "block",
            "XDG_STATE_HOME": str(self.home / "state"),
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_hook(self, relative: str, payload: dict) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(ROOT / relative)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=self.env,
            cwd=self.home,
            check=False,
        )

    def read_metrics(self) -> tuple[list[dict], str]:
        path = self.home / "state" / "context-routing" / "metrics.jsonl"
        text = path.read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()], text

    def test_claude_blocks_huge_read_and_preserves_unrelated_command(self):
        blocked = self.run_hook(
            ".claude/hooks/pre-tool-gate-v2.sh",
            {"tool_name": "Read", "tool_input": {"file_path": str(self.huge)}},
        )
        self.assertEqual(blocked.returncode, 0)
        self.assertIn("permissionDecision", blocked.stdout)
        self.assertIn("deny", blocked.stdout)

        unrelated = self.run_hook(
            ".claude/hooks/pre-tool-gate-v2.sh",
            {"tool_name": "Bash", "tool_input": {"command": "printf ok"}},
        )
        self.assertEqual(unrelated.returncode, 0)
        self.assertNotIn("permissionDecision", unrelated.stdout)

    def test_codex_blocks_huge_shell_read_and_preserves_unrelated_command(self):
        blocked = self.run_hook(
            ".codex/hooks/pre-bash-guard.sh",
            {"tool_name": "exec_command", "tool_input": {"command": f"cat {self.huge}"}},
        )
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("CONTEXT BLOCK", blocked.stderr)

        unrelated = self.run_hook(
            ".codex/hooks/pre-bash-guard.sh",
            {"tool_name": "exec_command", "tool_input": {"command": "printf ok"}},
        )
        self.assertEqual(unrelated.returncode, 0)

    def test_claude_post_observer_records_private_metrics_and_preserves_payload(self):
        fake_bin = self.home / ".local" / "bin"
        fake_bin.mkdir(parents=True)
        observed_payload = self.home / "claude-observed.json"
        fake_lean_ctx = fake_bin / "lean-ctx"
        fake_lean_ctx.write_text(
            f'#!/bin/sh\ncat > "{observed_payload}"\nexit 7\n',
            encoding="utf-8",
        )
        fake_lean_ctx.chmod(0o755)
        private_path = str(self.home / "claude-private-input.txt")
        private_output = "claude-private-output-" + ("x" * 160)
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": private_path},
            "tool_response": {"output": private_output},
        }

        observed = self.run_hook(
            ".claude/hooks/lean-ctx-observe.sh",
            payload,
        )

        self.assertEqual(observed.returncode, 0)
        self.assertEqual(observed.stdout, "")
        self.assertEqual(observed.stderr, "")
        self.assertEqual(json.loads(observed_payload.read_text()), payload)
        metrics, raw_metrics = self.read_metrics()
        self.assertEqual(metrics[-1]["client"], "claude")
        self.assertEqual(
            metrics[-1]["returned_tokens"],
            (len(private_output.encode("utf-8")) + 3) // 4,
        )
        self.assertNotIn(private_output, raw_metrics)
        self.assertNotIn(private_path, raw_metrics)

    def test_codex_post_observer_records_reference_metrics_and_preserves_notice(self):
        private_path = str(self.home / "codex-private-input.txt")
        private_output = (
            "codex-private-output-"
            + ("x" * 16_000)
            + "[Archived:codex-post-observer-fixture]"
        )
        command = f"cat {private_path}"
        payload = {
            "tool_name": "exec_command",
            "tool_input": {"command": command},
            "tool_response": {"exit_code": 9, "output": private_output},
        }

        observed = self.run_hook(
            ".codex/hooks/post-bash-observe.sh",
            payload,
        )

        self.assertEqual(observed.returncode, 0)
        self.assertIn("CODEX POST-BASH NOTICE:", observed.stdout)
        self.assertIn("exit=9", observed.stdout)
        metrics, raw_metrics = self.read_metrics()
        self.assertEqual(metrics[-1]["client"], "codex")
        self.assertGreater(metrics[-1]["returned_tokens"], 4_000)
        self.assertEqual(metrics[-1]["reason_code"], "bounded-output")
        self.assertNotIn(private_output, raw_metrics)
        self.assertNotIn(private_path, raw_metrics)
        self.assertNotIn(command, raw_metrics)

    def test_cursor_adapter_emits_permission_schema(self):
        blocked = self.run_hook(
            ".cursor/hooks/context-file-gate.sh",
            {"tool_name": "read_file", "tool_input": {"path": str(self.huge)}},
        )
        self.assertEqual(json.loads(blocked.stdout)["permission"], "deny")

        allowed = self.run_hook(
            ".cursor/hooks/context-file-gate.sh",
            {"tool_name": "read_file", "tool_input": {"path": str(self.small)}},
        )
        self.assertEqual(json.loads(allowed.stdout)["permission"], "allow")

    def test_agy_adapter_emits_allow_tool_schema(self):
        blocked = self.run_hook(
            ".gemini/hooks/context-file-gate.sh",
            {
                "toolCall": {
                    "name": "run_command",
                    "args": {"CommandLine": f"cat {self.huge}"},
                }
            },
        )
        self.assertFalse(json.loads(blocked.stdout)["allow_tool"])

        allowed = self.run_hook(
            ".gemini/hooks/context-file-gate.sh",
            {
                "toolCall": {
                    "name": "run_command",
                    "args": {"CommandLine": "printf ok"},
                }
            },
        )
        self.assertTrue(json.loads(allowed.stdout)["allow_tool"])

    def test_agy_post_observer_records_privacy_safe_output_metrics(self):
        private_output = "agy-private-output-" + ("x" * 80)
        observed = self.run_hook(
            ".gemini/hooks/context-observe.sh",
            {
                "toolCall": {
                    "name": "run_command",
                    "args": {"CommandLine": "printf ok"},
                },
                "result": {"output": private_output},
            },
        )

        self.assertEqual(observed.returncode, 0)
        self.assertEqual(json.loads(observed.stdout), {})
        metrics, raw_metrics = self.read_metrics()
        self.assertEqual(metrics[-1]["client"], "agy")
        self.assertEqual(
            metrics[-1]["returned_tokens"],
            (len(private_output.encode("utf-8")) + 3) // 4,
        )
        self.assertNotIn(private_output, raw_metrics)

    def test_cursor_post_observer_records_reference_metrics_and_never_blocks(self):
        private_output = (
            "cursor-private-output-"
            + ("x" * 16_000)
            + "[Archived:post-observer-fixture]"
        )
        observed = self.run_hook(
            ".cursor/hooks/context-observe.sh",
            {
                "tool_name": "Shell",
                "tool_input": {"command": "printf ok"},
                "tool_output": private_output,
            },
        )

        self.assertEqual(observed.returncode, 0)
        self.assertEqual(json.loads(observed.stdout), {})
        metrics, raw_metrics = self.read_metrics()
        self.assertEqual(metrics[-1]["client"], "cursor")
        self.assertGreater(metrics[-1]["returned_tokens"], 4_000)
        self.assertEqual(metrics[-1]["reason_code"], "bounded-output")
        self.assertNotIn(private_output, raw_metrics)

        unrelated = self.run_hook(
            ".cursor/hooks/context-observe.sh",
            {"tool_name": "unrelated", "tool_input": {}},
        )
        self.assertEqual(unrelated.returncode, 0)
        self.assertEqual(json.loads(unrelated.stdout), {})
        metrics, _ = self.read_metrics()
        self.assertEqual(metrics[-1]["reason_code"], "post-output-unavailable")

    def test_post_observers_are_registered_once_without_replacing_existing_hooks(self):
        agy = json.loads((ROOT / ".gemini/hooks.json").read_text(encoding="utf-8"))
        agy_commands = [
            hook["command"]
            for config in agy.values()
            for group in config.get("PostToolUse", [])
            for hook in group.get("hooks", [])
        ]
        self.assertEqual(
            sum("context-observe.sh" in command for command in agy_commands),
            1,
        )

        cursor = json.loads((ROOT / ".cursor/hooks.json").read_text(encoding="utf-8"))
        cursor_commands = [
            hook["command"] for hook in cursor["hooks"]["postToolUse"]
        ]
        self.assertEqual(
            sum("context-observe.sh" in command for command in cursor_commands),
            1,
        )
        self.assertTrue(
            any("advisor-escalate.sh" in command for command in cursor_commands)
        )

if __name__ == "__main__":
    unittest.main()
