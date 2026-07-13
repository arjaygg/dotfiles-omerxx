import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.policy_decision import record_decision


def proposal() -> dict[str, object]:
    return {
        "id": "reviewable-example",
        "problem": "A repeated workflow needs review.",
        "evidence": ["session-a", "session-b"],
        "recurrence": 2,
        "current_behavior": "The workflow repeats.",
        "proposed_destination": "skill",
        "proposed_change": "Add a documented skill.",
        "expected_effect": "Reduce repeated work.",
        "risks": "The skill could be too broad.",
        "conflicts": "None known.",
        "context_cost": "On-demand only.",
        "evaluation": "Compare baseline and candidate metrics.",
        "review_after": "2026-10-01",
        "evidence_class": "recurrence",
    }


class PolicyDecisionTests(unittest.TestCase):
    def test_record_writes_hash_only_decision_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proposal_path = root / "proposal.json"
            ledger_path = root / "decisions.jsonl"
            proposal_path.write_text(json.dumps(proposal()), encoding="utf-8")

            entry = record_decision(
                proposal_path,
                ledger_path,
                decision="reject",
                rationale="Insufficient evidence for the proposed destination.",
                decided_at="2026-07-13",
            )

            stored = json.loads(ledger_path.read_text(encoding="utf-8"))

        self.assertEqual(stored, entry)
        self.assertEqual(entry["decision"], "reject")
        self.assertNotIn("evidence", entry)
        self.assertRegex(entry["proposal_sha256"], r"^[0-9a-f]{64}$")

    def test_record_appends_distinct_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proposal_path = root / "proposal.json"
            ledger_path = root / "decisions.jsonl"
            proposal_path.write_text(json.dumps(proposal()), encoding="utf-8")
            record_decision(proposal_path, ledger_path, decision="defer", rationale="Needs eval.", decided_at="2026-07-13")
            record_decision(proposal_path, ledger_path, decision="reject", rationale="Still insufficient.", decided_at="2026-07-14")

            lines = ledger_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 2)

    def test_record_rejects_empty_rationale_and_invalid_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proposal_path = root / "proposal.json"
            ledger_path = root / "decisions.jsonl"
            proposal_path.write_text(json.dumps(proposal()), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "rationale"):
                record_decision(proposal_path, ledger_path, decision="reject", rationale=" ", decided_at="2026-07-13")
            with self.assertRaisesRegex(ValueError, "decision"):
                record_decision(proposal_path, ledger_path, decision="promote", rationale="reason", decided_at="2026-07-13")

    def test_record_rejects_accept_after_review_deadline(self):
        with tempfile.TemporaryDirectory() as dir:
            root = Path(dir)
            proposal_path = root / "proposal.json"
            ledger_path = root / "decisions.jsonl"
            expired = proposal() | {"review_after": "2026-07-12"}
            proposal_path.write_text(json.dumps(expired), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "past the proposal review deadline"):
                record_decision(
                    proposal_path,
                    ledger_path,
                    decision="accept",
                    rationale="Accepting after review.",
                    decided_at="2026-07-13",
                )

    def test_cli_records_explicit_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proposal_path = root / "proposal.json"
            ledger_path = root / "decisions.jsonl"
            proposal_path.write_text(json.dumps(proposal()), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("policy_decision.py")),
                    str(proposal_path),
                    "--ledger",
                    str(ledger_path),
                    "--decision",
                    "reject",
                    "--rationale",
                    "Needs more evidence.",
                    "--decided-at",
                    "2026-07-13",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["recorded"]["applied"], False)


if __name__ == "__main__":
    unittest.main()
