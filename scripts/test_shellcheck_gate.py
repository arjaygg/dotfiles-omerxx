"""Tests for scripts/shellcheck_gate.py and the defects it exists to catch.

Context: `shell_syntax_check.py` runs `bash -n`, a syntax parse that accepts code which parses but
is wrong. Nothing ran shellcheck repo-wide (the only other call is inside
`scripts/ai/validate-changeset.sh`, staged-changeset only, invoked by the auto-ship skill rather
than CI or the pre-commit hook). This gate closes that.

Its first run found `.cursor/hooks/before-shell-git-commit.sh` failing OPEN — see
`test_cursor_commit_gate_actually_denies` below, which pins the behaviour, not just the lint.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "shellcheck_gate.py"
CURSOR_HOOK = ROOT / ".cursor" / "hooks" / "before-shell-git-commit.sh"


def run_gate(*args):
    return subprocess.run([sys.executable, str(GATE), *args],
                          capture_output=True, text=True, cwd=str(ROOT))


class ShellcheckGateTests(unittest.TestCase):
    def test_repo_is_clean_at_error_severity(self):
        r = run_gate("--summary")
        self.assertEqual(r.returncode, 0,
                         f"error-severity shellcheck findings present:\n{r.stdout}\n{r.stderr}")
        data = json.loads(r.stdout)
        self.assertEqual(data["findings"], 0)
        self.assertGreater(data["shell_files"], 50,
                           "governed file list collapsed — candidate_files() may have changed")

    def test_severity_stays_at_error(self):
        """The governed set carries ~113 warning-level findings; gating on warnings would be red
        from day one and would train people to ignore the gate."""
        self.assertEqual(json.loads(run_gate("--summary").stdout)["severity"], "error")

    def test_file_list_is_not_redefined(self):
        """Reuse shell_syntax_check.candidate_files so the two shell gates cannot drift apart on
        which files count as governed."""
        src = GATE.read_text(encoding="utf-8")
        self.assertIn("from shell_syntax_check import candidate_files", src)

    def test_missing_shellcheck_fails_rather_than_passing_silently(self):
        """A gate that cannot run is not a green gate."""
        src = GATE.read_text(encoding="utf-8")
        self.assertIn("shellcheck is not installed", src)
        self.assertIn("could not run", src)


class CursorCommitGateBehaviourTests(unittest.TestCase):
    """The defect the lint surfaced, pinned behaviourally.

    `python3 - <<'PY'` took the program from stdin, so the heredoc overrode the piped JSON and
    `json.load(sys.stdin)` never saw the payload (SC2259). It raised JSONDecodeError and fell
    through to the trailing `allow`, so every raw `git commit` in a hyper-atomic repo was permitted.
    A second bug compounded it: `read -r command cwd` reads ONE line and splits on IFS, so `cwd`
    captured the rest of the command line and line 2 was never read.
    """

    def _run(self, payload: str):
        return subprocess.run(["bash", str(CURSOR_HOOK)], input=payload,
                              capture_output=True, text=True)

    def test_cursor_commit_gate_actually_denies(self):
        r = self._run(json.dumps({"command": "git commit -m wip", "cwd": str(ROOT)}))
        self.assertIn('"permission": "deny"', r.stdout,
                      "the gate fails open — a raw git commit was allowed")

    def test_command_with_spaces_survives_parsing(self):
        """Guards the second bug: a split command string used to lose everything after word 1."""
        r = self._run(json.dumps({"command": "git commit -m 'a longer message here'",
                                  "cwd": str(ROOT)}))
        self.assertIn('"permission": "deny"', r.stdout)

    def test_sanctioned_wrappers_are_allowed(self):
        for cmd in ("~/.dotfiles/scripts/ai/commit.sh -m a -m b",
                    "~/.dotfiles/scripts/ai/checkpoint.sh wip"):
            with self.subTest(cmd=cmd):
                r = self._run(json.dumps({"command": cmd, "cwd": str(ROOT)}))
                self.assertIn('"permission": "allow"', r.stdout)

    def test_unrelated_command_is_allowed(self):
        r = self._run(json.dumps({"command": "git status", "cwd": str(ROOT)}))
        self.assertIn('"permission": "allow"', r.stdout)

    def test_payload_is_not_read_from_stdin(self):
        """Regression: the program must not come from stdin alongside the payload.

        Comments are stripped before asserting — the fix's own explanatory comment quotes the old
        broken form (`python3 - <<'PY'`), and matching against raw file text flags that as a
        reintroduction.
        """
        src = CURSOR_HOOK.read_text(encoding="utf-8")
        code = "\n".join(line for line in src.splitlines()
                         if not line.lstrip().startswith("#"))
        self.assertNotIn("python3 - <<", code, "program back on stdin — SC2259 reintroduced")
        self.assertIn("AGENT_HOOK_INPUT", code, "payload should arrive via the environment")


if __name__ == "__main__":
    unittest.main()
