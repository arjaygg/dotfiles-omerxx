import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.policy_decision import evaluate_gate, record_decision
from scripts.policy_proposal import build_review_report


def proposal() -> dict[str, object]:
    return {
        "id": "reviewable-example",
        "owner": "platform-team",
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
    def _write_review(self, root):
        proposal_path = root / "proposal.json"
        review_path = root / "review.json"
        proposal_path.write_text(json.dumps(proposal()), encoding="utf-8")
        review_path.write_text(
            json.dumps(
                build_review_report(proposal(), {"latency_ms": 100}, {"latency_ms": 90})
            ),
            encoding="utf-8",
        )
        return proposal_path, review_path

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
        self.assertEqual(entry["owner"], "platform-team")
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

    def test_record_rejects_malformed_existing_ledger_entry(self):
        with tempfile.TemporaryDirectory() as dir:
            root = Path(dir)
            proposal_path = root / "proposal.json"
            ledger_path = root / "decisions.jsonl"
            proposal_path.write_text(json.dumps(proposal()), encoding="utf-8")
            ledger_path.write_text(json.dumps({"applied": True}) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing fields"):
                record_decision(
                    proposal_path,
                    ledger_path,
                    decision="reject",
                    rationale="Rejecting malformed history.",
                    decided_at="2026-07-13",
                )

    def test_gate_requires_a_matching_human_decision(self):
        with tempfile.TemporaryDirectory() as dir:
            root = Path(dir)
            proposal_path, review_path = self._write_review(root)
            result = evaluate_gate(
                proposal_path,
                review_path,
                root / "decisions.jsonl",
                evaluated_at="2026-07-14",
            )
        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "no-matching-decision")
        self.assertFalse(result["auto_apply"])

    def test_gate_is_eligible_only_after_accept_and_never_auto_applies(self):
        with tempfile.TemporaryDirectory() as dir:
            root = Path(dir)
            proposal_path, review_path = self._write_review(root)
            ledger_path = root / "decisions.jsonl"
            record_decision(
                proposal_path,
                ledger_path,
                decision="accept",
                rationale="Reviewed metrics and risks.",
                decided_at="2026-07-13",
            )
            result = evaluate_gate(proposal_path, review_path, ledger_path, evaluated_at="2026-07-14")
        self.assertTrue(result["eligible"])
        self.assertEqual(result["promotion_status"], "eligible-review-gated")
        self.assertTrue(result["requires_explicit_apply"])
        self.assertFalse(result["auto_apply"])

    def test_gate_follows_latest_non_accept_decision(self):
        with tempfile.TemporaryDirectory() as dir:
            root = Path(dir)
            proposal_path, review_path = self._write_review(root)
            ledger_path = root / "decisions.jsonl"
            record_decision(proposal_path, ledger_path, decision="accept", rationale="Initial accept.", decided_at="2026-07-13")
            record_decision(proposal_path, ledger_path, decision="defer", rationale="Recheck risk.", decided_at="2026-07-14")
            result = evaluate_gate(proposal_path, review_path, ledger_path, evaluated_at="2026-07-15")
        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "latest-decision-not-accepted")

    def test_cli_gate_emits_machine_readable_review_gate(self):
        with tempfile.TemporaryDirectory() as dir:
            root = Path(dir)
            proposal_path, review_path = self._write_review(root)
            ledger_path = root / "decisions.jsonl"
            record_decision(proposal_path, ledger_path, decision="accept", rationale="Reviewed.", decided_at="2026-07-13")
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("policy_decision.py")),
                    str(proposal_path),
                    "--ledger",
                    str(ledger_path),
                    "--gate-review",
                    str(review_path),
                    "--evaluated-at",
                    "2026-07-14",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["eligible"])
        self.assertFalse(payload["auto_apply"])

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
