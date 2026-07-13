import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.shellcheck_check import Issue, compare_baseline, parse_findings, run_shellcheck


class ShellCheckTests(unittest.TestCase):
    def test_parse_findings_normalizes_shellcheck_json(self):
        findings = parse_findings(
            '[{"file":"hook.sh","line":3,"endLine":3,"column":2,"endColumn":5,"level":"error","code":2259,"message":"bad pipe","fix":null}]'
        )

        self.assertEqual(
            findings,
            [Issue("hook.sh", 3, 3, 2, 5, "error", 2259, "bad pipe")],
        )

    def test_baseline_comparison_reports_drift(self):
        baseline = [Issue("hook.sh", 3, 3, 2, 5, "error", 2259, "bad pipe")]
        current = baseline + [Issue("other.sh", 1, 1, 1, 2, "error", 2001, "new")]

        comparison = compare_baseline(current, baseline)

        self.assertFalse(comparison["match"])
        self.assertEqual(comparison["added"][0]["code"], 2001)
        self.assertEqual(comparison["removed"], [])

    def test_runner_uses_json_output_and_accepts_findings_exit_one(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            fake = temporary / "fake_shellcheck.py"
            fake.write_text(
                "import json, sys\n"
                "print(json.dumps([{'file': sys.argv[-1], 'line': 1, 'endLine': 1, 'column': 1, 'endColumn': 2, 'level': 'error', 'code': 2259, 'message': 'bad', 'fix': None}]))\n"
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            shell = temporary / "hook.sh"
            shell.write_text("echo ok\n", encoding="utf-8")

            available, findings = run_shellcheck([shell], executable=[sys.executable, str(fake)])

        self.assertTrue(available)
        self.assertEqual(findings[0].code, 2259)
        self.assertEqual(findings[0].path, str(shell))


if __name__ == "__main__":
    unittest.main()
