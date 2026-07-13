import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude/hooks/scratchpad-reread-guard.sh"


class ScratchpadGuardTests(unittest.TestCase):
    session_id = "scratchpad-guard-unittest"
    log_path = Path(f"/tmp/.claude-scratchpad-reads-{os.getuid()}-{session_id}")

    def setUp(self):
        self.log_path.unlink(missing_ok=True)

    def tearDown(self):
        self.log_path.unlink(missing_ok=True)

    def run_hook(self, payload):
        return subprocess.run(
            ["bash", str(HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_first_scratchpad_read_is_silent(self):
        result = self.run_hook(
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "/tmp/scratchpad/fixture.md"},
                "session_id": self.session_id,
            }
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_second_scratchpad_read_returns_schema_valid_deny(self):
        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/scratchpad/fixture.md"},
            "session_id": self.session_id,
        }
        self.run_hook(payload)
        result = self.run_hook(payload)

        decision = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(decision["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("Already read", decision["hookSpecificOutput"]["permissionDecisionReason"])

    def test_non_read_tool_is_ignored(self):
        result = self.run_hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "/tmp/scratchpad/fixture.md"},
                "session_id": self.session_id,
            }
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
