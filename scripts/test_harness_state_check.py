import json
import tempfile
import unittest
from pathlib import Path

from scripts.harness_state_check import (
    DISABLED_SENTINELS,
    ENABLED_REQUIRED_FILES,
    check_harness_state,
)


def write(path: Path, text: str = "ok\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_disabled_repo(root: Path) -> None:
    marker = root / ".harness-disabled"
    marker.mkdir()
    for relative in DISABLED_SENTINELS:
        text = (
            "AI coding-agent harness disabled.\n"
            "Run scripts/ai-harness-toggle.sh enable to restore it.\n"
            if relative == "README.txt"
            else "archived\n"
        )
        write(marker / relative, text)
    (root / ".claude/claude-statusline").mkdir(parents=True)


def make_enabled_repo(root: Path) -> None:
    for relative in ENABLED_REQUIRED_FILES:
        write(root / relative)


def cursor_statusline_config(root: Path, command: object | None = None) -> dict[str, object]:
    script = root / ".cursor/cursor-statusline/statusline.sh"
    return {
        "permissions": {"allow": [], "deny": []},
        "statusLine": {
            "type": "command",
            "command": str(script) if command is None else command,
            "padding": 2,
            "updateIntervalMs": 1000,
            "timeoutMs": 2000,
        },
    }


def add_local_cursor_statusline(root: Path) -> None:
    script = root / ".cursor/cursor-statusline/statusline.sh"
    write(script, "#!/usr/bin/env bash\n")
    script.chmod(0o755)
    write(root / ".cursor/cli-config.json", json.dumps(cursor_statusline_config(root)) + "\n")


def add_tdd_guard_results(root: Path) -> None:
    write(root / ".claude/tdd-guard/data/test.json", "{}\n")


class HarnessStateCheckTests(unittest.TestCase):
    def test_valid_disabled_layout_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_disabled_repo(root)

            state, results = check_harness_state(root)

        self.assertEqual(state, "disabled")
        self.assertFalse([result for result in results if result.status == "fail"])

    def test_marker_only_is_inconsistent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".harness-disabled").mkdir()

            state, results = check_harness_state(root)

        self.assertEqual(state, "inconsistent")
        self.assertIn(
            ("disabled-archive-sentinel", "README.txt", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_symlink_marker_is_inconsistent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "archive"
            target.mkdir()
            (root / ".harness-disabled").symlink_to(target, target_is_directory=True)

            state, results = check_harness_state(root)

        self.assertEqual(state, "inconsistent")
        self.assertEqual(results[0].rule, "disabled-marker")
        self.assertEqual(results[0].status, "fail")

    def test_active_claude_hook_is_inconsistent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_disabled_repo(root)
            write(root / ".claude/hooks/pre-tool-gate-v2.sh")

            state, results = check_harness_state(root)

        self.assertEqual(state, "inconsistent")
        self.assertIn(
            ("disabled-claude-allowed-path", ".claude/hooks", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_exact_local_cursor_statusline_and_tdd_results_are_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_disabled_repo(root)
            add_local_cursor_statusline(root)
            add_tdd_guard_results(root)

            state, results = check_harness_state(root)

        self.assertEqual(state, "disabled")
        self.assertFalse([result for result in results if result.status == "fail"])

    def test_cursor_rules_or_symlinked_statusline_are_inconsistent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_disabled_repo(root)
            add_local_cursor_statusline(root)
            write(root / ".cursor/rules.md")
            (root / ".cursor/cursor-statusline/statusline.sh").unlink()
            (root / ".cursor/cursor-statusline/statusline.sh").symlink_to(root / "outside")

            state, results = check_harness_state(root)

        self.assertEqual(state, "inconsistent")
        failures = {(result.rule, result.path) for result in results if result.status == "fail"}
        self.assertIn(("disabled-cursor-allowed-path", ".cursor/rules.md"), failures)
        self.assertIn(
            ("disabled-cursor-statusline-path", ".cursor/cursor-statusline/statusline.sh"),
            failures,
        )

    def test_cursor_statusline_configuration_is_complete_and_strict(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_disabled_repo(root)
            (root / ".cursor").mkdir()

            state, results = check_harness_state(root)
            self.assertEqual(state, "inconsistent")
            self.assertIn(
                ("disabled-cursor-allowed-path", ".cursor/cli-config.json", "fail"),
                [(result.rule, result.path, result.status) for result in results],
            )

            add_local_cursor_statusline(root)
            write(
                root / ".cursor/cli-config.json",
                """{
                  "permissions": {"allow": [], "deny": []},
                  "statusLine": {
                    "type": "command",
                    "command": "bash .harness-disabled/repo/.claude/hooks/pre-tool-gate-v2.sh",
                    "padding": 2,
                    "updateIntervalMs": 1000,
                    "timeoutMs": 2000
                  }
                }\n""",
            )

            state, results = check_harness_state(root)
            self.assertEqual(state, "inconsistent")
            self.assertIn(
                ("disabled-cursor-config", ".cursor/cli-config.json", "fail"),
                [(result.rule, result.path, result.status) for result in results],
            )

            for invalid_command in (1, [], {}, False, "~definitely_no_such_username/statusline.sh"):
                with self.subTest(command=invalid_command):
                    write(
                        root / ".cursor/cli-config.json",
                        json.dumps(cursor_statusline_config(root, invalid_command)) + "\n",
                    )
                    state, results = check_harness_state(root)
                    self.assertEqual(state, "inconsistent")
                    self.assertIn(
                        ("disabled-cursor-config", ".cursor/cli-config.json", "fail"),
                        [(result.rule, result.path, result.status) for result in results],
                    )

            write(
                root / ".cursor/cli-config.json",
                """{
                  "permissions": {"allow": [], "deny": []},
                  "permissions": {"allow": [], "deny": []},
                  "statusLine": NaN
                }\n""",
            )
            state, results = check_harness_state(root)

        self.assertEqual(state, "inconsistent")
        self.assertIn(
            ("disabled-cursor-config", ".cursor/cli-config.json", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_tdd_guard_permits_only_exact_results_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_disabled_repo(root)
            add_tdd_guard_results(root)
            write(root / ".claude/tdd-guard/hook.sh")
            (root / ".claude/tdd-guard/data/test.json").unlink()
            (root / ".claude/tdd-guard/data/test.json").symlink_to(root / "outside")

            state, results = check_harness_state(root)

        self.assertEqual(state, "inconsistent")
        failures = {(result.rule, result.path) for result in results if result.status == "fail"}
        self.assertIn(("disabled-tdd-guard-path", ".claude/tdd-guard/hook.sh"), failures)
        self.assertIn(
            ("disabled-tdd-guard-data-path", ".claude/tdd-guard/data/test.json"),
            failures,
        )

    def test_tdd_guard_results_data_must_be_non_executable_json_object(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_disabled_repo(root)
            add_tdd_guard_results(root)
            write(root / ".claude/tdd-guard/data/test.json", "[]\n")

            state, results = check_harness_state(root)
            self.assertEqual(state, "inconsistent")
            self.assertIn(
                (
                    "disabled-tdd-guard-results-data",
                    ".claude/tdd-guard/data/test.json",
                    "fail",
                ),
                [(result.rule, result.path, result.status) for result in results],
            )

            write(root / ".claude/tdd-guard/data/test.json", "{\"result\": NaN}\n")
            state, results = check_harness_state(root)
            self.assertEqual(state, "inconsistent")
            self.assertIn(
                (
                    "disabled-tdd-guard-results-data",
                    ".claude/tdd-guard/data/test.json",
                    "fail",
                ),
                [(result.rule, result.path, result.status) for result in results],
            )

            write(root / ".claude/tdd-guard/data/test.json", "{}\n")
            (root / ".claude/tdd-guard/data/test.json").chmod(0o755)
            state, results = check_harness_state(root)

        self.assertEqual(state, "inconsistent")
        self.assertIn(
            (
                "disabled-tdd-guard-results-data",
                ".claude/tdd-guard/data/test.json",
                "fail",
            ),
            [(result.rule, result.path, result.status) for result in results],
        )

    def test_archive_and_active_symlinks_are_inconsistent_without_following_them(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_disabled_repo(root)
            archive = root / ".harness-disabled/repo"
            target = root / "outside"
            archive.rename(target)
            archive.symlink_to(target, target_is_directory=True)
            (root / "ai").symlink_to(root / "missing")

            state, results = check_harness_state(root)

        self.assertEqual(state, "inconsistent")
        failures = {(result.rule, result.path) for result in results if result.status == "fail"}
        self.assertIn(("disabled-archive-directory", "repo"), failures)
        self.assertIn(("disabled-absent-path", "ai"), failures)

    def test_valid_enabled_layout_passes_and_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_enabled_repo(root)

            state, results = check_harness_state(root)
            self.assertEqual(state, "enabled")
            self.assertFalse([result for result in results if result.status == "fail"])

            (root / "ai/config/manifest.json").unlink()
            state, results = check_harness_state(root)

        self.assertEqual(state, "inconsistent")
        self.assertIn(
            ("enabled-required-file", "ai/config/manifest.json", "fail"),
            [(result.rule, result.path, result.status) for result in results],
        )


if __name__ == "__main__":
    unittest.main()
