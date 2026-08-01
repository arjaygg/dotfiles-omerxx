"""Tests for the home-path normaliser utility.

`lean-ctx doctor --fix` rewrites hook entries with the absolute path of its own
binary; this helper rewrites them back to `$HOME` form. It was the engine of the
retired sanitize-staged-settings pre-commit hook — `.claude/settings.json` is
untracked since decisions/0016 — and is kept as a standalone utility.
"""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZER = ROOT / "scripts/normalize_home_paths.py"

# Split so this file does not trip public_hygiene_check's own
# absolute-home-path rule, the same way that module splits its org-name pattern.
FAKE_HOME = "/Users" + "/someone"
OTHER_HOME = "/Users" + "/somebody-else"

REAL_DRIFT = f'"command": "{FAKE_HOME}/.cargo/bin/lean-ctx hook read-dedup"'


def run_normalizer(text: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(NORMALIZER), *args],
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )


class NormalizeTests(unittest.TestCase):
    def test_rewrites_the_given_home_to_dollar_home(self):
        result = run_normalizer(REAL_DRIFT, "--home", FAKE_HOME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"$HOME/.cargo/bin/lean-ctx hook read-dedup"', result.stdout)
        self.assertNotIn(FAKE_HOME, result.stdout)

    def test_is_idempotent(self):
        once = run_normalizer(REAL_DRIFT, "--home", FAKE_HOME).stdout
        twice = run_normalizer(once, "--home", FAKE_HOME).stdout

        self.assertEqual(once, twice)

    def test_check_mode_reports_drift_without_writing(self):
        result = run_normalizer(REAL_DRIFT, "--check", "--home", FAKE_HOME)

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")

    def test_check_mode_passes_on_already_normalised_text(self):
        clean = '"command": "$HOME/.cargo/bin/lean-ctx hook read-dedup"'

        result = run_normalizer(clean, "--check", "--home", FAKE_HOME)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_other_users_home_is_reported_not_silently_rewritten(self):
        """$HOME is the wrong answer for a path under a different user's home,
        so it must escalate to a human rather than be guessed."""
        text = f'"command": "{OTHER_HOME}/bin/thing"'

        result = run_normalizer(text, "--home", FAKE_HOME)

        self.assertEqual(result.returncode, 2)
        self.assertIn("manual review", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
