import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.hook_event_matrix import Issue, check_matrix, load_matrix, settings_events


ROOT = Path(__file__).resolve().parents[1]


class HookEventMatrixTests(unittest.TestCase):
    def test_current_settings_have_representative_coverage(self):
        settings = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8"))
        cases = load_matrix(ROOT / "scripts/fixtures/hook-event-matrix.json")

        self.assertEqual(check_matrix(settings, cases), [])
        self.assertEqual(len(settings_events(settings)), 14)

    def test_missing_and_stale_events_are_reported(self):
        settings = {"hooks": {"SessionStart": [], "Stop": []}}
        cases = [{"event": "SessionStart", "payload": {"session_id": "fixture"}, "required": []}, {"event": "OldEvent", "payload": {"value": True}, "required": []}]

        issues = check_matrix(settings, cases)

        self.assertEqual(
            issues,
            [
                Issue("Stop", "missing-event", "configured hook event has no representative payload"),
                Issue("OldEvent", "stale-event", "matrix event is not configured in settings"),
            ],
        )

    def test_matrix_rejects_duplicate_events_and_missing_required_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(
                json.dumps(
                    [
                        {"event": "PreToolUse", "required": ["tool_name"], "payload": {}},
                        {"event": "PreToolUse", "required": [], "payload": {"tool_name": "Bash"}},
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "payload must be"):
                load_matrix(path)

    def test_matrix_rejects_duplicate_after_payload_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.json"
            path.write_text(
                json.dumps(
                    [
                        {"event": "PreToolUse", "required": [], "payload": {"tool_name": "Bash"}},
                        {"event": "PreToolUse", "required": [], "payload": {"tool_name": "Read"}},
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_matrix(path)

    def test_cli_passes_current_matrix(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/hook_event_matrix.py"),
                str(ROOT / ".claude/settings.json"),
                str(ROOT / "scripts/fixtures/hook-event-matrix.json"),
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
