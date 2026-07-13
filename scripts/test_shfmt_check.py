import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.shfmt_check import _fingerprint, check, compare


class ShfmtCheckTests(unittest.TestCase):
    def test_check_records_unformatted_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "hook.sh"
            script.write_text("echo hi\n", encoding="utf-8")
            completed = subprocess.CompletedProcess([], 1, stdout=f"{script}\n", stderr="")
            with mock.patch("scripts.shfmt_check.shutil.which", return_value="/bin/shfmt"), mock.patch(
                "scripts.shfmt_check.subprocess.run", return_value=completed
            ):
                report = check([script])
        self.assertEqual(report["shell_file_count"], 1)
        self.assertEqual(report["unformatted"], [str(script)])

    def test_compare_matches_privacy_safe_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "hook.sh"
            script.write_text("echo hi\n", encoding="utf-8")
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "shell_file_count": 1,
                        "unformatted_count": 1,
                        "fingerprint": _fingerprint([str(script)]),
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.CompletedProcess([], 1, stdout=f"{script}\n", stderr="")
            with mock.patch("scripts.shfmt_check.shutil.which", return_value="/bin/shfmt"), mock.patch(
                "scripts.shfmt_check.subprocess.run", return_value=completed
            ):
                report = compare([script], baseline)
        self.assertTrue(report["baseline_match"])


if __name__ == "__main__":
    unittest.main()
