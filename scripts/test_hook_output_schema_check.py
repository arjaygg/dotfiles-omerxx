import tempfile
import unittest
from pathlib import Path

from scripts.hook_output_schema_check import check_hook_outputs, summarize_issues


class HookOutputSchemaCheckTests(unittest.TestCase):
    def test_reports_permission_decision_without_hook_event_name(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hook = root / "task-gate.sh"
            hook.write_text(
                "jq -n --arg reason \"$MSG\" "
                "'{\"hookSpecificOutput\":{\"permissionDecision\":\"deny\","
                "\"permissionDecisionReason\":$reason}}'\n",
                encoding="utf-8",
            )

            issues = check_hook_outputs(root)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "permission-decision-missing-hook-event-name")

    def test_accepts_complete_permission_context_and_rewrite_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "deny.sh").write_text(
                "'{hookSpecificOutput:{hookEventName:\"PreToolUse\","
                "permissionDecision:\"deny\",permissionDecisionReason:$r}}'\n",
                encoding="utf-8",
            )
            (root / "context.py").write_text(
                'print({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", '
                '"additionalContext": msg}})\n',
                encoding="utf-8",
            )
            (root / "rewrite.sh").write_text(
                '"hookSpecificOutput": {\n'
                '  "hookEventName": "PreToolUse",\n'
                '  "permissionDecision": "allow",\n'
                '  "updatedInput": $updated\n'
                "}\n",
                encoding="utf-8",
            )

            issues = check_hook_outputs(root)

        self.assertEqual(issues, [])

    def test_reports_updated_input_without_allow(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "rewrite.sh").write_text(
                '"hookSpecificOutput": {\n'
                '  "hookEventName": "PreToolUse",\n'
                '  "updatedInput": $updated\n'
                "}\n",
                encoding="utf-8",
            )

            issues = check_hook_outputs(root)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule, "updated-input-not-explicitly-allowed")

    def test_current_hook_output_schema_baseline_is_reportable(self):
        root = Path(__file__).resolve().parents[1] / ".claude/hooks"
        issues = check_hook_outputs(root)
        summary = summarize_issues(issues)

        self.assertGreaterEqual(summary["total"], 1)
        self.assertIn("permission-decision-missing-hook-event-name", summary["by_rule"])


if __name__ == "__main__":
    unittest.main()
