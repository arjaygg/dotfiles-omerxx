import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.sh"


def make_setup_fixture(root: Path, *, disabled: bool) -> Path:
    setup = root / "setup.sh"
    shutil.copy2(SETUP, setup)
    helper = root / "scripts/check-skill-drift.sh"
    helper.parent.mkdir(parents=True)
    helper.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    helper.chmod(0o755)
    if disabled:
        (root / ".harness-disabled").mkdir()
    return setup


class SetupCheckTests(unittest.TestCase):
    def run_setup(self, setup: Path, mode: str, home: Path) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["HOME"] = str(home)
        return subprocess.run(
            ["bash", str(setup), mode],
            cwd=setup.parent,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_disabled_fixture_is_successful_noop_without_runtime_writes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            setup = make_setup_fixture(root, disabled=True)
            home = root / "home"
            home.mkdir()

            for mode in ("--check", "--dry-run"):
                with self.subTest(mode=mode):
                    result = self.run_setup(setup, mode, home)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("AI coding-agent harness is disabled", result.stdout)
                    self.assertNotIn("validating tracked config boundaries", result.stdout)
                    self.assertNotIn("Setup complete", result.stdout)
                    self.assertEqual(list(home.iterdir()), [], f"{mode} wrote under fake HOME")

    def test_enabled_fixture_runs_non_mutating_check_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            setup = make_setup_fixture(root, disabled=False)
            home = root / "home"
            home.mkdir()

            check = self.run_setup(setup, "--check", home)
            dry_run = self.run_setup(setup, "--dry-run", home)

        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertIn("validating tracked config boundaries", check.stdout)
        self.assertNotIn("AI coding-agent harness is disabled", check.stdout)
        self.assertNotIn("Setup complete", check.stdout)
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        self.assertIn("no stow, symlink, install, prune, extension, or cleanup commands", dry_run.stdout)
        self.assertNotIn("Setup complete", dry_run.stdout)


if __name__ == "__main__":
    unittest.main()
