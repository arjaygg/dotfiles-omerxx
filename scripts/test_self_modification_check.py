import tempfile
import unittest
from pathlib import Path

from scripts.self_modification_check import check_self_modification, summarize_issues


class SelfModificationCheckTests(unittest.TestCase):
    def test_reports_tracked_hook_policy_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hook = root / ".claude/hooks/hook-graduate.sh"
            hook.parent.mkdir(parents=True)
            hook.write_text(
                "STATE_FILE=\"${SCRIPT_DIR}/hook-graduation-state.json\"\n"
                "sed -i '' 's/a/b/' \"${SCRIPT_DIR}/hook-config.yaml\"\n"
                "jq '.x=1' \"$STATE_FILE\" > \"${STATE_FILE}.tmp\" && mv \"${STATE_FILE}.tmp\" \"$STATE_FILE\"\n",
                encoding="utf-8",
            )

            issues = check_self_modification(root)

        self.assertEqual(summarize_issues(issues)["total"], 2)
        self.assertEqual(
            summarize_issues(issues)["by_target"],
            {"hook-config.yaml": 1, "hook-graduation-state.json": 1},
        )

    def test_ignores_detect_only_settings_guard(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hook = root / ".claude/hooks/settings-symlink-guard.sh"
            hook.parent.mkdir(parents=True)
            hook.write_text(
                "SRC=\"$HOME/.dotfiles/.claude/settings.json\"\n"
                "warn \"not auto-syncing or relinking; review manually\"\n",
                encoding="utf-8",
            )

            issues = check_self_modification(root)

        self.assertEqual(issues, [])

    def test_current_repo_self_modification_baseline_is_reportable(self):
        root = Path(__file__).resolve().parents[1]
        issues = check_self_modification(root)
        summary = summarize_issues(issues)

        self.assertGreaterEqual(summary["total"], 2)
        self.assertIn("hook-graduate.sh", next(iter(summary["by_path"])))


if __name__ == "__main__":
    unittest.main()
