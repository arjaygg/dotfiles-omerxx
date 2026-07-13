import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.permission_hook_conflicts import check_conflicts


ROOT = Path(__file__).resolve().parents[1]


class PermissionHookConflictTests(unittest.TestCase):
    def test_exact_allow_deny_conflict_is_reported(self):
        settings = {
            "permissions": {"allow": ["Bash(git status *)"], "deny": ["Bash(git status *)"]},
            "hooks": {},
        }

        conflicts = check_conflicts(settings)

        self.assertEqual([conflict.rule for conflict in conflicts], ["permission-conflict"])

    def test_exact_tool_hook_under_permission_deny_is_reported(self):
        settings = {
            "permissions": {"deny": ["Bash(git push *)"]},
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash(git push *)", "hooks": [{"type": "command", "command": "check.sh"}]}
                ]
            },
        }

        conflicts = check_conflicts(settings)

        self.assertEqual([conflict.rule for conflict in conflicts], ["hook-unreachable-under-deny"])

    def test_unrelated_permissions_and_hooks_have_no_conflict(self):
        settings = {
            "permissions": {"allow": ["Bash(git status *)"], "deny": ["Bash(git push *)"]},
            "hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": "check.sh"}]}]},
        }

        self.assertEqual(check_conflicts(settings), [])

    def test_cli_reports_json_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps({"permissions": {"allow": ["Read"], "deny": ["Read"]}, "hooks": {}}),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/permission_hook_conflicts.py"), str(path), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)[0]["rule"], "permission-conflict")


if __name__ == "__main__":
    unittest.main()
