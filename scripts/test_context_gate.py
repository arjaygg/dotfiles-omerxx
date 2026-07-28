import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from ai.context.context_gate import (
    GateRequest,
    classify_path,
    evaluate_request,
    main,
    parse_payload,
)


class ContextGateBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_sized(self, name: str, byte_count: int, line_count: int) -> Path:
        path = self.root / name
        if line_count <= 1:
            content = b"x" * byte_count
        else:
            self.assertGreaterEqual(byte_count, line_count - 1)
            content = b"\n" * (line_count - 1) + b"x" * (byte_count - line_count + 1)
        path.write_bytes(content)
        return path

    def test_size_boundaries_are_inclusive_at_lower_class(self):
        small = self.write_sized("small.md", 16 * 1024, 200)
        medium = self.write_sized("medium.md", 128 * 1024, 1_500)
        large = self.write_sized("large.md", 512 * 1024, 1_500)

        self.assertEqual(classify_path(small).size_class, "small")
        self.assertEqual(classify_path(medium).size_class, "medium")
        self.assertEqual(classify_path(large).size_class, "large")

    def test_crossing_each_boundary_promotes_the_size_class(self):
        medium_bytes = self.write_sized("medium-bytes.md", 16 * 1024 + 1, 200)
        medium_lines = self.write_sized("medium-lines.md", 16 * 1024, 201)
        large_bytes = self.write_sized("large-bytes.md", 128 * 1024 + 1, 200)
        large_lines = self.write_sized("large-lines.md", 128 * 1024, 1_501)
        huge = self.write_sized("huge.md", 512 * 1024 + 1, 1_500)

        self.assertEqual(classify_path(medium_bytes).size_class, "medium")
        self.assertEqual(classify_path(medium_lines).size_class, "medium")
        self.assertEqual(classify_path(large_bytes).size_class, "large")
        self.assertEqual(classify_path(large_lines).size_class, "large")
        self.assertEqual(classify_path(huge).size_class, "huge")

    def test_lockfiles_generated_artifacts_and_logs_are_huge(self):
        for name in ("package-lock.json", "generated.pb.go", "build.log"):
            with self.subTest(name=name):
                path = self.write_sized(name, 32, 1)
                self.assertEqual(classify_path(path).size_class, "huge")


class ContextGateDecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.state = self.root / "state"

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_file(self, name: str, size: int) -> Path:
        path = self.root / name
        path.write_bytes(b"x" * size)
        return path

    def evaluate(self, request: GateRequest, rollout: str = "warn"):
        with mock.patch.dict(
            os.environ,
            {
                "CONTEXT_ROUTING_ROLLOUT": rollout,
                "XDG_STATE_HOME": str(self.state),
            },
            clear=False,
        ):
            return evaluate_request(request)

    def test_small_native_read_is_allowed(self):
        path = self.make_file("small.md", 1_024)
        result = self.evaluate(
            GateRequest(client="claude", event="pre_tool_use", tool="Read", path=str(path))
        )
        self.assertEqual(result.decision, "allow")

    def test_medium_read_warns_with_focused_alternative(self):
        path = self.make_file("medium.md", 50 * 1024)
        result = self.evaluate(
            GateRequest(client="codex", event="pre_tool_use", tool="read_file", path=str(path))
        )
        self.assertEqual(result.decision, "warn")
        self.assertEqual(result.reason_code, "medium-unscoped-read")
        self.assertIn('ctx_read(mode="task")', result.message)

    def test_large_read_warns_then_blocks_after_rollout(self):
        path = self.make_file("large.md", 200 * 1024)
        request = GateRequest(
            client="cursor", event="pre_tool_use", tool="Read", path=str(path)
        )
        self.assertEqual(self.evaluate(request, "warn").decision, "warn")
        blocked = self.evaluate(request, "block")
        self.assertEqual(blocked.decision, "deny")
        self.assertEqual(blocked.reason_code, "large-unscoped-read")
        self.assertIn("ctx_compose", blocked.message)

    def test_huge_native_read_is_always_denied(self):
        path = self.make_file("generated.lock", 32)
        request = GateRequest(
            client="gemini", event="pre_tool_use", tool="read_file", path=str(path)
        )
        self.assertEqual(self.evaluate(request, "warn").decision, "deny")

    def test_exact_ctx_read_modes_are_explicit_escape_hatches(self):
        path = self.make_file("large.md", 200 * 1024)
        for mode in ("raw", "full", "anchored"):
            with self.subTest(mode=mode):
                result = self.evaluate(
                    GateRequest(
                        client="codex",
                        event="pre_tool_use",
                        tool="ctx_read",
                        path=str(path),
                        mode=mode,
                    ),
                    "block",
                )
                self.assertEqual(result.decision, "allow")
                self.assertEqual(result.reason_code, "exactness-escape")

    def test_focused_ctx_read_modes_are_allowed(self):
        path = self.make_file("huge.log", 600 * 1024)
        for mode in ("task", "reference", "lines:5-20"):
            with self.subTest(mode=mode):
                result = self.evaluate(
                    GateRequest(
                        client="windsurf",
                        event="pre_tool_use",
                        tool="ctx_read",
                        path=str(path),
                        mode=mode,
                    ),
                    "block",
                )
                self.assertEqual(result.decision, "allow")

    def test_machine_override_can_only_demote_a_denial_to_warning(self):
        path = self.make_file("large.md", 200 * 1024)
        override_dir = self.root / "config" / "context-routing"
        override_dir.mkdir(parents=True)
        (override_dir / "override.json").write_text(
            json.dumps({"large": "allow"}), encoding="utf-8"
        )
        request = GateRequest(
            client="claude", event="pre_tool_use", tool="Read", path=str(path)
        )
        with mock.patch.dict(
            os.environ,
            {
                "CONTEXT_ROUTING_ROLLOUT": "block",
                "XDG_CONFIG_HOME": str(self.root / "config"),
                "XDG_STATE_HOME": str(self.state),
            },
            clear=False,
        ):
            result = evaluate_request(request)
        self.assertEqual(result.decision, "warn")
        self.assertEqual(result.reason_code, "local-demotion")

    def test_metrics_are_privacy_safe(self):
        path = self.make_file("private-name.md", 50 * 1024)
        self.evaluate(
            GateRequest(client="claude", event="pre_tool_use", tool="Read", path=str(path))
        )
        metric_path = self.state / "context-routing" / "metrics.jsonl"
        metric = json.loads(metric_path.read_text(encoding="utf-8").splitlines()[-1])
        self.assertNotIn(str(path), json.dumps(metric))
        self.assertNotIn("command", metric)
        self.assertEqual(
            metric["path_hash"],
            hashlib.sha256(str(path.resolve()).encode()).hexdigest(),
        )


class ContextGatePayloadTests(unittest.TestCase):
    def test_direct_tool_payloads_for_all_clients(self):
        fixtures = {
            "claude": {
                "tool_name": "Read",
                "tool_input": {"file_path": "docs/guide.md"},
            },
            "codex": {
                "tool": "read_file",
                "input": {"path": "docs/guide.md", "mode": "reference"},
            },
            "cursor": {
                "tool_name": "read_file",
                "tool_input": {"path": "docs/guide.md"},
            },
            "agy": {
                "tool_name": "read_file",
                "tool_input": {"file_path": "docs/guide.md"},
            },
        }
        for client, payload in fixtures.items():
            with self.subTest(client=client):
                request = parse_payload(payload, client=client)
                self.assertEqual(request.path, "docs/guide.md")

    def test_common_shell_reads_are_parsed(self):
        commands = {
            "cat docs/guide.md": ("full", None),
            "cat < docs/guide.md": ("full", None),
            "head -n 20 docs/guide.md": ("bounded", 20),
            "tail -n 30 docs/guide.md": ("bounded", 30),
            "sed -n '10,25p' docs/guide.md": ("bounded", 16),
            "cat docs/guide.md | head -n 5": ("bounded", 5),
            "cat docs/guide.md | sed -n '2,6p'": ("bounded", 5),
            "cat docs/guide.md | grep routing | head -n 4": ("bounded", 4),
            "cat docs/guide.md | wc -l": ("metadata", None),
            "wc -l < docs/guide.md": ("metadata", None),
        }
        for command, (command_class, limit) in commands.items():
            with self.subTest(command=command):
                request = parse_payload(
                    {"tool_name": "exec_command", "tool_input": {"command": command}},
                    client="codex",
                )
                self.assertEqual(request.path, "docs/guide.md")
                self.assertEqual(request.command_class, command_class)
                self.assertEqual(request.limit, limit)

    def test_unbounded_shell_forms_are_never_misclassified_as_focused(self):
        commands = (
            "sed '10,25p' docs/guide.md",
            "sed -n '1,10p; 1,$p' docs/guide.md",
            "tail -n +1 docs/guide.md",
            "head -n -1 docs/guide.md",
            "cat docs/guide.md | sed -n p",
            "cat docs/guide.md | awk '{print}'",
            "cat docs/guide.md | grep .",
            "printf ignored | cat docs/guide.md",
            "wc docs/small.md | cat docs/guide.md",
            "python3 < docs/guide.md",
        )
        for command in commands:
            with self.subTest(command=command):
                request = parse_payload(
                    {"tool_name": "exec_command", "tool_input": {"command": command}},
                    client="codex",
                )
                self.assertEqual(request.path, "docs/guide.md")
                self.assertEqual(request.command_class, "full")
                self.assertIsNone(request.limit)
                self.assertFalse(request.unparseable)

    def test_unbounded_shell_evasions_are_denied_for_generated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "generated.lock"
            path.write_text("generated\n", encoding="utf-8")
            commands = (
                f"sed '1,10p' {path}",
                f"tail -n +1 {path}",
                f"cat {path} | grep .",
                f"printf ignored | cat {path}",
            )
            for command in commands:
                with self.subTest(command=command):
                    request = parse_payload(
                        {
                            "tool_name": "exec_command",
                            "tool_input": {"command": command},
                        },
                        client="codex",
                    )
                    with mock.patch.dict(
                        os.environ,
                        {"XDG_STATE_HOME": str(root / "state")},
                        clear=False,
                    ):
                        result = evaluate_request(request)
                    self.assertEqual(result.decision, "deny")
                    self.assertEqual(result.reason_code, "huge-native-full-read")

    def test_gemini_tool_call_payload_is_adapted(self):
        request = parse_payload(
            {
                "toolCall": {
                    "name": "run_command",
                    "args": {"CommandLine": "cat docs/guide.md"},
                }
            },
            client="agy",
        )
        self.assertEqual(request.tool, "run_command")
        self.assertEqual(request.path, "docs/guide.md")
        self.assertEqual(request.command_class, "full")

    def test_unrelated_compound_shell_commands_pass_without_warning(self):
        for command in (
            "printf ok && echo done",
            "git status; echo complete",
            "python3 -c 'print(\"cat docs/guide.md\")' || echo failed",
        ):
            with self.subTest(command=command):
                request = parse_payload(
                    {
                        "tool_name": "run_command",
                        "tool_input": {"command": command},
                    },
                    client="gemini",
                )
                self.assertFalse(request.unparseable)
                self.assertEqual(request.command_class, "other")
                self.assertIsNone(request.path)
                with tempfile.TemporaryDirectory() as directory:
                    with mock.patch.dict(
                        os.environ,
                        {"XDG_STATE_HOME": directory},
                        clear=False,
                    ):
                        result = evaluate_request(request)
                self.assertEqual(result.decision, "allow")
                self.assertEqual(result.reason_code, "no-file-read")

    def test_unparseable_compound_file_reads_warn_and_pass(self):
        request = parse_payload(
            {
                "tool_name": "run_command",
                "tool_input": {"command": "cat docs/a.md && cat docs/b.md"},
            },
            client="gemini",
        )
        self.assertTrue(request.unparseable)
        self.assertEqual(request.command_class, "compound")
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ,
                {"XDG_STATE_HOME": directory},
                clear=False,
            ):
                result = evaluate_request(request)
        self.assertEqual(result.decision, "warn")
        self.assertEqual(result.reason_code, "unparseable-compound-shell")

    def test_malformed_payload_fails_open_with_machine_readable_reason(self):
        output = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO("{")), redirect_stdout(output):
            return_code = main(["--client", "codex", "--json"])
        self.assertEqual(return_code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["decision"], "allow")
        self.assertEqual(result["reason_code"], "payload-parse-failed")

    def test_post_tool_payload_estimates_tokens_without_retaining_content(self):
        request = parse_payload(
            {
                "tool_name": "exec_command",
                "tool_response": {"output": "x" * 16_000},
            },
            client="codex",
            event="post_tool_use",
        )
        self.assertEqual(request.returned_tokens, 4_000)
        self.assertIsNone(request.path)
        self.assertIsNone(request.command)


if __name__ == "__main__":
    unittest.main()
