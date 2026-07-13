import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.learning_signal import (
    SignalValidationError,
    record_signal,
    sanitize_signal,
)


ROOT = Path(__file__).resolve().parents[1]


def valid_signal() -> dict[str, object]:
    return {
        "signal_id": "sig-001",
        "signal_type": "hook_block",
        "occurred_at": "2026-07-13T12:00:00Z",
        "session_ref": "private-session-123",
        "event_ref": "private-event-456",
        "recurrence_key": "hook:block:grep",
        "evidence_class": "recurrence",
        "recurrence_count": 2,
    }


class LearningSignalTests(unittest.TestCase):
    def test_sanitizes_private_references_and_forbids_promotion(self):
        sanitized = sanitize_signal(valid_signal())

        self.assertEqual(sanitized["schema"], 1)
        self.assertEqual(sanitized["signal_id"], "sig-001")
        self.assertNotIn("private-session-123", json.dumps(sanitized))
        self.assertNotIn("private-event-456", json.dumps(sanitized))
        self.assertEqual(len(sanitized["session_ref_sha256"]), 64)
        self.assertEqual(len(sanitized["event_ref_sha256"]), 64)
        self.assertFalse(sanitized["raw_evidence_stored"])
        self.assertFalse(sanitized["auto_promote"])
        self.assertEqual(sanitized["promotion_status"], "review-required")

    def test_rejects_raw_transcripts_private_context_and_unknown_fields(self):
        for field in ("transcript", "prompt", "output", "private_context", "details"):
            candidate = valid_signal()
            candidate[field] = "must not be persisted"
            with self.subTest(field=field), self.assertRaises(SignalValidationError):
                sanitize_signal(candidate)

    def test_rejects_invalid_signal_type_timestamp_and_recurrence(self):
        cases = [
            ("signal_type", "unknown"),
            ("occurred_at", "not-a-timestamp"),
            ("recurrence_count", 0),
        ]
        for field, value in cases:
            candidate = valid_signal()
            candidate[field] = value
            with self.subTest(field=field), self.assertRaises(SignalValidationError):
                sanitize_signal(candidate)

    def test_records_atomically_only_to_an_explicit_external_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repo = temporary / "repo"
            repo.mkdir()
            ledger = temporary / "signals.jsonl"

            result = record_signal(repo, ledger, valid_signal())

            self.assertEqual(result["signal_id"], "sig-001")
            lines = ledger.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0]), result)
            with self.assertRaises(SignalValidationError):
                record_signal(repo, ledger, valid_signal())
            with self.assertRaises(SignalValidationError):
                record_signal(repo, repo / "signals.jsonl", valid_signal())

    def test_cli_outputs_sanitized_record_and_never_raw_input(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repo = temporary / "repo"
            repo.mkdir()
            input_path = temporary / "signal.json"
            input_path.write_text(json.dumps(valid_signal()), encoding="utf-8")
            ledger = temporary / "signals.jsonl"

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/learning_signal.py"),
                    "--root",
                    str(repo),
                    "--input",
                    str(input_path),
                    "--ledger",
                    str(ledger),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("private-session-123", result.stdout)
        self.assertEqual(json.loads(result.stdout)["promotion_status"], "review-required")


if __name__ == "__main__":
    unittest.main()
