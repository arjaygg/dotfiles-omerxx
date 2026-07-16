import json
import tempfile
import unittest
from pathlib import Path

from scripts.hook_fixture_runner import check_result, load_manifest, run_case, summarize_run


class HookFixtureRunnerTests(unittest.TestCase):
    def test_allow_result_is_accepted(self):
        failures = check_result({"expect": "allow"}, 0, "", "")

        self.assertEqual(failures, [])

    def test_deny_result_requires_structured_decision(self):
        stdout = json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": "blocked",
                }
            }
        )

        self.assertEqual(check_result({"expect": "deny"}, 0, stdout, ""), [])
        self.assertNotEqual(check_result({"expect": "deny"}, 0, "", ""), [])
        self.assertNotEqual(check_result({"expect": "deny"}, 0, f"noise\n{stdout}", ""), [])

    def test_ask_result_requires_ask_decision_and_reason(self):
        stdout = json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": "confirm risky command",
                }
            }
        )

        self.assertEqual(check_result({"expect": "ask"}, 0, stdout, ""), [])
        self.assertNotEqual(check_result({"expect": "ask"}, 0, "{}", ""), [])

    def test_rewrite_result_requires_allow_decision_and_updated_input(self):
        case = {
            "expect": "rewrite",
            "input": {"tool_input": {"command": "grep x", "description": "search"}},
            "expected_updated_input": {"command": "rg x"},
        }
        stdout = json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "permissionDecisionReason": "rewrite",
                    "updatedInput": {"command": "rg x", "description": "search"},
                }
            }
        )

        self.assertEqual(check_result(case, 0, stdout, ""), [])
        self.assertNotEqual(
            check_result(case, 0, stdout.replace('"description": "search"', '"other": true'), ""),
            [],
        )

    def test_context_result_requires_additional_context(self):
        stdout = json.dumps(
            {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "nudge"}}
        )

        self.assertEqual(check_result({"expect": "context", "event": "UserPromptSubmit"}, 0, stdout, ""), [])
        self.assertNotEqual(check_result({"expect": "context", "event": "UserPromptSubmit"}, 0, "{}", ""), [])

    def test_summarize_run_counts_cases_and_failures(self):
        cases = [{"name": "allow", "expect": "allow"}, {"name": "deny", "expect": "deny"}]
        failures = {"deny": ["deny fixture must emit JSON on stdout"]}

        self.assertEqual(
            summarize_run(cases, failures),
            {"total": 2, "passed": 1, "failed": 1, "failed_cases": ["deny"]},
        )

    def test_runner_executes_a_fixture_and_loads_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hook = root / "hook.sh"
            hook.write_text("#!/bin/sh\ncat >/dev/null\n", encoding="utf-8")
            hook.chmod(0o755)
            manifest = root / "fixtures.json"
            manifest.write_text(
                json.dumps(
                    [
                        {"name": "smoke", "expect": "allow", "input": {}},
                        {"name": "ask", "expect": "ask", "input": {}},
                    ]
                ),
                encoding="utf-8",
            )

            cases = load_manifest(manifest)
            result = run_case(hook, cases[0])

        self.assertEqual(cases[0]["name"], "smoke")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check_result(cases[0], result.returncode, result.stdout, result.stderr), [])


if __name__ == "__main__":
    unittest.main()
