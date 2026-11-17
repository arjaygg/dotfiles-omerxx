import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

GUARD = Path(os.environ.get("GUARD_UNDER_TEST") or Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "worktree-guard.py")
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def run_git(cwd, *args):
    env = {"PATH": os.environ["PATH"], "HOME": str(cwd), **GIT_ENV}
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=env)


def make_repo(path, branch="main", opt_in=True):
    path.mkdir(parents=True)
    run_git(path, "init", "-q", "-b", branch)
    if opt_in:
        run_git(path, "config", "worktreeguard.enabled", "true")
    (path / "f.txt").write_text("x")
    run_git(path, "add", "f.txt")
    run_git(path, "commit", "-q", "-m", "init")
    return path


class WorktreeGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.primary = make_repo(self.base / "primary")

    def call(self, tool, tool_input, cwd=None, **env):
        payload = {
            "tool_name": tool,
            "tool_input": tool_input,
            "cwd": str(cwd or self.primary),
        }
        child_env = {"PATH": os.environ["PATH"], **env}
        done = subprocess.run(
            ["python3", "-I", str(GUARD)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=child_env,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        if not done.stdout.strip():
            return "allow"
        return json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"]

    def edit(self, path, **kwargs):
        return self.call("Edit", {"file_path": str(path)}, **kwargs)

    def test_edit_in_primary_on_main_is_denied(self):
        self.assertEqual(self.edit(self.primary / "f.txt"), "ask")
        self.assertEqual(self.edit(self.primary / "new" / "deep.txt"), "ask")
        self.assertEqual(self.call("Write", {"file_path": str(self.primary / "g.txt")}), "ask")
        self.assertEqual(
            self.call("NotebookEdit", {"notebook_path": str(self.primary / "n.ipynb")}), "ask"
        )

    def test_edit_in_a_linked_worktree_is_allowed(self):
        wt = self.base / "wt"
        run_git(self.primary, "worktree", "add", "-q", "-b", "feature", str(wt))
        self.assertEqual(self.edit(wt / "f.txt"), "allow")
        # Even when the worktree is on main-named branch history, the check is the linked dir.
        self.assertEqual(self.call("Bash", {"command": "git commit -m x"}, cwd=wt), "allow")

    def test_primary_on_a_feature_branch_is_allowed(self):
        run_git(self.primary, "checkout", "-q", "-b", "feature")
        self.assertEqual(self.edit(self.primary / "f.txt"), "allow")

    def test_detached_head_in_primary_is_denied(self):
        run_git(self.primary, "checkout", "-q", "--detach")
        self.assertEqual(self.edit(self.primary / "f.txt"), "ask")

    def test_paths_outside_any_repo_are_allowed(self):
        scratch = self.base / "scratch"
        scratch.mkdir()
        self.assertEqual(self.edit(scratch / "notes.txt"), "allow")
        self.assertEqual(self.edit(scratch / "missing" / "notes.txt"), "allow")

    def test_a_repository_that_has_not_opted_in_is_allowed(self):
        other = make_repo(self.base / "other", opt_in=False)
        self.assertEqual(self.edit(other / "f.txt"), "allow")
        self.assertEqual(self.edit(other / "f.txt", WORKTREE_GUARD_MODE="deny"), "allow")

    def test_bash_git_verbs_are_judged_by_cwd(self):
        for command in ("git commit -m x", "git -C . rebase main", "cd x && git merge feature"):
            self.assertEqual(self.call("Bash", {"command": command}), "ask", command)
        for command in ("git status", "git log --oneline", "git diff", "ls"):
            self.assertEqual(self.call("Bash", {"command": command}), "allow", command)

    def test_bash_git_commit_in_a_linked_worktree_is_allowed(self):
        wt = self.base / "wt"
        run_git(self.primary, "worktree", "add", "-q", "-b", "feature", str(wt))
        self.assertEqual(self.call("Bash", {"command": "git commit -m x"}, cwd=wt), "allow")

    def test_mode_off_and_ask(self):
        target = self.primary / "f.txt"
        self.assertEqual(self.edit(target, WORKTREE_GUARD_MODE="off"), "allow")
        self.assertEqual(self.edit(target, WORKTREE_GUARD_MODE="ask"), "ask")
        self.assertEqual(self.edit(target, WORKTREE_GUARD_MODE="deny"), "deny")

    def test_deny_reason_names_enter_worktree(self):
        done = subprocess.run(
            ["python3", "-I", str(GUARD)],
            input=json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {"file_path": str(self.primary / "f.txt")},
                    "cwd": str(self.primary),
                }
            ),
            capture_output=True,
            text=True,
            env={"PATH": os.environ["PATH"]},
        )
        reason = json.loads(done.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("EnterWorktree", reason)

    def test_unreadable_input_asks_instead_of_allowing(self):
        done = subprocess.run(
            ["python3", "-I", str(GUARD)],
            input="not json",
            capture_output=True,
            text=True,
            env={"PATH": os.environ["PATH"]},
        )
        self.assertEqual(done.returncode, 0)
        decision = json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"]
        self.assertEqual(decision, "ask")

    def test_per_repo_mode_deny_off_and_env_override(self):
        target = self.primary / "f.txt"
        run_git(self.primary, "config", "worktreeguard.mode", "deny")
        self.assertEqual(self.edit(target), "deny")
        self.assertEqual(self.edit(target, WORKTREE_GUARD_MODE="ask"), "ask")
        self.assertEqual(self.edit(target, WORKTREE_GUARD_MODE="off"), "allow")
        run_git(self.primary, "config", "worktreeguard.mode", "off")
        self.assertEqual(self.edit(target), "allow")
        run_git(self.primary, "config", "worktreeguard.mode", "bogus")
        self.assertEqual(self.edit(target), "ask")
        run_git(self.primary, "config", "--unset", "worktreeguard.mode")
        self.assertEqual(self.edit(target), "ask")

    def test_per_repo_deny_applies_to_a_linked_worktree_as_allow(self):
        run_git(self.primary, "config", "worktreeguard.mode", "deny")
        wt = self.base / "wt"
        run_git(self.primary, "worktree", "add", "-q", "-b", "feature", str(wt))
        self.assertEqual(self.edit(wt / "f.txt"), "allow")
        self.assertEqual(self.call("Bash", {"command": "echo hi > out.txt"}, cwd=wt), "allow")

    def test_shell_writes_in_primary_follow_repo_mode(self):
        run_git(self.primary, "config", "worktreeguard.mode", "deny")
        p = self.primary
        commands = [
            "cat > f.txt <<EOF\nhello\nEOF",
            "echo hi >> notes.md",
            "echo hi > %s/a.txt" % p,
            "echo hi 2> err.log",
            "python3 -c \"open('x.txt','w').write('y')\"",
            "python3 -c \"from pathlib import Path; Path('x').write_text('y')\"",
            "cp /tmp/a new.txt",
            "mv f.txt g.txt",
            "rm -rf build",
            "mkdir -p docs/new",
            "touch x",
            "sed -i 's/a/b/' f.txt",
            "sed -i '' 's/a/b/' f.txt",
            "echo x | tee out.txt",
            "ln -s f.txt link",
            "dd if=/dev/zero of=blob bs=1 count=1",
            "git commit -m x",
            "cd /tmp && rm %s/f.txt" % p,
            "cd sub && touch x",
            "ls && touch x",
        ]
        for command in commands:
            self.assertEqual(self.call("Bash", {"command": command}), "deny", command)

    def test_shell_reads_tests_and_safe_git_pass(self):
        run_git(self.primary, "config", "worktreeguard.mode", "deny")
        commands = [
            "ls -la",
            "cat f.txt",
            "grep -rn x . | head",
            "git status",
            "git log --oneline -5",
            "git diff HEAD",
            "git show HEAD",
            "git worktree add ../wt2 -b other",
            "python3 -m pytest -q",
            "python3 -c \"print(open('f.txt').read())\"",
            "echo hi > /dev/null",
            "ls 2>&1 | head",
            "cp f.txt /tmp/copy.txt",
            "echo hi > /tmp/scratch.txt",
            "cd /tmp && touch x",
            "cat <<EOF\nrm -rf x > y\nEOF",
            "sed 's/a/b/' f.txt",
        ]
        for command in commands:
            self.assertEqual(self.call("Bash", {"command": command}), "allow", command)

    def test_shell_write_into_primary_from_another_cwd_is_judged(self):
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        self.assertEqual(
            self.call("Bash", {"command": "echo x > %s/f.txt" % self.primary}, cwd=elsewhere), "ask"
        )
        self.assertEqual(
            self.call("Bash", {"command": "mkdir %s/new" % self.primary}, cwd=elsewhere), "ask"
        )
        wt = self.base / "wt"
        run_git(self.primary, "worktree", "add", "-q", "-b", "feature", str(wt))
        self.assertEqual(
            self.call("Bash", {"command": "touch %s/x" % self.primary}, cwd=wt), "ask"
        )

    def test_shell_write_in_primary_on_feature_branch_or_unopted_repo_is_allowed(self):
        other = make_repo(self.base / "other", opt_in=False)
        self.assertEqual(self.call("Bash", {"command": "touch x"}, cwd=other), "allow")
        run_git(self.primary, "checkout", "-q", "-b", "feature")
        self.assertEqual(self.call("Bash", {"command": "touch x"}), "allow")

    def test_review_false_allows_are_judged(self):
        run_git(self.primary, "config", "worktreeguard.mode", "deny")
        commands = [
            "cat <<'EOF' > README.md\nhi\nEOF",
            "cat > README.md <<EOF\nhi\nEOF",
            "echo x>README.md",
            "cmd 2>out.log",
            "git pull",
            "git reset --hard HEAD~1",
            "git checkout -- f.txt",
            "git -C %s restore f.txt" % self.primary,
            "git stash",
            "git add -A",
            "sed -i '' 's/a/b/' f.txt",
            "perl -pi -e 's/a/b/' f.txt",
            "(cd sub && touch x)",
            "python3 -c \"open('docs/x.md','w').write('y')\"",
            "python3 -c \"open('/etc/hosts').read(); open('out','w')\"",
            "sudo -u nobody rm f.txt",
        ]
        for command in commands:
            self.assertEqual(self.call("Bash", {"command": command}), "deny", command)

    def test_review_false_asks_are_allowed(self):
        run_git(self.primary, "config", "worktreeguard.mode", "deny")
        commands = [
            "git log --oneline -- merge",
            "git show HEAD -- apply.py",
            "git stash list",
            "sed -i '' 's/a/b/' /tmp/f",
            "perl -pi -e 's/a/b/' /tmp/f",
            "chmod 755 /tmp/f",
            "(cd /tmp && rm x)",
            "pushd /tmp && rm x",
            "cd -- /tmp && rm x",
            "grep '>' README.md",
            "python3 -c \"open('/tmp/x','w').write('y')\"",
            "echo a>/tmp/x",
        ]
        for command in commands:
            self.assertEqual(self.call("Bash", {"command": command}), "allow", command)

    def test_git_c_pull_from_unrelated_cwd_is_judged(self):
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        self.assertEqual(
            self.call("Bash", {"command": "git -C %s pull" % self.primary}, cwd=elsewhere), "ask"
        )

    def test_other_tools_are_ignored(self):
        self.assertEqual(self.call("Read", {"file_path": str(self.primary / "f.txt")}), "allow")


if __name__ == "__main__":
    unittest.main()
