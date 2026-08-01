"Behavioral coverage for lifecycle safety foundation entrypoints."

import errno
import json
import os
import pty
import select
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STACK_SHIP = ROOT / ".claude" / "scripts" / "stack-ship.sh"
STACK_SHIP_COMPAT = ROOT / "scripts" / "stack-ship.sh"
CHECKPOINT = ROOT / "scripts" / "ai" / "checkpoint.sh"
TASK_GATE = ROOT / ".claude" / "hooks" / "task-gate.sh"
CREATE_STACK = ROOT / ".claude" / "scripts" / "pr-stack" / "create-stack.sh"
CURSOR_GUARD = ROOT / ".cursor" / "hooks" / "before-shell-git-commit.sh"
CURSOR_HOOKS = ROOT / ".cursor" / "hooks.json"
CI_WATCH = ROOT / "ai" / "skills" / "ci-watch" / "SKILL.md"


def run(cwd: Path, *args: str, env=None, input_text=None, check=True):
    proc = subprocess.run(
        list(args), cwd=str(cwd), env=env, input=input_text,
        capture_output=True, text=True,
    )
    if check and proc.returncode != 0:
        raise AssertionError(f"{args} failed ({proc.returncode}): {proc.stderr}")
    return proc


def git(cwd: Path, *args: str, check=True):
    return run(cwd, "git", *args, check=check)


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "lifecycle-test@example.com")
    git(path, "config", "user.name", "Lifecycle Test")
    (path / "README.md").write_text("initial\n")
    git(path, "add", "README.md")
    git(path, "commit", "-q", "-m", "chore: initialize fixture")
    return path


def write_executable(path: Path, text: str):
    path.write_text(text)
    path.chmod(0o755)


GH_STUB = r'''#!/usr/bin/env bash
set -u
printf '%s\n' "$*" >> "$GH_LOG"
if [[ "$1" == "pr" && "$2" == "view" ]]; then
  branch="$3"
  if [[ "$*" == *"state,isDraft,mergeable,mergeStateStatus,headRefOid,baseRefName"* ]]; then
    head_oid="${GH_HEAD_OVERRIDE:-}"
    [[ -n "$head_oid" ]] || head_oid=$(git rev-parse "refs/heads/$branch")
    jq -nc --arg state "$GH_PR_STATE" --argjson draft "$GH_DRAFT" \
      --arg mergeable "$GH_MERGEABLE" --arg merge_state "$GH_MERGE_STATE" \
      --arg head "$head_oid" --arg base "$GH_BASE" \
      '{state:$state,isDraft:$draft,mergeable:$mergeable,mergeStateStatus:$merge_state,headRefOid:$head,baseRefName:$base}'
    exit 0
  elif [[ "$*" == *"--json baseRefName"* ]]; then
    printf '%s\n' "$GH_BASE"
    exit 0
  elif [[ "$*" == *"--json state"* ]]; then
    printf '%s\n' "$GH_POST_STATE"
    exit 0
  fi
elif [[ "$1" == "pr" && "$2" == "checks" ]]; then
  if [[ " $* " == *" --required "* ]]; then
    printf '%s\n' "$GH_REQUIRED_JSON"
    exit "${GH_REQUIRED_RC:-0}"
  fi
  printf '%s\n' "$GH_CHECKS_JSON"
  exit "${GH_CHECKS_RC:-0}"
elif [[ "$1" == "pr" && "$2" == "merge" ]]; then
  if [[ "$3" == "${GH_FAIL_BRANCH:-}" ]]; then
    echo "simulated merge failure for $3" >&2
    exit 1
  fi
  exit 0
elif [[ "$1" == "pr" && "$2" == "edit" ]]; then
  exit 0
fi
echo "unexpected gh invocation: $*" >&2
exit 64
'''


class StackShipSafetyTests(unittest.TestCase):
    def make_fixture(self, tmp: Path):
        repo = init_repo(tmp / "repo")
        git(repo, "checkout", "-q", "-b", "feature/root")
        (repo / "root.txt").write_text("root\n")
        git(repo, "add", "root.txt")
        git(repo, "commit", "-q", "-m", "feat: add root")
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        gh_log = tmp / "gh.log"
        write_executable(bin_dir / "gh", GH_STUB)
        env = os.environ.copy()
        env.update({
            "PATH": f"{bin_dir}:{env['PATH']}", "GH_LOG": str(gh_log),
            "GH_PR_STATE": "OPEN", "GH_DRAFT": "false",
            "GH_MERGEABLE": "MERGEABLE", "GH_MERGE_STATE": "CLEAN",
            "GH_HEAD_OVERRIDE": "", "GH_BASE": "main", "GH_POST_STATE": "MERGED",
            "GH_REQUIRED_JSON": '[{"name":"ci","bucket":"pass","state":"SUCCESS"}]',
            "GH_CHECKS_JSON": '[{"name":"ci","bucket":"pass","state":"SUCCESS"}]',
            "GH_REQUIRED_RC": "0", "GH_CHECKS_RC": "0", "GH_FAIL_BRANCH": "",
        })
        return repo, gh_log, env

    def run_ship(self, repo: Path, env, *extra: str):
        return run(repo, str(STACK_SHIP), *extra, "--branch", "feature/root",
                   env=env, check=False)

    def test_refuses_unsafe_pr_and_check_states_without_merging(self):
        cases = [
            ({"GH_DRAFT": "true"}, "draft"),
            ({"GH_PR_STATE": "CLOSED"}, "not open"),
            ({"GH_MERGEABLE": "CONFLICTING", "GH_MERGE_STATE": "DIRTY"}, "conflicting"),
            ({"GH_HEAD_OVERRIDE": "0" * 40}, "does not exactly match"),
            ({"GH_REQUIRED_JSON": "[]"}, "No required checks"),
            ({"GH_REQUIRED_JSON": '[{"name":"ci","bucket":"pending"}]',
              "GH_CHECKS_JSON": '[{"name":"ci","bucket":"pending"}]'}, "pending"),
            ({"GH_REQUIRED_JSON": '[{"name":"ci","bucket":"fail"}]',
              "GH_CHECKS_JSON": '[{"name":"ci","bucket":"fail"}]'}, "failed"),
            ({"GH_REQUIRED_JSON": '[{"name":"ci","bucket":"mystery"}]',
              "GH_CHECKS_JSON": '[{"name":"ci","bucket":"mystery"}]'}, "unknown"),
        ]
        with tempfile.TemporaryDirectory() as td:
            repo, gh_log, base_env = self.make_fixture(Path(td))
            for overrides, expected in cases:
                with self.subTest(expected=expected):
                    gh_log.write_text("")
                    env = base_env.copy()
                    env.update(overrides)
                    proc = self.run_ship(repo, env, "--dry-run")
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertIn(expected.lower(), proc.stderr.lower())
                    self.assertNotIn("pr merge", gh_log.read_text())

    def test_merge_is_server_auto_merge_pinned_to_exact_local_head(self):
        with tempfile.TemporaryDirectory() as td:
            repo, gh_log, env = self.make_fixture(Path(td))
            head_sha = git(repo, "rev-parse", "refs/heads/feature/root").stdout.strip()
            proc = self.run_ship(repo, env, "--yes", "--reason", "approved by test")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls = [line for line in gh_log.read_text().splitlines()
                     if line.startswith("pr merge ")]
            self.assertEqual(len(calls), 1)
            self.assertIn("--auto", calls[0])
            self.assertIn(f"--match-head-commit {head_sha}", calls[0])
            self.assertNotIn("--admin", calls[0])

    def test_unattended_multi_branch_shipment_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            repo, gh_log, env = self.make_fixture(Path(td))
            git(repo, "checkout", "-q", "-b", "feature/dependent", "feature/root")
            (repo / "dependent.txt").write_text("dependent\n")
            git(repo, "add", "dependent.txt")
            git(repo, "commit", "-q", "-m", "feat: add dependent")
            git(repo, "checkout", "-q", "feature/root")
            proc = self.run_ship(repo, env, "--yes", "--reason", "approved by test")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("Multi-branch shipment requires", proc.stderr)
            self.assertNotIn("pr merge", gh_log.read_text())

    def test_dependent_failure_stops_before_later_dependents(self):
        with tempfile.TemporaryDirectory() as td:
            repo, gh_log, env = self.make_fixture(Path(td))
            for branch in ("feature/dep-a", "feature/dep-b"):
                git(repo, "checkout", "-q", "-b", branch, "feature/root")
                name = branch.rsplit("/", 1)[1]
                (repo / f"{name}.txt").write_text(f"{name}\n")
                git(repo, "add", f"{name}.txt")
                git(repo, "commit", "-q", "-m", f"feat: add {name}")
            git(repo, "checkout", "-q", "feature/root")
            env["GH_FAIL_BRANCH"] = "feature/dep-a"
            master_fd, slave_fd = pty.openpty()
            proc = subprocess.Popen(
                [str(STACK_SHIP), "--branch", "feature/root"],
                cwd=str(repo),
                env=env,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
            )
            os.close(slave_fd)
            output = bytearray()
            confirmation_sent = False
            deadline = time.monotonic() + 15
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        proc.kill()
                        proc.wait()
                        self.fail(f"stack-ship timed out: {output.decode(errors='replace')}")
                    ready, _, _ = select.select(
                        [master_fd], [], [], min(remaining, 0.25)
                    )
                    if ready:
                        try:
                            chunk = os.read(master_fd, 4096)
                        except OSError as exc:
                            if exc.errno == errno.EIO:
                                break
                            raise
                        if not chunk:
                            break
                        output.extend(chunk)
                        if (
                            not confirmation_sent
                            and b"Continue? (y/n)" in output
                        ):
                            os.write(master_fd, b"y\n")
                            confirmation_sent = True
                    if proc.poll() is not None and not ready:
                        break
            finally:
                os.close(master_fd)
            returncode = proc.wait(timeout=5)
            transcript = output.decode(errors="replace")
            self.assertTrue(confirmation_sent, transcript)
            self.assertNotEqual(returncode, 0, transcript)
            calls = [line for line in gh_log.read_text().splitlines()
                     if line.startswith("pr merge ")]
            self.assertTrue(any("feature/root" in line for line in calls))
            self.assertTrue(any("feature/dep-a" in line for line in calls))
            self.assertFalse(any("feature/dep-b" in line for line in calls))


class CompatibilityAndProducerTests(unittest.TestCase):
    def test_legacy_stack_ship_delegates_to_canonical_entrypoint(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            canonical = run(cwd, str(STACK_SHIP), "--invalid-test-option", check=False)
            compat = run(cwd, str(STACK_SHIP_COMPAT), "--invalid-test-option", check=False)
            self.assertEqual(compat.returncode, canonical.returncode)
            self.assertEqual(compat.stderr, canonical.stderr)
        source = STACK_SHIP_COMPAT.read_text()
        self.assertIn("../.claude/scripts/stack-ship.sh", source)
        self.assertNotIn("gh pr merge", source)

    def test_ci_watch_records_full_sha_and_has_no_deploy_side_effect(self):
        source = CI_WATCH.read_text()
        self.assertIn("**SHA:** <HEAD_SHA>", source)
        self.assertIn("**SHA:** ${HEAD_SHA}", source)
        self.assertNotIn("**Commit:**", source)
        self.assertNotIn("gh workflow run", source)
        self.assertNotIn("deploy", source.lower())


class CheckpointAndGateTests(unittest.TestCase):
    def make_checkpoint_harness(self, tmp: Path):
        harness = tmp / "harness" / "scripts" / "ai"
        harness.mkdir(parents=True)
        shutil.copy2(CHECKPOINT, harness / "checkpoint.sh")
        commit_log = tmp / "commit-args.log"
        staged_log = tmp / "staged.log"
        write_executable(harness / "commit.sh", f'''#!/usr/bin/env bash
printf '%s\\n' "$@" > "{commit_log}"
git diff --cached --name-only > "{staged_log}"
''')
        return harness / "checkpoint.sh", commit_log, staged_log

    def test_checkpoint_requires_and_stages_only_explicit_paths(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            checkpoint, commit_log, staged_log = self.make_checkpoint_harness(tmp)
            (repo / "selected.txt").write_text("selected\n")
            (repo / "unrelated.txt").write_text("unrelated\n")
            missing = run(repo, str(checkpoint), "-m", "save work", check=False)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("explicit path", missing.stderr)
            proc = run(repo, str(checkpoint), "-m", "save selected work", "--",
                       "selected.txt", check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(staged_log.read_text().splitlines(), ["selected.txt"])
            self.assertIn("chore(checkpoint): save selected work", commit_log.read_text())
            self.assertNotIn("unrelated.txt",
                             git(repo, "diff", "--cached", "--name-only").stdout)

    def test_checkpoint_uses_only_the_canonical_commit_path(self):
        source = CHECKPOINT.read_text()
        self.assertNotIn("git add .", source)
        self.assertNotIn("git commit", source)
        self.assertNotIn("--no-verify", source)
        self.assertIn('"$SCRIPT_DIR/commit.sh"', source)

    def test_task_gate_emits_top_level_stop_block(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            config = home / ".dotfiles" / ".claude" / "hooks" / "hook-config.yaml"
            config.parent.mkdir(parents=True)
            config.write_text("task-gate: block\n")
            env = os.environ.copy()
            env["HOME"] = str(home)
            env.pop("CLAUDE_SESSION_ID", None)
            proc = run(ROOT, str(TASK_GATE), env=env,
                       input_text='{"background_tasks":[{}]}', check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(set(payload), {"decision", "reason"})
            self.assertEqual(payload["decision"], "block")
            self.assertIn("background task", payload["reason"])


class CreateStackSafetyTests(unittest.TestCase):
    def prepare(self, tmp: Path, ignored: bool):
        repo = init_repo(tmp / "repo")
        if ignored:
            (repo / ".gitignore").write_text(".trees/\n.env\n")
            git(repo, "add", ".gitignore")
            git(repo, "commit", "-q", "-m", "chore: ignore local files")
        (repo / ".git" / ".graphite_repo_config").write_text("{}\n")
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        gt_log = tmp / "gt.log"
        write_executable(bin_dir / "gt", f'''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "{gt_log}"
exit 0
''')
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        return repo, gt_log, env

    def test_create_stack_refuses_when_trees_is_not_already_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            repo, _, env = self.prepare(Path(td), ignored=False)
            proc = run(repo, str(CREATE_STACK), "feature/new", "main",
                       env=env, check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("must already be ignored", proc.stderr)
            self.assertFalse((repo / ".trees").exists())
            self.assertFalse((repo / ".gitignore").exists())

    def test_create_stack_preserves_local_files_and_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            repo, gt_log, env = self.prepare(Path(td), ignored=True)
            (repo / ".env").write_text("SECRET=fixture-only\n")
            before_ignore = (repo / ".gitignore").read_text()
            git(repo, "update-ref", "refs/branch-metadata/keep", "HEAD")
            proc = run(repo, str(CREATE_STACK), "feature/new", "main",
                       env=env, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            worktree = repo / ".trees" / "new"
            self.assertTrue(worktree.is_dir())
            self.assertFalse((worktree / ".env").exists())
            self.assertEqual((repo / ".gitignore").read_text(), before_ignore)
            self.assertEqual(git(repo, "rev-parse", "refs/branch-metadata/keep").returncode, 0)
            self.assertEqual(gt_log.read_text().splitlines(),
                             ["branch track feature/new --parent main"])

    def test_create_stack_uses_verified_exact_ancestor_when_base_moves(self):
        with tempfile.TemporaryDirectory() as td:
            repo, _, env = self.prepare(Path(td), ignored=True)
            exact_base = git(repo, "rev-parse", "HEAD").stdout.strip()
            (repo / "later.txt").write_text("branch moved\n")
            git(repo, "add", "later.txt")
            git(repo, "commit", "-q", "-m", "chore: move named base")

            proc = run(repo, str(CREATE_STACK), "feature/pinned", "main",
                       "--base-sha", exact_base, env=env, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(git(repo / ".trees" / "pinned", "rev-parse", "HEAD").stdout.strip(),
                             exact_base)

    def test_create_stack_refuses_non_exact_or_non_ancestor_base_sha(self):
        with tempfile.TemporaryDirectory() as td:
            repo, _, env = self.prepare(Path(td), ignored=True)
            head = git(repo, "rev-parse", "HEAD").stdout.strip()
            abbreviated = run(repo, str(CREATE_STACK), "feature/short", "main",
                              "--base-sha", head[:12], env=env, check=False)
            self.assertNotEqual(abbreviated.returncode, 0)
            self.assertIn("exact lowercase", abbreviated.stderr)

            git(repo, "checkout", "-q", "--orphan", "unrelated")
            git(repo, "rm", "-q", "-rf", ".")
            (repo / "orphan.txt").write_text("unrelated\n")
            git(repo, "add", "orphan.txt")
            git(repo, "commit", "-q", "-m", "chore: unrelated")
            unrelated = git(repo, "rev-parse", "HEAD").stdout.strip()
            git(repo, "checkout", "-q", "main")
            rejected = run(repo, str(CREATE_STACK), "feature/unrelated", "main",
                           "--base-sha", unrelated, env=env, check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("not an ancestor", rejected.stderr)

    def test_create_stack_rejects_legacy_initial_commit_argument(self):
        with tempfile.TemporaryDirectory() as td:
            repo, _, env = self.prepare(Path(td), ignored=True)
            proc = run(repo, str(CREATE_STACK), "feature/new", "main", "initial commit",
                       env=env, check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("Initial commit creation is not supported", proc.stderr)
            self.assertFalse((repo / ".trees").exists())

    def test_create_stack_contains_no_broad_repair_or_secret_copy(self):
        source = CREATE_STACK.read_text()
        for forbidden in ("cp .env", ">> .gitignore", "git commit", "git pack-refs",
                          "git update-ref -d", "gt repo fix"):
            self.assertNotIn(forbidden, source)


class CursorCommitGuardTests(unittest.TestCase):
    def test_guard_reads_command_and_cwd_from_payload(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            repo = init_repo(Path(td) / "repo with spaces")
            expected_hooks = home / ".dotfiles" / "git" / "hooks"
            git(repo, "config", "core.hooksPath", str(expected_hooks))
            env = os.environ.copy()
            env["HOME"] = str(home)
            denied = run(repo, str(CURSOR_GUARD), env=env,
                         input_text=json.dumps({"command": 'git commit -m "raw"',
                                                "cwd": str(repo)}), check=False)
            self.assertEqual(denied.returncode, 0, denied.stderr)
            self.assertEqual(json.loads(denied.stdout)["permission"], "deny")
            allowed = run(repo, str(CURSOR_GUARD), env=env,
                          input_text=json.dumps({"command": "git status", "cwd": str(repo)}),
                          check=False)
            self.assertEqual(json.loads(allowed.stdout)["permission"], "allow")

    def test_guard_is_registered_in_cursor_hooks(self):
        config = json.loads(CURSOR_HOOKS.read_text())
        commands = [entry["command"]
                    for entry in config["hooks"]["beforeShellExecution"]]
        self.assertTrue(any("before-shell-git-commit.sh" in command
                            for command in commands))


if __name__ == "__main__":
    unittest.main()
