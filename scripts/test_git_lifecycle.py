"""Hermetic behavioral tests for scripts/ai/git_lifecycle.py."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ai" / "git_lifecycle.py"


def run(
    cwd: Path,
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        list(args),
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"{args} failed ({proc.returncode})\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(cwd, "git", *args, check=check)


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "lifecycle-test@example.com")
    git(path, "config", "user.name", "Lifecycle Test")
    (path / "owned").mkdir()
    (path / "owned" / "tracked.txt").write_text("initial\n")
    (path / "README.md").write_text("fixture\n")
    git(path, "add", "owned/tracked.txt", "README.md")
    git(path, "commit", "-q", "-m", "chore: initialize lifecycle fixture")
    return path


def add_local_origin(repo: Path, root: Path) -> Path:
    origin = root / "origin.git"
    git(root, "init", "-q", "--bare", "-b", "main", str(origin))
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "-u", "origin", "main")
    return origin


def cli(
    repo: Path,
    command: str,
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    proc = run(repo, str(SCRIPT), command, *args, check=check, env=env)
    stream = proc.stdout if proc.returncode == 0 else proc.stderr
    payload = json.loads(stream.strip()) if stream.strip() else {}
    return proc, payload


def start(
    repo: Path,
    *,
    run_id: str = "run-1",
    branch: str = "feature/lifecycle",
    owned: tuple[str, ...] = ("owned",),
    key: str = "start-1",
) -> dict:
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    args = [
        "--run-id",
        run_id,
        "--task",
        "Implement lifecycle fixture",
        "--base-branch",
        "main",
        "--base-sha",
        head,
        "--intended-branch",
        branch,
        "--worktree",
        str(repo),
        "--idempotency-key",
        key,
    ]
    for path in owned:
        args.extend(["--owned-path", path])
    return cli(repo, "start", *args)[1]


def ready(repo: Path, run_id: str = "run-1", key: str = "ready-1") -> dict:
    return cli(
        repo,
        "ready",
        "--run-id",
        run_id,
        "--subject",
        "feat(lifecycle): add deterministic controller",
        "--body",
        "Provide a fail-closed lifecycle decision for every repository state.",
        "--open-tasks",
        "0",
        "--validation",
        '{"name":"unit tests","passed":true}',
        "--idempotency-key",
        key,
    )[1]


def record(
    repo: Path,
    kind: str,
    status: str,
    key: str,
    *,
    source: str | None = None,
    authoritative: bool = True,
    run_id: str = "run-1",
    sha: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    sha = sha or git(repo, "rev-parse", "HEAD").stdout.strip()
    args = [
        "--run-id",
        run_id,
        "--kind",
        kind,
        "--status",
        status,
        "--source",
        source or f"{kind}-authority",
        "--sha",
        sha,
        "--idempotency-key",
        key,
    ]
    if authoritative:
        args.append("--authoritative")
    return cli(repo, "record", *args, check=False)


def inspect(repo: Path, run_id: str = "run-1") -> dict:
    return cli(repo, "inspect", "--run-id", run_id)[1]


def state_paths(repo: Path, run_id: str = "run-1") -> tuple[Path, Path, Path]:
    common_raw = git(repo, "rev-parse", "--git-common-dir").stdout.strip()
    common = Path(common_raw)
    if not common.is_absolute():
        common = (repo / common).resolve()
    root = common / "agent-lifecycle"
    return root / "runs" / f"{run_id}.json", root / "audit.jsonl", root / "repository.lock"


def file_fingerprint(path: Path) -> tuple[int, int, str]:
    stat = path.stat()
    return (
        stat.st_size,
        stat.st_mtime_ns,
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )


class DecisionMatrixTests(unittest.TestCase):
    def test_complete_one_action_progression(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_local_origin(repo, tmp)
            start(repo)
            self.assertEqual(inspect(repo)["action"], "create_stack")

            git(repo, "switch", "-q", "-c", "feature/lifecycle")
            self.assertEqual(inspect(repo)["action"], "awaiting_work")

            (repo / "owned" / "new.txt").write_text("change\n")
            self.assertEqual(inspect(repo)["action"], "editing")

            ready(repo)
            self.assertEqual(inspect(repo)["action"], "commit")

            git(repo, "add", "owned/new.txt")
            git(repo, "commit", "-q", "-m", "feat(lifecycle): add controller fixture")
            self.assertEqual(inspect(repo)["action"], "push")

            git(repo, "push", "-q", "-u", "origin", "feature/lifecycle")
            self.assertEqual(inspect(repo)["action"], "open_pr")

            self.assertEqual(record(repo, "pr", "open", "pr-1")[0].returncode, 0)
            self.assertEqual(inspect(repo)["action"], "wait_ci")

            self.assertEqual(record(repo, "ci", "passing", "ci-1")[0].returncode, 0)
            self.assertEqual(inspect(repo)["action"], "merge_eligible")

            self.assertEqual(record(repo, "merge", "merged", "merge-1")[0].returncode, 0)
            self.assertEqual(inspect(repo)["action"], "sync")

            self.assertEqual(record(repo, "sync", "synced", "sync-1")[0].returncode, 0)
            cleanup = inspect(repo)
            self.assertEqual(cleanup["action"], "cleanup")
            requirements = cleanup["evidence"]["required_before_cleanup"]
            self.assertEqual(
                {item["name"] for item in requirements},
                {"child_stack_safe", "no_active_sessions"},
            )
            self.assertTrue(all(item["provided"] is False for item in requirements))

            halt = cli(
                repo,
                "halt",
                "--run-id",
                "run-1",
                "--status",
                "done",
                "--reason",
                "Lifecycle fixture completed",
                "--idempotency-key",
                "halt-1",
            )[1]
            self.assertTrue(halt["ok"])
            self.assertEqual(inspect(repo)["action"], "done")

    def test_commit_requires_exclusive_owned_dirty_paths(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            start(repo)
            git(repo, "switch", "-q", "-c", "feature/lifecycle")
            (repo / "owned" / "new.txt").write_text("owned\n")
            (repo / "foreign.txt").write_text("foreign\n")
            ready(repo)
            result = inspect(repo)
            self.assertEqual(result["action"], "blocked")
            self.assertEqual(result["reason_code"], "foreign_dirty_paths")
            self.assertEqual(result["evidence"]["foreign_dirty_paths"], ["foreign.txt"])

    def test_non_authoritative_and_stale_facts_never_enable_merge(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_local_origin(repo, tmp)
            start(repo)
            git(repo, "switch", "-q", "-c", "feature/lifecycle")
            (repo / "owned" / "one.txt").write_text("one\n")
            ready(repo)
            git(repo, "add", "owned/one.txt")
            git(repo, "commit", "-q", "-m", "feat: add first lifecycle change")
            git(repo, "push", "-q", "-u", "origin", "feature/lifecycle")
            first_head = git(repo, "rev-parse", "HEAD").stdout.strip()
            record(repo, "pr", "open", "pr-first")
            record(repo, "ci", "passing", "ci-advisory", authoritative=False)
            self.assertEqual(inspect(repo)["action"], "wait_ci")
            record(repo, "ci", "passing", "ci-first")
            self.assertEqual(inspect(repo)["action"], "merge_eligible")

            (repo / "owned" / "two.txt").write_text("two\n")
            git(repo, "add", "owned/two.txt")
            git(repo, "commit", "-q", "-m", "feat: add second lifecycle change")
            git(repo, "push", "-q", "origin", "feature/lifecycle")
            stale = inspect(repo)
            self.assertEqual(stale["action"], "open_pr")
            self.assertTrue(
                any(first_head in note for note in stale["evidence"]["fact_notes"])
            )

            short_sha = git(repo, "rev-parse", "--short", "HEAD").stdout.strip()
            proc, payload = record(
                repo, "ci", "passing", "ci-short", sha=short_sha
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("exact lowercase", payload["error"])

    def test_contradictory_authoritative_sources_block(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            add_local_origin(repo, tmp)
            start(repo)
            git(repo, "switch", "-q", "-c", "feature/lifecycle")
            (repo / "owned" / "one.txt").write_text("one\n")
            ready(repo)
            git(repo, "add", "owned/one.txt")
            git(repo, "commit", "-q", "-m", "feat: add lifecycle change")
            git(repo, "push", "-q", "-u", "origin", "feature/lifecycle")
            record(repo, "pr", "open", "pr-github", source="github")
            record(repo, "pr", "closed", "pr-mirror", source="mirror")
            result = inspect(repo)
            self.assertEqual(result["action"], "blocked")
            self.assertEqual(result["reason_code"], "contradictory_remote_facts")


class GitInspectionTests(unittest.TestCase):
    def test_reports_staged_unstaged_untracked_and_all_paths(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            start(repo)
            git(repo, "switch", "-q", "-c", "feature/lifecycle")
            tracked = repo / "owned" / "tracked.txt"
            tracked.write_text("staged\n")
            git(repo, "add", "owned/tracked.txt")
            tracked.write_text("staged and unstaged\n")
            (repo / "owned" / "untracked.txt").write_text("new\n")
            result = inspect(repo)
            git_state = result["evidence"]["git"]
            self.assertEqual(result["action"], "editing")
            self.assertEqual(git_state["staged_paths"], ["owned/tracked.txt"])
            self.assertEqual(git_state["unstaged_paths"], ["owned/tracked.txt"])
            self.assertEqual(git_state["untracked_paths"], ["owned/untracked.txt"])
            self.assertEqual(
                git_state["changed_paths"],
                ["owned/tracked.txt", "owned/untracked.txt"],
            )

    def test_rename_reports_source_and_destination_paths(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            start(repo)
            git(repo, "switch", "-q", "-c", "feature/lifecycle")
            git(repo, "mv", "owned/tracked.txt", "owned/renamed.txt")
            result = inspect(repo)
            git_state = result["evidence"]["git"]
            self.assertEqual(result["action"], "editing")
            self.assertEqual(
                git_state["changed_paths"],
                ["owned/renamed.txt", "owned/tracked.txt"],
            )
            self.assertEqual(
                git_state["staged_paths"],
                ["owned/renamed.txt", "owned/tracked.txt"],
            )

    def test_conflict_and_each_active_operation_block(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            start(repo)
            git(repo, "switch", "-q", "-c", "feature/lifecycle")
            git_dir = Path(git(repo, "rev-parse", "--absolute-git-dir").stdout.strip())
            probes = {
                "merge": git_dir / "MERGE_HEAD",
                "rebase": git_dir / "rebase-merge",
                "cherry-pick": git_dir / "CHERRY_PICK_HEAD",
                "revert": git_dir / "REVERT_HEAD",
                "bisect": git_dir / "BISECT_LOG",
            }
            for operation, marker in probes.items():
                with self.subTest(operation=operation):
                    if marker.suffix:
                        marker.write_text("fixture\n")
                    else:
                        marker.mkdir()
                    result = inspect(repo)
                    self.assertEqual(result["action"], "blocked")
                    self.assertIn(operation, result["evidence"]["git"]["active_operations"])
                    if marker.is_dir():
                        marker.rmdir()
                    else:
                        marker.unlink()

            git(repo, "switch", "-q", "-c", "side", "main")
            (repo / "owned" / "tracked.txt").write_text("side\n")
            git(repo, "commit", "-qam", "fix: change side")
            git(repo, "switch", "-q", "feature/lifecycle")
            (repo / "owned" / "tracked.txt").write_text("feature\n")
            git(repo, "commit", "-qam", "fix: change feature")
            merge = git(repo, "merge", "side", check=False)
            self.assertNotEqual(merge.returncode, 0)
            result = inspect(repo)
            self.assertEqual(result["action"], "blocked")
            self.assertEqual(result["reason_code"], "active_git_operation")
            self.assertEqual(result["evidence"]["git"]["conflict_paths"], ["owned/tracked.txt"])

    def test_inspect_is_byte_and_mtime_read_only_and_uses_no_network(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            start(repo)
            state, audit, lock = state_paths(repo)
            index = Path(git(repo, "rev-parse", "--git-path", "index").stdout.strip())
            if not index.is_absolute():
                index = (repo / index).resolve()
            watched = [state, audit, lock, index]
            before = {path: file_fingerprint(path) for path in watched}

            real_git = shutil.which("git")
            self.assertIsNotNone(real_git)
            bin_dir = tmp / "bin"
            bin_dir.mkdir()
            wrapper = bin_dir / "git"
            wrapper.write_text(
                "#!/bin/sh\n"
                'case "$1" in fetch|pull|push|ls-remote) exit 97 ;; esac\n'
                f'exec "{real_git}" "$@"\n'
            )
            wrapper.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            proc, result = cli(
                repo, "inspect", "--run-id", "run-1", check=False, env=env
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(result["action"], "create_stack")
            after = {path: file_fingerprint(path) for path in watched}
            self.assertEqual(after, before)


class ValidationAndPersistenceTests(unittest.TestCase):
    def test_owned_path_normalization_rejects_escapes_git_and_duplicates(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            outside = tmp / "outside"
            outside.mkdir()
            (repo / "escape").symlink_to(outside, target_is_directory=True)
            cases = [
                (("/absolute",), "repository-relative"),
                (("../outside",), "may not contain"),
                ((".git/config",), "may not address"),
                (("owned/item", "owned/./item"), "duplicate"),
                (("escape/item",), "escapes"),
            ]
            base_sha = git(repo, "rev-parse", "HEAD").stdout.strip()
            for index, (paths, expected) in enumerate(cases):
                with self.subTest(paths=paths):
                    args = [
                        "--run-id",
                        f"bad-{index}",
                        "--task",
                        "Reject unsafe owned path",
                        "--base-branch",
                        "main",
                        "--base-sha",
                        base_sha,
                        "--intended-branch",
                        "feature/safe-path",
                        "--idempotency-key",
                        f"bad-key-{index}",
                    ]
                    for path in paths:
                        args.extend(["--owned-path", path])
                    proc, payload = cli(repo, "start", *args, check=False)
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertIn(expected, payload["error"])

    def test_branch_and_ready_validation_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            base_sha = git(repo, "rev-parse", "HEAD").stdout.strip()
            proc, payload = cli(
                repo,
                "start",
                "--run-id",
                "bad-branch",
                "--task",
                "Reject unsupported branch",
                "--base-branch",
                "main",
                "--base-sha",
                base_sha,
                "--intended-branch",
                "topic/not-supported",
                "--owned-path",
                "owned",
                "--idempotency-key",
                "bad-branch-key",
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("supported prefix", payload["error"])

            start(repo)
            git(repo, "switch", "-q", "-c", "feature/lifecycle")
            (repo / "owned" / "new.txt").write_text("change\n")
            proc, payload = cli(
                repo,
                "ready",
                "--run-id",
                "run-1",
                "--subject",
                "not conventional",
                "--body",
                "This body would otherwise be meaningful.",
                "--open-tasks",
                "0",
                "--validation",
                "tests=pass",
                "--idempotency-key",
                "bad-ready-1",
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("conventional", payload["error"])
            proc, payload = cli(
                repo,
                "ready",
                "--run-id",
                "run-1",
                "--subject",
                "feat: valid subject",
                "--body",
                "This body explains the required behavior.",
                "--open-tasks",
                "1",
                "--validation",
                "tests=pass",
                "--idempotency-key",
                "bad-ready-2",
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("open tasks equal zero", payload["error"])

    def test_idempotent_writes_do_not_duplicate_state_or_audit(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            first = start(repo)
            state, audit, _ = state_paths(repo)
            state_before = file_fingerprint(state)
            audit_before = file_fingerprint(audit)
            second = start(repo)
            self.assertFalse(first["idempotent"])
            self.assertTrue(second["idempotent"])
            self.assertEqual(file_fingerprint(state), state_before)
            self.assertEqual(file_fingerprint(audit), audit_before)
            self.assertEqual(len(audit.read_text().splitlines()), 1)

            git(repo, "switch", "-q", "-c", "feature/lifecycle")
            (repo / "owned" / "new.txt").write_text("change\n")
            ready(repo)
            ready_state = file_fingerprint(state)
            ready_audit = file_fingerprint(audit)
            duplicate = ready(repo)
            self.assertTrue(duplicate["idempotent"])
            self.assertEqual(file_fingerprint(state), ready_state)
            self.assertEqual(file_fingerprint(audit), ready_audit)
            self.assertEqual(len(audit.read_text().splitlines()), 2)

            proc, payload = cli(
                repo,
                "ready",
                "--run-id",
                "run-1",
                "--subject",
                "fix: different payload",
                "--body",
                "This payload intentionally differs from the original ready event.",
                "--open-tasks",
                "0",
                "--validation",
                "tests=pass",
                "--idempotency-key",
                "ready-1",
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("different operation or payload", payload["error"])

    def test_lock_contention_times_out_without_corruption(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            start(repo)
            git(repo, "switch", "-q", "-c", "feature/lifecycle")
            (repo / "owned" / "new.txt").write_text("change\n")
            state, audit, lock = state_paths(repo)
            before = (file_fingerprint(state), file_fingerprint(audit))
            with lock.open("r+") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                proc, payload = cli(
                    repo,
                    "ready",
                    "--run-id",
                    "run-1",
                    "--subject",
                    "feat: valid locked update",
                    "--body",
                    "This update must wait for the repository lifecycle lock.",
                    "--open-tasks",
                    "0",
                    "--validation",
                    "tests=pass",
                    "--idempotency-key",
                    "ready-locked",
                    "--lock-timeout",
                    "0.05",
                    check=False,
                )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(payload["error_type"], "LockTimeoutError")
            self.assertEqual((file_fingerprint(state), file_fingerprint(audit)), before)
            json.loads(state.read_text())
            for line in audit.read_text().splitlines():
                json.loads(line)

    def test_state_is_shared_across_linked_worktrees(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = init_repo(tmp / "repo")
            git(repo, "branch", "feature/linked")
            linked = tmp / "linked"
            git(repo, "worktree", "add", "-q", str(linked), "feature/linked")
            start(
                linked,
                run_id="linked-run",
                branch="feature/linked",
                key="linked-start",
            )
            state, _, _ = state_paths(repo, "linked-run")
            self.assertTrue(state.is_file())
            result = inspect(repo, "linked-run")
            self.assertEqual(result["action"], "awaiting_work")
            self.assertEqual(result["evidence"]["git"]["root"], str(linked.resolve()))


if __name__ == "__main__":
    unittest.main()
