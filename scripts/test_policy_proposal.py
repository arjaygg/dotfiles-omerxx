import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.policy_proposal import build_review_report, validate_proposal


ROOT = Path(__file__).resolve().parents[1]


def valid_proposal(**overrides):
    value = {
        "id": "prefer-explicit-overlays",
        "owner": "platform-team",
        "problem": "Runtime settings drift from portable source.",
        "evidence": ["session-a: runtime drift detected", "session-b: same drift detected"],
        "recurrence": 2,
        "current_behavior": "The doctor reports drift after startup.",
        "proposed_destination": "skill",
        "proposed_change": "Add a review-only drift workflow.",
        "expected_effect": "Reduce repeated manual drift diagnosis.",
        "risks": "Users may confuse proposals with applied changes.",
        "conflicts": "None known.",
        "context_cost": "Adds one on-demand skill.",
        "evaluation": "Compare baseline and candidate doctor runs.",
        "review_after": "2026-10-01",
        "evidence_class": "recurrence",
    }
    value.update(overrides)
    return value


class PolicyProposalTests(unittest.TestCase):
    def test_valid_proposal_has_no_errors(self):
        self.assertEqual(validate_proposal(valid_proposal()), [])

    def test_required_fields_and_destination_are_enforced(self):
        value = valid_proposal()
        del value["evaluation"]

        errors = validate_proposal(value)

        self.assertIn("missing required field: evaluation", errors)
        invalid_destination = validate_proposal(valid_proposal(proposed_destination="canonical-policy"))
        self.assertIn("unsupported proposed_destination: canonical-policy", invalid_destination)

    def test_unknown_fields_are_rejected(self):
        errors = validate_proposal(valid_proposal(unreviewed_instruction="apply this automatically"))
        self.assertIn("unsupported field: unreviewed_instruction", errors)

    def test_recurrence_threshold_requires_two_observations(self):
        errors = validate_proposal(valid_proposal(recurrence=1, evidence_class="recurrence"))

        self.assertIn("recurrence evidence requires recurrence >= 2", errors)

    def test_strong_evidence_can_qualify_once_but_auto_promotion_is_rejected(self):
        value = valid_proposal(recurrence=1, evidence_class="security", auto_promote=True)

        errors = validate_proposal(value)

        self.assertEqual(errors, ["auto_promote must not be true"])

    def test_review_after_accepts_date_or_named_condition(self):
        self.assertEqual(validate_proposal(valid_proposal(review_after="2026-10-01")), [])
        self.assertEqual(validate_proposal(valid_proposal(review_after="condition: after next quarterly eval")), [])

    def test_review_after_rejects_unstructured_expiry_text(self):
        errors = validate_proposal(valid_proposal(review_after="sometime later"))

        self.assertIn("review_after must be an ISO date or condition:<description>", errors)

    def test_owner_is_required_and_portable(self):
        self.assertEqual(validate_proposal(valid_proposal(owner="platform-team")), [])
        errors = validate_proposal(valid_proposal(owner="../private-owner"))
        self.assertIn("owner must use portable owner characters and be at most 128 characters", errors)

    def test_review_report_compares_baseline_and_candidate_metrics(self):
        report = build_review_report(
            valid_proposal(),
            {"latency_ms": 100, "tests_passed": 10},
            {"latency_ms": 80, "tests_passed": 10},
        )

        self.assertEqual(report["owner"], "platform-team")
        self.assertEqual(report["decision"], "review-required")
        self.assertFalse(report["auto_promote"])
        self.assertEqual(report["evaluation"]["status"], "changed")
        self.assertEqual(report["evaluation"]["metrics"]["latency_ms"]["delta"], -20)

    def test_review_report_rejects_mismatched_metric_sets(self):
        with self.assertRaisesRegex(ValueError, "metric names must match"):
            build_review_report(valid_proposal(), {"latency_ms": 100}, {"tests_passed": 10})

    def test_review_report_rejects_non_numeric_metric_values(self):
        with self.assertRaisesRegex(ValueError, "finite numbers"):
            build_review_report(valid_proposal(), {"latency_ms": "100"}, {"latency_ms": 80})

    def test_cli_returns_nonzero_for_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            proposal = Path(directory) / "proposal.json"
            proposal.write_text(json.dumps(valid_proposal(recurrence=1)), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/policy_proposal.py"), "validate", str(proposal)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("recurrence evidence requires recurrence >= 2", result.stdout)

    def test_review_cli_emits_human_review_required_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proposal = root / "proposal.json"
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            proposal.write_text(json.dumps(valid_proposal()), encoding="utf-8")
            baseline.write_text(json.dumps({"latency_ms": 100}), encoding="utf-8")
            candidate.write_text(json.dumps({"latency_ms": 90}), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/policy_proposal.py"),
                    "review",
                    str(proposal),
                    "--baseline",
                    str(baseline),
                    "--candidate",
                    str(candidate),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["decision"], "review-required")
        self.assertFalse(report["auto_promote"])


if __name__ == "__main__":
    unittest.main()
