import json
import tempfile
import unittest
from pathlib import Path

from scripts.hook_fixture_runner import check_result, load_manifest, run_case


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

    def test_runner_executes_a_fixture_and_loads_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hook = root / "hook.sh"
            hook.write_text("#!/bin/sh\ncat >/dev/null\n", encoding="utf-8")
            hook.chmod(0o755)
            manifest = root / "fixtures.json"
            manifest.write_text(
                json.dumps([{"name": "smoke", "expect": "allow", "input": {}}]),
                encoding="utf-8",
            )

            cases = load_manifest(manifest)
            result = run_case(hook, cases[0])

        self.assertEqual(cases[0]["name"], "smoke")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(check_result(cases[0], result.returncode, result.stdout, result.stderr), [])


if __name__ == "__main__":
    unittest.main()
