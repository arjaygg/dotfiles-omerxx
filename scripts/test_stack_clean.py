"""Regression tests for clean-stack.sh branch deletion after a rewritten merge.

`git branch -d` only accepts a branch whose tip is an ancestor of the default
branch. `gh pr merge --rebase` / `--squash` rewrite the commits, so a fully
shipped branch is never an ancestor and -d always refuses — which used to make
clean-stack.sh warn "Branch not fully merged" and silently skip the delete on
every single rebase merge.
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / ".claude/scripts/pr-stack/clean-stack.sh"


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )


class CleanStackRewrittenMergeTests(unittest.TestCase):
    def _repo(self) -> Path:
        directory = tempfile.TemporaryDirectory()
        repo = Path(directory.name)
        self.addCleanup(directory.cleanup)
        git(repo, "init", "-q", "-b", "main", ".")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "test")
        (repo / "base.txt").write_text("base\n", encoding="utf-8")
        git(repo, "add", "base.txt")
        git(repo, "commit", "-qm", "base")
        return repo

    def _branch_with_commit(self, repo: Path, branch: str, filename: str) -> None:
        git(repo, "checkout", "-qb", branch)
        (repo / filename).write_text("work\n", encoding="utf-8")
        git(repo, "add", filename)
        git(repo, "commit", "-qm", f"feat: add {filename}")
        git(repo, "checkout", "-q", "main")

    def _run_clean(self, repo: Path, branch: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(CLEAN), branch],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(repo)},
        )

    def _branch_exists(self, repo: Path, branch: str) -> bool:
        return branch in git(repo, "branch", "--list", branch).stdout

    def test_rebase_merged_branch_is_deleted(self):
        repo = self._repo()
        self._branch_with_commit(repo, "feature/x", "g.txt")
        # Cherry-pick reapplies the patch, which is what `gh pr merge --rebase`
        # does. Amending afterwards forces a distinct SHA: cherry-picking a commit
        # whose parent is already HEAD can otherwise produce a byte-identical SHA
        # when both land in the same second, which would make the branch a real
        # ancestor and quietly stop testing the rebase path at all.
        self.assertEqual(git(repo, "cherry-pick", "feature/x").returncode, 0)
        git(repo, "commit", "--amend", "-qm", "feat: add g.txt (rebased onto main)")
        self.assertNotEqual(
            git(repo, "rev-parse", "feature/x").stdout,
            git(repo, "rev-parse", "main").stdout,
            "precondition: the rebased commit must have a different SHA",
        )
        self.assertNotEqual(
            git(repo, "branch", "-d", "feature/x").returncode,
            0,
            "precondition: plain `git branch -d` must refuse, or the bug cannot reproduce",
        )

        result = self._run_clean(repo, "feature/x")

        self.assertFalse(self._branch_exists(repo, "feature/x"), result.stdout + result.stderr)
        self.assertIn("rebase/squash-merged", result.stdout)

    def test_rebase_merged_branch_is_deleted_after_default_branch_advances(self):
        repo = self._repo()
        self._branch_with_commit(repo, "feature/w", "j.txt")
        git(repo, "cherry-pick", "feature/w")
        (repo / "later.txt").write_text("later\n", encoding="utf-8")
        git(repo, "add", "later.txt")
        git(repo, "commit", "-qm", "unrelated later work")

        result = self._run_clean(repo, "feature/w")

        self.assertFalse(self._branch_exists(repo, "feature/w"), result.stdout + result.stderr)

    def test_squash_merged_branch_is_deleted(self):
        repo = self._repo()
        git(repo, "checkout", "-qb", "feature/z")
        (repo / "i.txt").write_text("s1\n", encoding="utf-8")
        git(repo, "add", "i.txt")
        git(repo, "commit", "-qm", "part 1")
        (repo / "i.txt").write_text("s1\ns2\n", encoding="utf-8")
        git(repo, "add", "i.txt")
        git(repo, "commit", "-qm", "part 2")
        git(repo, "checkout", "-q", "main")
        git(repo, "merge", "--squash", "feature/z")
        git(repo, "commit", "-qm", "squashed")

        result = self._run_clean(repo, "feature/z")

        self.assertFalse(self._branch_exists(repo, "feature/z"), result.stdout + result.stderr)

    def test_genuinely_unmerged_branch_is_preserved(self):
        repo = self._repo()
        self._branch_with_commit(repo, "feature/y", "h.txt")

        result = self._run_clean(repo, "feature/y")

        self.assertTrue(
            self._branch_exists(repo, "feature/y"),
            "unmerged work must never be deleted without --force",
        )
        self.assertIn("not fully merged", result.stdout)

    def _worktree_repo(self):
        """A repo with a real worktree, mirroring what `stack create` produces."""
        repo = self._repo()
        git(repo, "checkout", "-qb", "docs/some-checkpoint")
        (repo / "d.txt").write_text("doc\n", encoding="utf-8")
        git(repo, "add", "d.txt")
        git(repo, "commit", "-qm", "docs: add d")
        git(repo, "checkout", "-q", "main")
        # `stack create` sanitizes an unknown prefix by removing the slash only.
        trees = repo / ".trees"
        trees.mkdir(exist_ok=True)
        git(repo, "worktree", "add", str(trees / "docssome-checkpoint"), "docs/some-checkpoint")
        return repo

    def test_worktree_is_found_for_a_branch_prefix_outside_the_strip_list(self):
        """docs/ is not in WINDOW_NAME's prefix list, so a path rebuilt from the
        branch name pointed at .trees/docs/<name> and the worktree was never
        removed. Resolution now comes from `git worktree list`."""
        repo = self._worktree_repo()
        git(repo, "cherry-pick", "docs/some-checkpoint")
        git(repo, "commit", "--amend", "-qm", "docs: add d (rebased)")

        result = self._run_clean(repo, "docs/some-checkpoint")

        self.assertNotIn("HOOK CRASH", result.stdout + result.stderr)
        self.assertFalse(
            (repo / ".trees/docssome-checkpoint").exists(),
            f"worktree not removed: {result.stdout}{result.stderr}",
        )
        self.assertFalse(self._branch_exists(repo, "docs/some-checkpoint"))

    def test_no_unguarded_force_delete(self):
        """Regression guard. `git branch -D` fails when the branch is still
        checked out in a worktree, and this script runs under `set -e` with an
        ERR trap, so a bare call turns a recoverable condition into an aborted
        run ("HOOK CRASH ... git branch -D"). Every force-delete must go through
        force_delete_branch(), which captures the failure and warns.

        Structural rather than behavioural: once worktree resolution is correct
        the branch is no longer checked out by the time the delete runs, so the
        crash is unreachable through the normal path — but the guard still has to
        hold for locked or stale worktrees.
        """
        source = (ROOT / ".claude/scripts/pr-stack/clean-stack.sh").read_text(encoding="utf-8")
        bare = [
            line.strip()
            for line in source.splitlines()
            if re.search(r"^\s*git branch -D\b", line)
            and "err=$(git branch -D" not in line
        ]

        self.assertEqual(
            bare,
            [],
            "bare `git branch -D` found; route it through force_delete_branch() so a "
            "failed delete warns instead of aborting the script",
        )
        self.assertIn("force_delete_branch()", source)


if __name__ == "__main__":
    unittest.main()
