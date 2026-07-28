"""Tests for setup.sh's retired-skill link removal (Goal 05 Step 9 criterion f).

`is_retired_skill()` existed and was used to *skip creating* links, but nothing ever removed a
link that already existed — so a skill retired after its link was created kept it forever.
`check-skill-drift.sh --prune-stale-links` does not catch it either: it removes only *dangling*
links, and a retired skill's target is still a valid directory. Separately,
`link_skills_from_dir()` had no retired guard at all, so `~/.codex/skills` re-created retired
links on every run.

These tests exercise the extracted shell functions directly against a temp HOME, so no real
skills directory is touched.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "setup.sh"

LEDGER = """# ledger

| skill | state | rationale |
|---|---|---|
| `gone-skill` | retired | retired for the test |
| `kept-skill` | disabled-pending | still listed, must survive |
"""


def run_shell(script: str, home: Path):
    env = dict(os.environ, HOME=str(home))
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)


def harness(home: Path, body: str) -> str:
    """Source just the helper block out of setup.sh, then run `body`.

    setup.sh is not idempotent-by-import (it symlinks the whole machine), so the functions are
    extracted by line range rather than sourced wholesale.
    """
    text = SETUP.read_text(encoding="utf-8")
    start = text.index("_removals_ledger=")
    end = text.index("# Claude Code skill symlinks")
    block = text[start:end]
    return f"set -euo pipefail\n{block}\n{body}\n"


class RetiredSkillLinkTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.home = Path(self._td.name)
        # Minimal fake dotfiles tree: the ledger plus two source skills.
        self.src = self.home / ".dotfiles" / "ai" / "skills"
        for name in ("gone-skill", "kept-skill"):
            (self.src / name).mkdir(parents=True)
            (self.src / name / "SKILL.md").write_text(f"# {name}\n")
        (self.home / ".dotfiles" / "ai" / "skills" / "REMOVALS.md").write_text(LEDGER)
        self.managed = [
            self.home / ".dotfiles" / ".claude" / "skills",
            self.home / ".claude" / "skills",
            self.home / ".codex" / "skills",
            self.home / ".gemini" / "skills",
            self.home / ".agents" / "skills",
        ]

    def tearDown(self):
        self._td.cleanup()

    def _seed_links(self):
        for d in self.managed:
            d.mkdir(parents=True, exist_ok=True)
            for name in ("gone-skill", "kept-skill"):
                link = d / name
                if not link.exists():
                    link.symlink_to(self.src / name)

    def test_retired_links_are_removed_from_every_managed_dir(self):
        self._seed_links()
        r = run_shell(harness(self.home, "remove_retired_skill_links"), self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        for d in self.managed:
            with self.subTest(dir=d.name):
                self.assertFalse((d / "gone-skill").exists(),
                                 f"retired link survived in {d}")
                self.assertTrue((d / "kept-skill").is_symlink(),
                                f"non-retired link was collateral damage in {d}")

    def test_a_real_directory_is_never_deleted(self):
        """Tool-managed folders live in these trees; deleting one would be destructive."""
        d = self.home / ".codex" / "skills"
        d.mkdir(parents=True, exist_ok=True)
        real = d / "gone-skill"
        real.mkdir()
        (real / "keep-me.txt").write_text("payload\n")

        r = run_shell(harness(self.home, "remove_retired_skill_links"), self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(real.is_dir(), "a real directory was deleted")
        self.assertTrue((real / "keep-me.txt").exists())
        self.assertIn("real directory", r.stdout)

    def test_running_twice_is_idempotent(self):
        self._seed_links()
        script = harness(self.home, "remove_retired_skill_links\nremove_retired_skill_links")
        r = run_shell(script, self.home)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_absent_directories_are_not_an_error(self):
        r = run_shell(harness(self.home, "remove_retired_skill_links"), self.home)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_link_skills_from_dir_refuses_to_create_a_retired_link(self):
        target = self.home / ".codex" / "skills"
        body = f'link_skills_from_dir "{self.src}" "{target}"'
        r = run_shell(harness(self.home, body), self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((target / "gone-skill").exists(),
                         "link_skills_from_dir re-created a retired skill link")
        self.assertTrue((target / "kept-skill").is_symlink(),
                        "link_skills_from_dir failed to link a live skill")

    def test_missing_ledger_is_a_no_op_not_a_crash(self):
        (self.home / ".dotfiles" / "ai" / "skills" / "REMOVALS.md").unlink()
        self._seed_links()
        r = run_shell(harness(self.home, "remove_retired_skill_links"), self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        # Nothing is known to be retired, so nothing may be removed.
        self.assertTrue((self.home / ".claude" / "skills" / "gone-skill").is_symlink())


if __name__ == "__main__":
    unittest.main()
