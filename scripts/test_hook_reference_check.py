import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.hook_reference_check import Issue, check_settings, compare_baseline, extract_file_references, load_baseline


ROOT = Path(__file__).resolve().parents[1]


class HookReferenceCheckTests(unittest.TestCase):
    def test_current_settings_have_no_missing_file_backed_references(self):
        settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))

        self.assertEqual(check_settings(settings, ROOT), [])

    def test_extractor_ignores_runtime_commands_and_keeps_file_backed_paths(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {"type": "command", "command": "bash \"$HOME/.dotfiles/.claude/hooks/example.sh\""},
                            {"type": "command", "command": "bash -lc 'lean-ctx hook redirect'"},
                        ]
                    }
                ]
            }
        }

        self.assertEqual(extract_file_references(settings), [("PreToolUse", ".claude/hooks/example.sh")])

    def test_missing_reference_is_reported(self):
        settings = {"hooks": {"SessionStart": [{"hooks": [{"command": "$HOME/.dotfiles/.claude/hooks/missing.sh"}]}]}}

        issues = check_settings(settings, ROOT)

        self.assertEqual(issues, [Issue("SessionStart", ".claude/hooks/missing.sh", "missing-file", "file-backed hook command does not resolve in the tracked distribution")])

    def test_baseline_reports_new_and_missing_findings(self):
        actual = [Issue("PreToolUse", "a.sh", "missing-file", "missing")]
        expected = [Issue("SessionStart", "b.sh", "missing-file", "missing")]

        differences = compare_baseline(actual, expected)

        self.assertEqual({issue.rule for issue in differences}, {"baseline-new", "baseline-missing"})

    def test_baseline_rejects_invalid_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text(json.dumps([{"event": "PreToolUse"}]), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "requires event"):
                load_baseline(path)

    def test_cli_passes_empty_reviewed_baseline(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/hook_reference_check.py"),
                str(ROOT / ".claude/settings.json"),
                "--root",
                str(ROOT),
                "--baseline",
                str(ROOT / "scripts/fixtures/hook-reference-baseline.json"),
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])


if __name__ == "__main__":
    unittest.main()
