"""Tests for the staged-settings home-path normaliser.

Context: `lean-ctx doctor --fix` rewrites three hook entries in
`.claude/settings.json` with the absolute path of its own binary, and
`~/.claude/settings.json` symlinks into this tracked repo. Verified empirically
that the rewrite happens from `$HOME/...` and from a bare `lean-ctx hook ...`
alike, so the entry cannot be written in a form that survives. The commit is
normalised instead.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZER = ROOT / "scripts/normalize_home_paths.py"
HOOK = ROOT / "git/hooks/sanitize-staged-settings.sh"

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


class PreCommitHookTests(unittest.TestCase):
    """End-to-end: the hook must fix the index and leave the working tree alone."""

    def _repo(self) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        repo = Path(directory.name)
        for args in (
            ["init", "-q", "-b", "main", "."],
            ["config", "user.email", "t@t.t"],
            ["config", "user.name", "t"],
        ):
            subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
        return repo

    def test_hook_normalises_the_index_but_not_the_working_tree(self):
        repo = self._repo()
        home = str(Path.home())
        polluted = json.dumps(
            {"hooks": {"PostToolUse": [{"command": f"{home}/.cargo/bin/lean-ctx hook rewrite"}]}},
            indent=2,
        )
        target = repo / ".claude/settings.json"
        target.parent.mkdir(parents=True)
        target.write_text(polluted, encoding="utf-8")
        subprocess.run(
            ["git", "add", ".claude/settings.json"], cwd=repo, check=True, capture_output=True
        )

        result = subprocess.run(
            ["bash", str(HOOK)], cwd=repo, capture_output=True, text=True, check=False
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        staged = subprocess.run(
            ["git", "show", ":.claude/settings.json"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertIn("$HOME/.cargo/bin/lean-ctx hook rewrite", staged)
        self.assertNotIn(home, staged)

        # The working copy keeps what lean-ctx wrote — the point of normalising
        # the index instead of the file.
        self.assertIn(home, target.read_text(encoding="utf-8"))

    def test_hook_is_a_noop_when_settings_is_not_staged(self):
        repo = self._repo()
        (repo / "other.txt").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "add", "other.txt"], cwd=repo, check=True, capture_output=True)

        result = subprocess.run(
            ["bash", str(HOOK)], cwd=repo, capture_output=True, text=True, check=False
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
