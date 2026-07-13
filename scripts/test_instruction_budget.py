import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.instruction_budget import check_budget, measure_file


ROOT = Path(__file__).resolve().parents[1]


class InstructionBudgetTests(unittest.TestCase):
    def test_measurement_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guidance.md"
            path.write_text("one two\nthree\n", encoding="utf-8")

            first = measure_file(path)
            second = measure_file(path)

        self.assertEqual(first, second)
        self.assertEqual(first.lines, 2)
        self.assertEqual(first.words, 3)
        self.assertEqual(first.bytes, len(b"one two\nthree\n"))

    def test_budget_reports_sorted_threshold_violations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            small = root / "a.md"
            large = root / "b.md"
            small.write_text("one\n", encoding="utf-8")
            large.write_text("one two three\nfour five six\n", encoding="utf-8")

            violations = check_budget([large, small], max_lines=1, max_words=3)

        self.assertEqual([violation.path for violation in violations], [str(large), str(large)])
        self.assertEqual([violation.metric for violation in violations], ["lines", "words"])

    def test_cli_emits_json_and_nonzero_for_over_budget_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "guidance.md"
            path.write_text("one two\nthree\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/instruction_budget.py"),
                    "--max-lines",
                    "1",
                    "--json",
                    str(path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["violations"][0]["metric"], "lines")


if __name__ == "__main__":
    unittest.main()
