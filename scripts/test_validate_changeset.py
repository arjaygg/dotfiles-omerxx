"""Fixture-based tests for scripts/ai/validate-changeset.sh.

Builds hand-made local git fixtures (no network I/O) and asserts the script
routes staged files into docs/config/source/unknown per
plans/2026-07-25-agentic-git-pipeline.md (D2/Step 2), and that it never blocks
on an unrecognized subsystem while still catching real syntax errors in
config/source files.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

VALIDATE_SCRIPT = Path(__file__).resolve().parent / "ai" / "validate-changeset.sh"


def run(cwd, *args, check=True):
    proc = subprocess.run(list(args), cwd=str(cwd), capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"{args} failed: {proc.stderr}")
    return proc


def git(cwd, *args, check=True):
    return run(cwd, "git", *args, check=check)


def init_repo(path: Path, branch: str = "main") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", branch)
    git(path, "config", "user.email", "validate-test@example.com")
    git(path, "config", "user.name", "Validate Test")
    (path / "README.md").write_text("init\n")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "chore: init")
    return path


def run_validate(repo: Path):
    proc = subprocess.run(
        [str(VALIDATE_SCRIPT), "--json"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    return proc.returncode, json.loads(proc.stdout.strip())


CLEAN_SH = "#!/usr/bin/env bash\nset -euo pipefail\necho \"hello\"\n"
BROKEN_SH = "#!/usr/bin/env bash\nset -euo pipefail\nif [ true; then\n  echo broken\n"


class ValidateChangesetTests(unittest.TestCase):
    def test_docs_only_no_extra_validation(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            (repo / "docs").mkdir()
            (repo / "docs" / "notes.md").write_text("# notes\n")
            git(repo, "add", "docs/notes.md")
            code, result = run_validate(repo)
            self.assertEqual(code, 0)
            self.assertEqual(result["result"], "pass")
            self.assertIn("docs/notes.md", result["categories"].get("docs", []))
            self.assertEqual(result["failures"], [])

    def test_config_valid_yaml_passes(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            (repo / "settings.yaml").write_text("key: value\nlist:\n  - a\n  - b\n")
            git(repo, "add", "settings.yaml")
            code, result = run_validate(repo)
            self.assertEqual(code, 0)
            self.assertEqual(result["result"], "pass")
            self.assertIn("settings.yaml", result["categories"].get("config", []))

    def test_config_invalid_yaml_fails(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            (repo / "settings.yaml").write_text("key: [unclosed\n")
            git(repo, "add", "settings.yaml")
            code, result = run_validate(repo)
            self.assertEqual(code, 1)
            self.assertEqual(result["result"], "fail")
            self.assertTrue(any("settings.yaml" in f for f in result["failures"]))

    def test_config_invalid_json_fails(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            (repo / "data.json").write_text("{ not valid json \n")
            git(repo, "add", "data.json")
            code, result = run_validate(repo)
            self.assertEqual(code, 1)
            self.assertEqual(result["result"], "fail")
            self.assertTrue(any("data.json" in f for f in result["failures"]))

    def test_source_valid_shell_passes(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            (repo / "scripts").mkdir()
            (repo / "scripts" / "run.sh").write_text(CLEAN_SH)
            git(repo, "add", "scripts/run.sh")
            code, result = run_validate(repo)
            self.assertEqual(code, 0)
            self.assertEqual(result["result"], "pass")
            self.assertIn("scripts/run.sh", result["categories"].get("source", []))

    def test_source_invalid_shell_fails(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            (repo / "scripts").mkdir()
            (repo / "scripts" / "broken.sh").write_text(BROKEN_SH)
            git(repo, "add", "scripts/broken.sh")
            code, result = run_validate(repo)
            self.assertEqual(code, 1)
            self.assertEqual(result["result"], "fail")
            self.assertTrue(any("broken.sh" in f for f in result["failures"]))

    def test_unknown_category_warns_but_never_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            (repo / "notes.rb").write_text("puts 'hi'\n")
            git(repo, "add", "notes.rb")
            code, result = run_validate(repo)
            self.assertEqual(code, 0)
            self.assertEqual(result["result"], "pass")
            self.assertTrue(any("notes.rb" in w for w in result["warnings"]))
            self.assertIn("notes.rb", result["categories"].get("unknown", []))

    def test_hook_script_forced_to_source_even_without_config_pattern(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            (repo / ".claude-atomic.yaml").write_text(
                "validation:\n"
                "  docs:\n"
                "    - \"docs/\"\n"
                "  config:\n"
                "    - \"*.yaml\"\n"
            )
            git(repo, "add", ".claude-atomic.yaml")
            git(repo, "commit", "-q", "-m", "chore: add atomic config")
            (repo / ".claude" / "hooks").mkdir(parents=True)
            (repo / ".claude" / "hooks" / "pre-commit.sh").write_text(CLEAN_SH)
            git(repo, "add", ".claude/hooks/pre-commit.sh")
            code, result = run_validate(repo)
            self.assertEqual(code, 0)
            self.assertEqual(result["result"], "pass")
            self.assertIn(".claude/hooks/pre-commit.sh", result["categories"].get("source", []))
            self.assertNotIn(".claude/hooks/pre-commit.sh", result["categories"].get("unknown", []))

    def test_custom_validation_block_routes_atypical_config_extension(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            (repo / ".claude-atomic.yaml").write_text(
                "validation:\n"
                "  config:\n"
                "    - \"*.cfg\"\n"
            )
            git(repo, "add", ".claude-atomic.yaml")
            git(repo, "commit", "-q", "-m", "chore: add atomic config")
            (repo / "app.cfg").write_text("export FOO=bar\n")
            git(repo, "add", "app.cfg")
            code, result = run_validate(repo)
            self.assertEqual(code, 0)
            self.assertEqual(result["result"], "pass")
            self.assertIn("app.cfg", result["categories"].get("config", []))

    def test_no_staged_files_passes_trivially(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            code, result = run_validate(repo)
            self.assertEqual(code, 0)
            self.assertEqual(result["result"], "pass")
            self.assertEqual(result["categories"], {})


if __name__ == "__main__":
    unittest.main()
