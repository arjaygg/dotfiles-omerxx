import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts/check-skill-drift.sh"
SETUP = ROOT / "setup.sh"


class SkillDriftCheckTests(unittest.TestCase):
    def run_check(self, skills_dir: Path) -> subprocess.CompletedProcess[str]:
        return self.run_check_args(str(skills_dir))

    def run_check_args(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(CHECK), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_dangling_symlink_fails(self):
        with tempfile.TemporaryDirectory() as td:
            skills_dir = Path(td) / "skills"
            skills_dir.mkdir()
            (skills_dir / "missing-skill").symlink_to(skills_dir / "does-not-exist")

            result = self.run_check(skills_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Dangling symlinks", result.stderr)
            self.assertIn("missing-skill", result.stderr)

    def test_valid_symlink_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skills_dir = root / "skills"
            source = root / "source" / "valid-skill"
            skills_dir.mkdir()
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text(
                "---\nname: valid-skill\ndescription: valid skill\n---\n",
                encoding="utf-8",
            )
            (skills_dir / "valid-skill").symlink_to(source)

            result = self.run_check(skills_dir)

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_symlink_to_dir_without_skill_file_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skills_dir = root / "skills"
            source = root / "source" / "not-a-skill"
            skills_dir.mkdir()
            source.mkdir(parents=True)
            (skills_dir / "not-a-skill").symlink_to(source)

            result = self.run_check(skills_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Symlink targets without SKILL.md", result.stderr)
            self.assertIn("not-a-skill", result.stderr)

    def test_prune_stale_links_removes_only_invalid_symlinks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skills_dir = root / "skills"
            valid_target = root / "source" / "valid-skill"
            non_skill_target = root / "source" / "not-a-skill"
            real_skill = skills_dir / "real-skill"
            skills_dir.mkdir()
            valid_target.mkdir(parents=True)
            non_skill_target.mkdir(parents=True)
            real_skill.mkdir()
            (valid_target / "SKILL.md").write_text(
                "---\nname: valid-skill\ndescription: valid skill\n---\n",
                encoding="utf-8",
            )
            (real_skill / "SKILL.md").write_text(
                "---\nname: real-skill\ndescription: real skill\n---\n",
                encoding="utf-8",
            )
            dangling = skills_dir / "dangling"
            not_a_skill = skills_dir / "not-a-skill"
            valid = skills_dir / "valid-skill"
            dangling.symlink_to(root / "missing")
            not_a_skill.symlink_to(non_skill_target)
            valid.symlink_to(valid_target)

            result = self.run_check_args("--prune-stale-links", str(skills_dir))

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(dangling.exists() or dangling.is_symlink())
            self.assertFalse(not_a_skill.exists() or not_a_skill.is_symlink())
            self.assertTrue(valid.is_symlink())
            self.assertTrue(real_skill.is_dir())
            self.assertIn("Pruned stale skill symlinks", result.stdout)
            self.assertIn("Non-quarantined real directories", result.stderr)

    def test_prune_stale_links_returns_clean_after_pruning_when_only_links_were_stale(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skills_dir = root / "skills"
            target = root / "source" / "not-a-skill"
            skills_dir.mkdir()
            target.mkdir(parents=True)
            (skills_dir / "dangling").symlink_to(root / "missing")
            (skills_dir / "not-a-skill").symlink_to(target)

            result = self.run_check_args("--prune-stale-links", str(skills_dir))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Pruned stale skill symlinks", result.stdout)
            self.assertIn("all entries are valid", result.stdout)

    def test_non_quarantined_real_directory_fails(self):
        with tempfile.TemporaryDirectory() as td:
            skills_dir = Path(td) / "skills"
            real_skill = skills_dir / "real-skill"
            real_skill.mkdir(parents=True)
            (real_skill / "SKILL.md").write_text(
                "---\nname: real-skill\ndescription: real skill\n---\n",
                encoding="utf-8",
            )

            result = self.run_check(skills_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Non-quarantined real directories", result.stderr)
            self.assertIn("real-skill", result.stderr)

    def test_repo_claude_skills_have_no_drift(self):
        result = self.run_check(ROOT / ".claude" / "skills")

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_repo_tool_skill_dirs_have_no_drift(self):
        result = self.run_check_args(
            str(ROOT / ".claude" / "skills"),
            str(ROOT / ".gemini" / "skills"),
            str(ROOT / ".cursor" / "skills"),
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_setup_prunes_stale_generated_user_skill_links(self):
        setup = SETUP.read_text(encoding="utf-8")

        self.assertIn("check-skill-drift.sh --prune-stale-links", setup)
        for user_skill_dir in (
            "$HOME/.claude/skills",
            "$HOME/.codex/skills",
            "$HOME/.gemini/skills",
            "$HOME/.cursor/skills",
        ):
            self.assertIn(user_skill_dir, setup)

    def test_multiple_skill_dirs_fail_if_any_dir_has_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            clean = root / "clean"
            dirty = root / "dirty"
            target = root / "source" / "valid-skill"
            clean.mkdir()
            dirty.mkdir()
            target.mkdir(parents=True)
            (target / "SKILL.md").write_text(
                "---\nname: valid-skill\ndescription: valid skill\n---\n",
                encoding="utf-8",
            )
            (clean / "valid-skill").symlink_to(target)
            (dirty / "missing-skill").symlink_to(root / "missing")

            result = self.run_check_args(str(clean), str(dirty))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing-skill", result.stderr)


if __name__ == "__main__":
    unittest.main()
