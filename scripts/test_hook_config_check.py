import unittest

from scripts.hook_config_check import check_hooks, summarize_issues


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

    def test_reports_pre_tool_gate_without_mcp_matcher(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash|Read|Edit|Write",
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'bash "$HOME/.dotfiles/.claude/hooks/pre-tool-gate-v2.sh"',
                            }
                        ],
                    }
                ]
            }
        }

        issues = check_hooks(settings)

        self.assertEqual([issue.rule for issue in issues], ["missing-mcp-tool-matcher"])

    def test_accepts_pre_tool_gate_with_mcp_matcher(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash|Read|mcp__.*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'bash "$HOME/.dotfiles/.claude/hooks/pre-tool-gate-v2.sh"',
                            }
                        ],
                    }
                ]
            }
        }

        self.assertEqual(check_hooks(settings), [])

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

    def test_reports_multiple_pre_tool_rewriters_in_one_group(self):
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "bash rewrite-a.sh"},
                            {"type": "command", "command": "bash rewrite-b.sh"},
                        ],
                    }
                ]
            }
        }

        self.assertEqual(
            [issue.rule for issue in check_hooks(settings)],
            ["multiple-input-rewriters"],
        )

    def test_summary_counts_by_rule_and_event_without_messages(self):
        settings = {
            "hooks": {
                "Stop": [{"matcher": ".*", "hooks": [{"type": "command", "command": "bash stop.sh"}]}],
                "WorktreeCreate": [
                    {
                        "matcher": ".*",
                        "hooks": [
                            {"type": "command", "command": "bash create.sh"},
                            {"type": "command", "command": "bash bridge.sh"},
                        ],
                    }
                ],
            }
        }

        summary = summarize_issues(check_hooks(settings))

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["by_rule"], {"ignored-matcher": 2, "parallel-handlers": 1})
        self.assertEqual(summary["by_event"], {"Stop": 1, "WorktreeCreate": 2})
        self.assertNotIn("message", summary)


if __name__ == "__main__":
    unittest.main()
