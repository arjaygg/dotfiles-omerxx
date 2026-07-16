import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.sh"


class SetupCheckTests(unittest.TestCase):
    def test_setup_check_runs_non_mutating_validators(self):
        result = subprocess.run(
            ["bash", str(SETUP), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("validating tracked config boundaries", result.stdout)
        self.assertIn('"by_source_status"', result.stdout)
        self.assertIn('"by_status"', result.stdout)
        self.assertIn('"by_rule"', result.stdout)
        self.assertIn('"by_scope"', result.stdout)
        self.assertNotIn("Setup complete", result.stdout)

    def test_setup_dry_run_stops_before_mutating_install_steps(self):
        result = subprocess.run(
            ["bash", str(SETUP), "--dry-run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no stow, symlink, install, prune, extension, or cleanup commands", result.stdout)
        self.assertNotIn("Setup complete", result.stdout)

    def test_check_and_dry_run_do_not_create_runtime_dirs_in_fresh_home(self):
        for mode in ("--check", "--dry-run"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                home = Path(td)
                environment = os.environ.copy()
                environment["HOME"] = str(home)

                result = subprocess.run(
                    ["bash", str(SETUP), mode],
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    sorted(path.name for path in home.iterdir()),
                    [],
                    f"{mode} created runtime files under fake HOME",
                )


if __name__ == "__main__":
    unittest.main()
