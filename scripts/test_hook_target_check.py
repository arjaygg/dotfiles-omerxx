import json
import tempfile
import unittest
from pathlib import Path

from scripts.hook_target_check import check_hook_targets, summarize_issues


def write_settings(path: Path, command: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": command}]}]}}),
        encoding="utf-8",
    )


class HookTargetCheckTests(unittest.TestCase):
    def test_reports_missing_dotfiles_hook_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            settings = root / ".claude/settings.json"
            write_settings(settings, 'bash "$HOME/.dotfiles/.claude/hooks/missing.sh"')

            issues = check_hook_targets(settings, root)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "missing-target")

    def test_reports_direct_non_executable_dotfiles_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hook = root / ".claude/hooks/direct.sh"
            hook.parent.mkdir(parents=True)
            hook.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            settings = root / ".claude/settings.json"
            write_settings(settings, "$HOME/.dotfiles/.claude/hooks/direct.sh")

            issues = check_hook_targets(settings, root)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "direct-target-not-executable")

    def test_accepts_bash_invoked_non_executable_target_and_direct_executable_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hook = root / ".claude/hooks/hook.sh"
            hook.parent.mkdir(parents=True)
            hook.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            settings = root / ".claude/settings.json"
            write_settings(settings, 'bash "$HOME/.dotfiles/.claude/hooks/hook.sh"')
            self.assertEqual(check_hook_targets(settings, root), [])

            hook.chmod(0o755)
            write_settings(settings, "$HOME/.dotfiles/.claude/hooks/hook.sh")
            self.assertEqual(check_hook_targets(settings, root), [])

    def test_current_repo_hook_targets_pass(self):
        root = Path(__file__).resolve().parents[1]
        issues = check_hook_targets(root / ".claude/settings.json", root)

        self.assertEqual(summarize_issues(issues)["total"], 0)


if __name__ == "__main__":
    unittest.main()
