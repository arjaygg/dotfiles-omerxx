"""Tests for stripping machine-local-only keys out of staged .claude/settings.json.

`skipDangerousModePermissionPrompt: true` is a deliberate local default here — it
lives in the gitignored `.claude/settings.local.json`, which takes precedence — but
Claude Code also writes it into `~/.claude/settings.json`, a symlink into this repo.
Removing it from the staged blob is therefore lossless at runtime.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STRIPPER = ROOT / "scripts/strip_local_only_settings.py"
HOOK = ROOT / "git/hooks/sanitize-staged-settings.sh"

KEY = "skipDangerousModePermissionPrompt"

MID_OBJECT = """{
  "alpha": 1,
  "%s": true,
  "omega": 2
}
""" % KEY

LAST_MEMBER = """{
  "alpha": 1,
  "%s": true
}
""" % KEY


def run(text: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(STRIPPER), *args],
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )


class StripTests(unittest.TestCase):
    def test_removes_the_key(self):
        result = run(MID_OBJECT)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(KEY, result.stdout)
        self.assertEqual(json.loads(result.stdout), {"alpha": 1, "omega": 2})

    def test_diff_is_one_line_not_a_reformat(self):
        """json.dump would rewrite all ~580 lines and bury the real change."""
        result = run(MID_OBJECT)

        removed = set(MID_OBJECT.splitlines()) - set(result.stdout.splitlines())
        self.assertEqual(len(removed), 1, f"expected a 1-line delta, got {removed}")
        self.assertIn(KEY, removed.pop())

    def test_is_idempotent(self):
        once = run(MID_OBJECT).stdout
        twice = run(once).stdout

        self.assertEqual(once, twice)

    def test_absent_key_is_a_passthrough(self):
        clean = '{\n  "alpha": 1\n}\n'

        result = run(clean)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, clean)

    def test_key_as_last_member_repairs_the_dangling_comma(self):
        """Removing the final member leaves `"alpha": 1,` before `}` — invalid
        JSON unless the comma goes too."""
        result = run(LAST_MEMBER)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"alpha": 1})
        self.assertNotIn(",", result.stdout.split("alpha")[1].split("\n")[0])

    def test_check_mode_flags_presence_without_writing(self):
        result = run(MID_OBJECT, "--check")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn(KEY, result.stderr)

    def test_check_mode_passes_when_absent(self):
        result = run('{"alpha": 1}', "--check")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_json_is_refused_not_guessed(self):
        result = run('{"alpha": 1,}')

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("not valid JSON", result.stderr)


class HookIntegrationTests(unittest.TestCase):
    def test_index_is_cleaned_and_working_copy_keeps_the_local_default(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        repo = Path(directory.name)
        for args in (
            ["init", "-q", "-b", "main", "."],
            ["config", "user.email", "t@t.t"],
            ["config", "user.name", "t"],
        ):
            subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

        target = repo / ".claude/settings.json"
        target.parent.mkdir(parents=True)
        target.write_text(MID_OBJECT, encoding="utf-8")
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
        self.assertNotIn(KEY, staged)

        # The whole point: the local default survives in the working copy.
        self.assertIn(KEY, target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
