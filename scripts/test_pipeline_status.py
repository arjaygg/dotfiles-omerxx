"""Fixture-based tests for scripts/ai/pipeline-status.sh.

Builds hand-made local git/worktree fixtures (no network I/O — remotes are
local bare repos) and asserts the script classifies each into the correct
signal per plans/2026-07-25-agentic-git-pipeline.md (D1/D1b/D4).
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

PIPELINE_SCRIPT = Path(__file__).resolve().parent / "ai" / "pipeline-status.sh"


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
    git(path, "config", "user.email", "pipeline-test@example.com")
    git(path, "config", "user.name", "Pipeline Test")
    (path / "README.md").write_text("init\n")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "chore: init")
    return path


def add_bare_origin(repo: Path, tmp: Path, push_branch: str = "main") -> Path:
    bare = tmp / "origin.git"
    git(tmp, "init", "-q", "--bare", str(bare))
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "push", "-q", "-u", "origin", push_branch)
    return bare


def run_pipeline(repo: Path) -> dict:
    proc = subprocess.run(
        [str(PIPELINE_SCRIPT), "--json"],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip())


class PipelineStatusTests(unittest.TestCase):
    def test_commit_due_when_small_changeset_staged(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_bare_origin(repo, tmp)
            git(repo, "checkout", "-q", "-b", "feature/one")
            (repo / "a.py").write_text("x = 1\n")
            git(repo, "add", "a.py")
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "commit_due")

    def test_split_needed_when_staged_changes_span_subsystems(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_bare_origin(repo, tmp)
            git(repo, "checkout", "-q", "-b", "feature/two")
            (repo / "mod.py").write_text("value = 1\n")
            (repo / "config.yaml").write_text("key: value\n")
            (repo / "thing_test.py").write_text("def test_x(): pass\n")
            git(repo, "add", "mod.py", "config.yaml", "thing_test.py")
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "split_needed")

    def test_split_needed_when_staged_changeset_is_oversized(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_bare_origin(repo, tmp)
            git(repo, "checkout", "-q", "-b", "feature/three")
            files = []
            for i in range(8):
                fname = f"mod_{i}.py"
                (repo / fname).write_text(f"value_{i} = {i}\n")
                files.append(fname)
            git(repo, "add", *files)
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "split_needed")

    def test_pr_due_when_branch_has_unpushed_commits(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_bare_origin(repo, tmp)
            git(repo, "checkout", "-q", "-b", "feature/four")
            (repo / "a.py").write_text("x = 1\n")
            git(repo, "add", "a.py")
            git(repo, "commit", "-q", "-m", "feat: add a")
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "pr_due")

    def test_pr_due_when_pushed_but_no_ci_status_file(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_bare_origin(repo, tmp)
            git(repo, "checkout", "-q", "-b", "feature/four-b")
            (repo / "a.py").write_text("x = 1\n")
            git(repo, "add", "a.py")
            git(repo, "commit", "-q", "-m", "feat: add a")
            git(repo, "push", "-q", "-u", "origin", "feature/four-b")
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "pr_due")
            self.assertIn("no ci-status.md", result["reason"])

    def test_ci_pending_when_ci_status_correlated_but_not_terminal(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_bare_origin(repo, tmp)
            git(repo, "checkout", "-q", "-b", "feature/five")
            (repo / "a.py").write_text("x = 1\n")
            git(repo, "add", "a.py")
            git(repo, "commit", "-q", "-m", "feat: add a")
            git(repo, "push", "-q", "-u", "origin", "feature/five")
            (repo / "plans").mkdir()
            (repo / "plans" / "ci-status.md").write_text(
                "**PR:** #1 — feature/five\n"
                "**Last checked:** t0 (poll 1/40)\n"
                "**Run status:** in_progress\n"
            )
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "ci_pending")

    def test_merge_due_when_ci_status_correlated_and_success(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_bare_origin(repo, tmp)
            git(repo, "checkout", "-q", "-b", "feature/six")
            (repo / "a.py").write_text("x = 1\n")
            git(repo, "add", "a.py")
            git(repo, "commit", "-q", "-m", "feat: add a")
            git(repo, "push", "-q", "-u", "origin", "feature/six")
            (repo / "plans").mkdir()
            (repo / "plans" / "ci-status.md").write_text(
                "**PR:** #1 — feature/six\n"
                "**Last checked:** t1 (poll 5/40)\n"
                "**Status:** SUCCESS\n"
            )
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "merge_due")

    def test_ci_pending_when_ci_status_branch_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_bare_origin(repo, tmp)
            git(repo, "checkout", "-q", "-b", "feature/seven")
            (repo / "a.py").write_text("x = 1\n")
            git(repo, "add", "a.py")
            git(repo, "commit", "-q", "-m", "feat: add a")
            git(repo, "push", "-q", "-u", "origin", "feature/seven")
            (repo / "plans").mkdir()
            (repo / "plans" / "ci-status.md").write_text(
                "**PR:** #2 — feature/other\n"
                "**Status:** SUCCESS\n"
            )
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "ci_pending")
            self.assertIn("stale or mismatched", result["reason"])

    def test_ci_pending_when_ci_status_sha_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_bare_origin(repo, tmp)
            git(repo, "checkout", "-q", "-b", "feature/eight")
            (repo / "a.py").write_text("x = 1\n")
            git(repo, "add", "a.py")
            git(repo, "commit", "-q", "-m", "feat: add a")
            git(repo, "push", "-q", "-u", "origin", "feature/eight")
            (repo / "plans").mkdir()
            (repo / "plans" / "ci-status.md").write_text(
                "**PR:** #3 — feature/eight\n"
                "**SHA:** 0000000000000000000000000000000000dead\n"
                "**Status:** SUCCESS\n"
            )
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "ci_pending")
            self.assertIn("stale or mismatched", result["reason"])

    def test_sync_due_when_local_main_is_behind_origin(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            bare = add_bare_origin(repo, tmp)
            clone2 = tmp / "clone2"
            git(tmp, "clone", "-q", str(bare), str(clone2))
            git(clone2, "config", "user.email", "pipeline-test@example.com")
            git(clone2, "config", "user.name", "Pipeline Test")
            (clone2 / "extra.md").write_text("more\n")
            git(clone2, "add", "extra.md")
            git(clone2, "commit", "-q", "-m", "docs: extra")
            git(clone2, "push", "-q", "origin", "main")
            git(repo, "fetch", "-q", "origin")
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "sync_due")

    def test_cleanup_due_for_merged_branch_without_worktree(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            git(repo, "checkout", "-q", "-b", "feature/merged")
            (repo / "a.py").write_text("x = 1\n")
            git(repo, "add", "a.py")
            git(repo, "commit", "-q", "-m", "feat: add a")
            git(repo, "checkout", "-q", "main")
            git(repo, "merge", "-q", "--no-ff", "feature/merged", "-m", "merge: feature/merged")
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "cleanup_due")
            self.assertIn("delete the local branch", result["reason"])

    def test_cleanup_due_reports_linked_worktree_for_merged_branch(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            git(repo, "checkout", "-q", "-b", "feature/wt")
            (repo / "a.py").write_text("x = 1\n")
            git(repo, "add", "a.py")
            git(repo, "commit", "-q", "-m", "feat: add a")
            git(repo, "checkout", "-q", "main")
            git(repo, "merge", "-q", "--no-ff", "feature/wt", "-m", "merge: feature/wt")
            wt_path = tmp / "wt-feature"
            git(repo, "worktree", "add", "-q", str(wt_path), "feature/wt")
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "cleanup_due")
            self.assertIn(str(wt_path), result["reason"])
            self.assertIn("linked worktree", result["reason"])

    def test_cleanup_due_detects_squash_merged_branch(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            git(repo, "checkout", "-q", "-b", "feature/squash")
            (repo / "squash.py").write_text("value = 42\n")
            git(repo, "add", "squash.py")
            git(repo, "commit", "-q", "-m", "feat: add squash value")
            git(repo, "checkout", "-q", "main")
            git(repo, "checkout", "feature/squash", "--", "squash.py")
            git(repo, "add", "squash.py")
            git(repo, "commit", "-q", "-m", "feat: add squash value (#1)")
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "cleanup_due")

    def test_none_when_main_in_sync_and_nothing_to_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_bare_origin(repo, tmp)
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "none")

    def test_none_when_feature_branch_has_nothing_due(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_bare_origin(repo, tmp)
            git(repo, "checkout", "-q", "-b", "feature/clean")
            git(repo, "push", "-q", "-u", "origin", "feature/clean")
            result = run_pipeline(repo)
            self.assertEqual(result["signal"], "none")


if __name__ == "__main__":
    unittest.main()
