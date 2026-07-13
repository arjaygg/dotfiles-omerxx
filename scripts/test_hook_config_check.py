import json
import tempfile
import unittest
from pathlib import Path

from scripts.hook_config_check import Issue, check_hooks, compare_baseline, load_baseline


class HookConfigCheckTests(unittest.TestCase):
    def test_valid_tool_hook_group_has_no_issues(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash|Edit",
                        "hooks": [{"type": "command", "command": "bash hook.sh"}],
                    }
                ]
            }
        }

        self.assertEqual(check_hooks(settings), [])

    def test_reports_ignored_matcher_on_event_without_matcher_support(self):
        settings = {
            "hooks": {
                "Stop": [
                    {
                        "matcher": ".*",
                        "hooks": [{"type": "command", "command": "bash stop.sh"}],
                    }
                ]
            }
        }

        issues = check_hooks(settings)

        self.assertEqual([issue.rule for issue in issues], ["ignored-matcher"])

    def test_reports_parallel_worktree_handlers(self):
        settings = {
            "hooks": {
                "WorktreeCreate": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {"type": "command", "command": "bash create.sh"},
                            {"type": "command", "command": "bash bridge.sh"},
                        ],
                    }
                ]
            }
        }

        issues = check_hooks(settings)

        self.assertEqual([issue.rule for issue in issues], ["ignored-matcher", "parallel-handlers"])

    def test_reports_unknown_events_and_malformed_handlers(self):
        settings = {
            "hooks": {
                "NotAnEvent": [{"hooks": [{"type": "command"}]}],
                "PostToolUse": [
                    {
                        "hooks": [
                            {"type": "unknown", "command": "ignored"},
                            {"type": "command", "command": 3},
                        ]
                    }
                ],
            }
        }

        self.assertEqual(
            [issue.rule for issue in check_hooks(settings)],
            ["unknown-event", "missing-command", "unknown-handler-type", "invalid-command"],
        )

    def test_accepts_each_handler_type_with_required_fields(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {"type": "command", "command": "bash hook.sh"},
                            {"type": "http", "url": "https://hooks.example.test/check"},
                            {"type": "mcp_tool", "server": "policy", "tool": "check"},
                            {"type": "prompt", "prompt": "Evaluate $ARGUMENTS"},
                            {"type": "agent", "prompt": "Verify $ARGUMENTS"},
                        ]
                    }
                ]
            }
        }

        self.assertEqual(check_hooks(settings), [])

    def test_reports_missing_and_invalid_handler_fields(self):
        settings = {
            "hooks": {
                "PostToolUse": [
                    {
                        "hooks": [
                            {"type": "http"},
                            {"type": "mcp_tool", "server": "policy"},
                            {"type": "prompt", "prompt": 3},
                            {"type": "agent"},
                        ]
                    }
                ]
            }
        }

        self.assertEqual(
            [issue.rule for issue in check_hooks(settings)],
            [
                "missing-url",
                "missing-tool",
                "invalid-prompt",
                "missing-prompt",
            ],
        )

    def test_matching_baseline_has_no_findings(self):
        issue = Issue("PreToolUse", "parallel-handlers", "ordering is not guaranteed")

        self.assertEqual(compare_baseline([issue], [issue]), [])

    def test_baseline_reports_new_and_missing_findings(self):
        expected = [Issue("PreToolUse", "ignored-matcher", "matcher is ignored")]
        actual = [Issue("PreToolUse", "parallel-handlers", "ordering is not guaranteed")]

        findings = compare_baseline(actual, expected)

        self.assertEqual([issue.rule for issue in findings], ["baseline-missing", "baseline-new"])

    def test_load_baseline_rejects_malformed_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text(json.dumps([{"event": "PreToolUse"}]), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "event, rule, and message"):
                load_baseline(path)


if __name__ == "__main__":
    unittest.main()
