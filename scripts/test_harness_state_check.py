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
