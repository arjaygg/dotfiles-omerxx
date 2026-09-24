"""Hermetic coverage for git/hooks/pre-commit's disabled-harness gate."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "git" / "hooks" / "pre-commit"
CHECKS = ("protect-main.sh", "detect-private-key.sh", "check-large-files.sh", "check-atomicity.sh")


class PreCommitDispatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)
        self.dotfiles = self.home / ".dotfiles"
        hooks = self.dotfiles / "git" / "hooks"
        scripts = self.dotfiles / "scripts"
        hooks.mkdir(parents=True)
        scripts.mkdir()
        self.log = self.home / "calls.log"
        shutil.copy(HOOK, hooks / "pre-commit")
        for name in CHECKS:
            (hooks / name).write_text(f'echo {name} >> "{self.log}"\n')
        for name in ("validate_skills.py", "run_evals.py"):
            (scripts / name).write_text(
                f"open({str(self.log)!r}, 'a').write('{name}\\n')\nraise SystemExit(1)\n"
            )

    def run_hook(self) -> tuple[int, list[str]]:
        env = {**os.environ, "HOME": str(self.home)}
        proc = subprocess.run(
            ["bash", str(self.dotfiles / "git" / "hooks" / "pre-commit")],
            env=env, capture_output=True, text=True, check=False,
        )
        calls = self.log.read_text().split() if self.log.exists() else []
        return proc.returncode, calls

    def test_disabled_harness_skips_skill_validators(self) -> None:
        (self.dotfiles / ".harness-disabled").mkdir()
        code, calls = self.run_hook()
        self.assertEqual(code, 0)
        self.assertEqual(calls, list(CHECKS))

    def test_enabled_harness_runs_skill_validators(self) -> None:
        code, calls = self.run_hook()
        self.assertEqual(code, 1)
        self.assertEqual(calls, [*CHECKS, "validate_skills.py"])


if __name__ == "__main__":
    unittest.main()
