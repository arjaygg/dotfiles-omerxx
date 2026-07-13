import unittest

from scripts.hook_config_check import check_hooks


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


if __name__ == "__main__":
    unittest.main()
