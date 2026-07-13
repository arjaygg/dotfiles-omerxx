import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.sh"


class SetupModeTests(unittest.TestCase):
    def test_dry_run_emits_proposals_without_installing(self):
        result = subprocess.run(
            ["bash", str(SETUP), "--dry-run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("proposals", payload)
        self.assertNotIn("Setup complete", result.stdout)

    def test_check_reports_doctor_findings_without_installing(self):
        result = subprocess.run(
            ["bash", str(SETUP), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertIn(result.returncode, {0, 1}, result.stderr)
        self.assertIsInstance(json.loads(result.stdout), list)
        self.assertNotIn("Setup complete", result.stdout)


if __name__ == "__main__":
    unittest.main()
