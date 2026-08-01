"""Hermetic behavioral coverage for the deterministic git lifecycle controller."""

from __future__ import annotations

import ast
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ai" / "git_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("git_lifecycle_under_test", SCRIPT)
LIFECYCLE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LIFECYCLE
SPEC.loader.exec_module(LIFECYCLE)


def run(
    cwd: Path,
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        list(args), cwd=str(cwd), env=env, capture_output=True, text=True, check=False
    )
    if check and proc.returncode:
        raise AssertionError(
            f"{args} failed ({proc.returncode})\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(cwd, "git", *args, check=check)


def init_repo(path: Path, *, origin: bool = False) -> tuple[Path, Path | None]:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "lifecycle-test@example.com")
    git(path, "config", "user.name", "Lifecycle Test")
    (path / "owned").mkdir()
    (path / "owned" / "tracked.txt").write_text("initial\n")
    (path / "README.md").write_text("fixture\n")
    git(path, "add", "owned/tracked.txt", "README.md")
    git(path, "commit", "-q", "-m", "chore: initialize lifecycle fixture")
    if not origin:
        return path, None
    bare = path.parent / "origin.git"
    git(path.parent, "init", "-q", "--bare", "-b", "main", str(bare))
    git(path, "remote", "add", "origin", str(bare))
    git(path, "push", "-q", "-u", "origin", "main")
    return path, bare


def cli(
    cwd: Path,
    command: str,
    *args: str,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    proc = run(cwd, str(SCRIPT), command, *args, check=check, env=env)
    stream = proc.stdout if proc.returncode == 0 else proc.stderr
    return proc, json.loads(stream.strip()) if stream.strip() else {}


def start(
    base: Path,
    *,
    run_id: str = "run-1",
    branch: str = "feature/lifecycle",
    key: str = "start-1",
    owned: tuple[str, ...] = ("owned",),
) -> dict:
    head = git(base, "rev-parse", "HEAD").stdout.strip()
    args = [
        "--run-id", run_id,
        "--task", "Implement deterministic lifecycle behavior",
        "--base-branch", "main",
        "--base-sha", head,
        "--intended-branch", branch,
        "--worktree", str(base),
        "--work-unit-id", "unit-1",
        "--work-unit", "Implement first validated change",
        "--idempotency-key", key,
    ]
    for path in owned:
        args.extend(["--owned-path", path])
    return cli(base, "start", *args)[1]


def add_linked(base: Path, path: Path, branch: str = "feature/lifecycle") -> Path:
    git(base, "worktree", "add", "-q", "-b", branch, str(path), "main")
    return path


def ready(
    base: Path,
    *,
    run_id: str = "run-1",
    key: str = "ready-1",
    validations: tuple[str, ...] = ('{"name":"unit tests","passed":true}',),
) -> tuple[subprocess.CompletedProcess[str], dict]:
    args = [
        "--run-id", run_id,
        "--subject", "feat(lifecycle): add validated work unit",
        "--body", "Bind this exact owned diff to passing validation evidence.",
        "--open-tasks", "0",
        "--idempotency-key", key,
    ]
    for value in validations:
        args.extend(["--validation", value])
    return cli(base, "ready", *args, check=False)


def next_unit(
    base: Path,
    *,
    run_id: str = "run-1",
    unit_id: str = "unit-2",
    key: str = "next-1",
) -> tuple[subprocess.CompletedProcess[str], dict]:
    return cli(
        base,
        "next-unit",
        "--run-id", run_id,
        "--work-unit-id", unit_id,
        "--work-unit", f"Implement validated change for {unit_id}",
        "--idempotency-key", key,
        check=False,
    )


def record(
    base: Path,
    linked: Path,
    kind: str,
    status: str,
    key: str,
    *,
    run_id: str = "run-1",
    source: str | None = None,
    authoritative: bool = True,
    sha: str | None = None,
    receipt_sha: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    args = [
        "--run-id", run_id,
        "--kind", kind,
        "--status", status,
        "--source", source or f"{kind}-authority",
        "--sha", sha or git(linked, "rev-parse", "HEAD").stdout.strip(),
        "--idempotency-key", key,
    ]
    if authoritative:
        args.append("--authoritative")
    if receipt_sha is not None:
        args.extend(["--receipt-sha", receipt_sha])
    return cli(base, "record", *args, check=False)


def inspect(base: Path, run_id: str = "run-1") -> dict:
    return cli(base, "inspect", "--run-id", run_id)[1]


def state_paths(base: Path, run_id: str = "run-1") -> tuple[Path, Path, Path]:
    common = Path(
        git(base, "rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()
    )
    root = common / "agent-lifecycle"
    return root / "runs" / f"{run_id}.json", root / "audit.jsonl", root / "repository.lock"


def fingerprint(path: Path) -> tuple[int, int, str]:
    metadata = path.stat()
    return metadata.st_size, metadata.st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest()


def committed_fixture(tmp: Path) -> tuple[Path, Path]:
    base, _ = init_repo(tmp / "repo", origin=True)
    start(base)
    linked = add_linked(base, tmp / "linked")
    (linked / "owned" / "one.txt").write_text("one\n")
    proc, payload = ready(base)
    if proc.returncode:
        raise AssertionError(payload)
    git(linked, "add", "owned/one.txt")
    git(linked, "commit", "-q", "-m", "feat: add first validated unit")
    return base, linked


def pushed_fixture(tmp: Path) -> tuple[Path, Path]:
    base, linked = committed_fixture(tmp)
    git(linked, "push", "-q", "-u", "origin", "feature/lifecycle")
    return base, linked


class WorktreeAndActionMatrixTests(unittest.TestCase):
    def test_true_linked_worktree_and_two_validated_commit_progression(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo", origin=True)
            start(base)
            checkpoints = [("base checkout", inspect(base), "create_stack")]
            linked = add_linked(base, tmp / "linked")
            checkpoints.append(("linked worktree registered", inspect(base), "awaiting_work"))

            (linked / "owned" / "one.txt").write_text("one\n")
            checkpoints.append(("first edit", inspect(base), "editing"))
            self.assertEqual(ready(base)[0].returncode, 0)
            checkpoints.append(("first ready", inspect(base), "commit"))
            git(linked, "add", "owned/one.txt")
            git(linked, "commit", "-q", "-m", "feat: add first validated unit")
            checkpoints.append(("first commit", inspect(base), "push"))

            self.assertEqual(next_unit(base)[0].returncode, 0)
            checkpoints.append(("second unit", inspect(base), "awaiting_work"))
            (linked / "owned" / "two.txt").write_text("two\n")
            checkpoints.append(("second edit", inspect(base), "editing"))
            self.assertEqual(ready(base, key="ready-2")[0].returncode, 0)
            checkpoints.append(("second ready", inspect(base), "commit"))
            git(linked, "add", "owned/two.txt")
            git(linked, "commit", "-q", "-m", "feat: add second validated unit")
            checkpoints.append(("second commit", inspect(base), "push"))

            git(linked, "push", "-q", "-u", "origin", "feature/lifecycle")
            checkpoints.append(("pushed", inspect(base), "open_pr"))
            self.assertEqual(record(base, linked, "pr", "open", "pr-1")[0].returncode, 0)
            checkpoints.append(("PR open", inspect(base), "wait_ci"))
            self.assertEqual(record(base, linked, "ci", "passing", "ci-1")[0].returncode, 0)
            checkpoints.append(("CI green", inspect(base), "merge_eligible"))
            head = git(linked, "rev-parse", "HEAD").stdout.strip()
            self.assertEqual(
                record(base, linked, "merge", "merged", "merge-1", receipt_sha=head)[0].returncode,
                0,
            )
            checkpoints.append(("merged", inspect(base), "sync"))
            self.assertEqual(
                record(base, linked, "sync", "synced", "sync-1", receipt_sha=head)[0].returncode,
                0,
            )
            checkpoints.append(("synced", inspect(base), "cleanup"))

            for label, observed, expected in checkpoints:
                with self.subTest(label=label):
                    self.assertEqual(observed["action"], expected, observed)
            cleanup = checkpoints[-1][1]
            self.assertEqual(
                {item["name"] for item in cleanup["evidence"]["required_before_cleanup"]},
                {"child_stack_safe", "no_active_sessions"},
            )

    def test_base_dirty_paths_are_scoped_to_run_ownership(self):
        with tempfile.TemporaryDirectory() as td:
            base, _ = init_repo(Path(td) / "repo")
            declared_base = git(base, "rev-parse", "HEAD").stdout.strip()
            start(base)
            (base / "unrelated.txt").write_text("unrelated in-progress work\n")
            allowed = inspect(base)
            self.assertEqual(allowed["action"], "create_stack")
            self.assertEqual(allowed["evidence"]["foreign_dirty_paths"], ["unrelated.txt"])
            self.assertEqual(allowed["evidence"]["git"]["head_sha"], declared_base)

            (base / "owned" / "tracked.txt").write_text("work started on trunk\n")
            blocked = inspect(base)
            self.assertEqual(
                (blocked["action"], blocked["reason_code"]),
                ("blocked", "owned_dirty_on_base"),
            )
            self.assertEqual(blocked["evidence"]["owned_dirty_paths"], ["owned/tracked.txt"])
            self.assertEqual(blocked["evidence"]["foreign_dirty_paths"], ["unrelated.txt"])

    def test_blocked_invariant_reason_matrix(self):
        cases = ("merge", "rebase", "cherry-pick", "revert", "bisect")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            start(base)
            linked = add_linked(base, tmp / "linked")
            git_dir = Path(git(linked, "rev-parse", "--absolute-git-dir").stdout.strip())
            markers = {
                "merge": git_dir / "MERGE_HEAD",
                "rebase": git_dir / "rebase-merge",
                "cherry-pick": git_dir / "CHERRY_PICK_HEAD",
                "revert": git_dir / "REVERT_HEAD",
                "bisect": git_dir / "BISECT_LOG",
            }
            for operation in cases:
                marker = markers[operation]
                with self.subTest(reason_class="active_operation", operation=operation):
                    marker.mkdir() if operation == "rebase" else marker.write_text("fixture\n")
                    result = inspect(base)
                    self.assertEqual(result["action"], "blocked")
                    self.assertEqual(result["reason_code"], "active_git_operation")
                    shutil.rmtree(marker) if marker.is_dir() else marker.unlink()
            (linked / "foreign.txt").write_text("foreign\n")
            result = inspect(base)
            self.assertEqual((result["action"], result["reason_code"]), ("blocked", "foreign_dirty_paths"))


    def test_dirty_state_conflict_and_rename_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            start(base)
            linked = add_linked(base, tmp / "linked")
            tracked = linked / "owned" / "tracked.txt"
            tracked.write_text("staged\n")
            git(linked, "add", "owned/tracked.txt")
            tracked.write_text("staged and unstaged\n")
            (linked / "owned" / "untracked.txt").write_text("new\n")
            evidence = inspect(base)["evidence"]["git"]
            self.assertEqual(evidence["staged_paths"], ["owned/tracked.txt"])
            self.assertEqual(evidence["unstaged_paths"], ["owned/tracked.txt"])
            self.assertEqual(evidence["untracked_paths"], ["owned/untracked.txt"])
            self.assertEqual(
                evidence["changed_paths"],
                ["owned/tracked.txt", "owned/untracked.txt"],
            )

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            start(base)
            linked = add_linked(base, tmp / "linked")
            side = tmp / "side"
            git(base, "worktree", "add", "-q", "-b", "side", str(side), "main")
            (side / "owned" / "tracked.txt").write_text("side\n")
            git(side, "commit", "-qam", "fix: change side")
            (linked / "owned" / "tracked.txt").write_text("feature\n")
            git(linked, "commit", "-qam", "fix: change feature")
            self.assertNotEqual(git(linked, "merge", "side", check=False).returncode, 0)
            conflict = inspect(base)
            self.assertEqual(conflict["action"], "blocked")
            self.assertEqual(
                conflict["evidence"]["git"]["conflict_paths"],
                ["owned/tracked.txt"],
            )

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            start(base)
            linked = add_linked(base, tmp / "linked")
            git(linked, "mv", "owned/tracked.txt", "owned/renamed.txt")
            evidence = inspect(base)["evidence"]["git"]
            expected = ["owned/renamed.txt", "owned/tracked.txt"]
            self.assertEqual(evidence["changed_paths"], expected)
            self.assertEqual(evidence["staged_paths"], expected)


class ReadinessAndHistoryTests(unittest.TestCase):
    def test_readiness_fingerprint_changes_and_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            start(base)
            linked = add_linked(base, tmp / "linked")
            target = linked / "owned" / "tracked.txt"
            target.write_text("ready one\n")
            self.assertEqual(ready(base)[0].returncode, 0)
            target.write_text("changed after ready\n")
            changed = inspect(base)
            self.assertEqual((changed["action"], changed["reason_code"]), ("blocked", "ready_diff_changed"))
            self.assertEqual(ready(base, key="ready-refresh")[0].returncode, 0)
            self.assertEqual(inspect(base)["action"], "commit")
            git(linked, "add", "owned/tracked.txt")
            git(linked, "commit", "-q", "-m", "feat: commit refreshed ready diff")
            (linked / "owned" / "later.txt").write_text("later\n")
            reused = inspect(base)
            self.assertEqual(
                (reused["action"], reused["reason_code"]),
                ("blocked", "readiness_consumed_dirty"),
            )

    def test_history_union_blocks_modify_then_revert_foreign_path(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, linked = committed_fixture(tmp)
            (linked / "README.md").write_text("foreign modification\n")
            git(linked, "add", "README.md")
            git(linked, "commit", "-q", "-m", "docs: modify foreign path")
            (linked / "README.md").write_text("fixture\n")
            git(linked, "add", "README.md")
            git(linked, "commit", "-q", "-m", "docs: restore foreign path")
            result = inspect(base)
            self.assertEqual(
                (result["action"], result["reason_code"]),
                ("blocked", "foreign_committed_paths"),
            )
            self.assertIn("README.md", result["reason"])
            self.assertIn("README.md", result["evidence"]["current_unit_history"]["paths"])

    def test_next_unit_requires_consumed_exact_regular_commit(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            start(base)
            linked = add_linked(base, tmp / "linked")
            (linked / "owned" / "one.txt").write_text("one\n")
            self.assertEqual(ready(base)[0].returncode, 0)
            proc, payload = next_unit(base)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(payload["error_code"], "unit_not_committed")
            git(linked, "add", "owned/one.txt")
            git(linked, "commit", "-q", "-m", "feat: consume first unit")
            self.assertEqual(next_unit(base)[0].returncode, 0)


class ValidationAndReceiptTests(unittest.TestCase):
    def test_validation_evidence_strict_rejection_matrix(self):
        invalid = [
            ("free text", ("tests failed",)),
            ("unknown token", ("tests",)),
            ("empty name", ("=pass",)),
            ("padded name", (" tests=pass",)),
            ("failed JSON", ('{"name":"tests","passed":false}',)),
            ("empty JSON name", ('{"name":"","passed":true}',)),
            ("duplicate", ("tests=pass", '{"name":"Tests","passed":true}')),
        ]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            start(base)
            linked = add_linked(base, tmp / "linked")
            (linked / "owned" / "one.txt").write_text("one\n")
            for index, (label, values) in enumerate(invalid):
                with self.subTest(label=label):
                    proc, payload = ready(base, key=f"bad-{index}", validations=values)
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertEqual(payload["error_code"], "invalid_validation")
            self.assertEqual(ready(base, key="strict-pass", validations=("tests=pass",))[0].returncode, 0)

    def test_successful_merge_and_sync_require_explicit_exact_receipts(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, linked = pushed_fixture(tmp)
            record(base, linked, "pr", "open", "pr-1")
            record(base, linked, "ci", "passing", "ci-1")
            for kind, status in (("merge", "merged"), ("sync", "synced")):
                with self.subTest(kind=kind, receipt="missing"):
                    proc, payload = record(base, linked, kind, status, f"{kind}-missing")
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertEqual(payload["error_code"], "missing_receipt")
                with self.subTest(kind=kind, receipt="abbreviated"):
                    proc, payload = record(
                        base, linked, kind, status, f"{kind}-short", receipt_sha="abc1234"
                    )
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertEqual(payload["error_code"], "invalid_sha")
            head = git(linked, "rev-parse", "HEAD").stdout.strip()
            self.assertEqual(
                record(base, linked, "merge", "merged", "merge-exact", receipt_sha=head)[0].returncode,
                0,
            )
            self.assertEqual(
                record(base, linked, "sync", "synced", "sync-exact", receipt_sha=head)[0].returncode,
                0,
            )
            self.assertEqual(inspect(base)["action"], "cleanup")

    def test_stale_nonauthoritative_and_contradictory_facts_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, linked = pushed_fixture(tmp)
            head = git(linked, "rev-parse", "HEAD").stdout.strip()
            record(base, linked, "pr", "open", "pr-github", source="github")
            record(
                base, linked, "ci", "passing", "ci-advisory",
                source="advisory", authoritative=False,
            )
            self.assertEqual(inspect(base)["action"], "wait_ci")
            record(base, linked, "pr", "closed", "pr-mirror", source="mirror")
            contradiction = inspect(base)
            self.assertEqual(contradiction["reason_code"], "contradictory_remote_facts")
            proc, payload = record(
                base, linked, "ci", "passing", "ci-short", sha=head[:8]
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(payload["error_code"], "invalid_sha")


    def test_path_and_branch_validation_rejection_matrix(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            outside = tmp / "outside"
            outside.mkdir()
            (base / "escape").symlink_to(outside, target_is_directory=True)
            head = git(base, "rev-parse", "HEAD").stdout.strip()
            cases = [
                ("absolute", ["/absolute"]),
                ("parent", ["../outside"]),
                ("git metadata", [".git/config"]),
                ("normalized duplicate", ["owned/item", "owned/./item"]),
                ("symlink escape", ["escape/item"]),
            ]
            for index, (label, paths) in enumerate(cases):
                args = [
                    "--run-id", f"bad-{index}", "--task", "Reject unsafe input",
                    "--base-branch", "main", "--base-sha", head,
                    "--intended-branch", "feature/safe", "--idempotency-key", f"key-{index}",
                ]
                for path in paths:
                    args.extend(["--owned-path", path])
                with self.subTest(label=label):
                    proc, payload = cli(base, "start", *args, check=False)
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertEqual(payload["error_code"], "invalid_owned_path")
            proc, payload = cli(
                base, "start", "--run-id", "bad-branch", "--task", "Reject branch",
                "--base-branch", "main", "--base-sha", head,
                "--intended-branch", "topic/unsupported", "--owned-path", "owned",
                "--idempotency-key", "bad-branch-key", check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(payload["error_code"], "invalid_branch")


    def test_exact_stale_fact_and_prior_head_facts_never_enable_merge(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, linked = pushed_fixture(tmp)
            old_head = git(linked, "rev-parse", "HEAD").stdout.strip()
            record(base, linked, "pr", "open", "pr-old")
            record(base, linked, "ci", "passing", "ci-old")
            self.assertEqual(inspect(base)["action"], "merge_eligible")
            self.assertEqual(next_unit(base)[0].returncode, 0)
            (linked / "owned" / "two.txt").write_text("two\n")
            self.assertEqual(ready(base, key="ready-two")[0].returncode, 0)
            git(linked, "add", "owned/two.txt")
            git(linked, "commit", "-q", "-m", "feat: add newer exact head")
            git(linked, "push", "-q", "origin", "feature/lifecycle")
            result = inspect(base)
            self.assertEqual(result["action"], "open_pr")
            self.assertTrue(any(old_head in item for item in result["evidence"]["stale_facts"]))
            proc, payload = record(
                base, linked, "ci", "passing", "ci-stale-full", sha=old_head
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(payload["error_code"], "stale_fact")


class AuditDurabilityTests(unittest.TestCase):
    def module_start(self, base: Path, key: str = "start-1") -> dict:
        head = git(base, "rev-parse", "HEAD").stdout.strip()
        return LIFECYCLE.start_run(
            base,
            run_id="run-1",
            task="Exercise audit durability",
            base_branch="main",
            base_sha=head,
            intended_branch="feature/lifecycle",
            owned_paths=["owned"],
            worktree=base,
            unit_id="unit-1",
            unit_description="Implement audited unit",
            key=key,
            timeout=1,
        )

    def test_state_before_audit_failure_repairs_before_idempotent_return(self):
        with tempfile.TemporaryDirectory() as td:
            base, _ = init_repo(Path(td) / "repo")
            with mock.patch.object(LIFECYCLE, "append_audit", side_effect=OSError("injected audit failure")):
                with self.assertRaises(OSError):
                    self.module_start(base)
            state, audit, _ = state_paths(base)
            self.assertTrue(state.exists())
            self.assertFalse(audit.exists())
            retry = self.module_start(base)
            self.assertTrue(retry["idempotent"])
            lines = audit.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["operation"], "start")

    def test_mutation_repairs_only_incomplete_final_line(self):
        with tempfile.TemporaryDirectory() as td:
            base, _ = init_repo(Path(td) / "repo")
            start(base)
            _, audit, _ = state_paths(base)
            with audit.open("ab") as handle:
                handle.write(b'{"partial"')
            proc, payload = cli(
                base,
                "halt",
                "--run-id", "run-1",
                "--status", "blocked",
                "--reason", "Injected audit recovery test",
                "--idempotency-key", "halt-1",
                check=False,
            )
            self.assertEqual(proc.returncode, 0, payload)
            events = [json.loads(line) for line in audit.read_text().splitlines()]
            self.assertEqual([event["operation"] for event in events], ["start", "halt"])

    def test_invalid_complete_audit_blocks_without_repair(self):
        with tempfile.TemporaryDirectory() as td:
            base, _ = init_repo(Path(td) / "repo")
            start(base)
            state, audit, _ = state_paths(base)
            with audit.open("ab") as handle:
                handle.write(b"not-json\n")
            before = (fingerprint(state), fingerprint(audit))
            result = inspect(base)
            self.assertEqual((result["action"], result["reason_code"]), ("blocked", "audit_invalid"))
            self.assertEqual((fingerprint(state), fingerprint(audit)), before)
            proc, payload = cli(
                base,
                "halt",
                "--run-id", "run-1",
                "--status", "blocked",
                "--reason", "Must not hide invalid history",
                "--idempotency-key", "halt-invalid",
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(payload["error_code"], "audit_invalid")

    def test_missing_audit_is_read_only_block_until_mutation_reconciles(self):
        with tempfile.TemporaryDirectory() as td:
            base, _ = init_repo(Path(td) / "repo")
            start(base)
            state, audit, _ = state_paths(base)
            audit.write_bytes(b"")
            before = (fingerprint(state), fingerprint(audit))
            result = inspect(base)
            self.assertEqual(result["reason_code"], "audit_inconsistent")
            self.assertEqual((fingerprint(state), fingerprint(audit)), before)
            proc, _ = cli(
                base,
                "halt",
                "--run-id", "run-1",
                "--status", "blocked",
                "--reason", "Reconcile missing audit event",
                "--idempotency-key", "halt-reconcile",
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(len(audit.read_text().splitlines()), 2)


class StateConcurrencyAndErrorTests(unittest.TestCase):
    def test_duplicate_nonterminal_run_refused_terminal_run_permits_new(self):
        with tempfile.TemporaryDirectory() as td:
            base, _ = init_repo(Path(td) / "repo")
            start(base)
            linked = add_linked(base, Path(td) / "linked")
            (linked / "owned" / "prior.txt").write_text("prior run\n")
            git(linked, "add", "owned/prior.txt")
            git(linked, "commit", "-q", "-m", "feat: leave prior terminal branch head")
            proc, payload = cli(
                base,
                "start",
                "--run-id", "run-2",
                "--task", "Duplicate target",
                "--base-branch", "main",
                "--base-sha", git(base, "rev-parse", "HEAD").stdout.strip(),
                "--intended-branch", "feature/lifecycle",
                "--owned-path", "owned",
                "--idempotency-key", "start-2",
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(payload["error_code"], "duplicate_run")
            self.assertEqual(
                cli(
                    base, "halt",
                    "--run-id", "run-1",
                    "--status", "done",
                    "--reason", "First run completed",
                    "--idempotency-key", "halt-1",
                )[0].returncode,
                0,
            )
            self.assertTrue(start(base, run_id="run-2", key="start-2")["ok"])
            self.assertEqual(inspect(base, "run-2")["action"], "awaiting_work")

    def test_lock_contention_preserves_state_and_audit(self):
        with tempfile.TemporaryDirectory() as td:
            base, _ = init_repo(Path(td) / "repo")
            start(base)
            state, audit, lock = state_paths(base)
            before = fingerprint(state), fingerprint(audit)
            with lock.open("r+") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                proc, payload = cli(
                    base,
                    "halt",
                    "--run-id", "run-1",
                    "--status", "blocked",
                    "--reason", "Lock contention test",
                    "--idempotency-key", "halt-locked",
                    "--lock-timeout", "0.05",
                    check=False,
                )
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(payload["error_code"], "lock_timeout")
            self.assertEqual((fingerprint(state), fingerprint(audit)), before)

    def test_shared_state_and_missing_worktree_error_are_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            start(base)
            linked = add_linked(base, tmp / "linked")
            self.assertEqual(inspect(linked)["action"], "awaiting_work")
            shutil.rmtree(linked)
            missing = inspect(base)
            self.assertEqual((missing["action"], missing["reason_code"]), ("blocked", "missing_worktree"))

    def test_nested_malformed_state_and_git_failure_never_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            start(base)
            state, _, _ = state_paths(base)
            payload = json.loads(state.read_text())
            payload["repository"] = None
            state.write_text(json.dumps(payload))
            proc, result = cli(base, "inspect", "--run-id", "run-1", check=False)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual((result["action"], result["reason_code"]), ("blocked", "invalid_state"))
            self.assertNotIn("Traceback", proc.stderr)
            with mock.patch.object(LIFECYCLE, "discover_repo", side_effect=OSError(5, "injected")):
                normalized = LIFECYCLE.inspect_run(base, "run-1")
            self.assertEqual(normalized["reason_code"], "inspection_error")

    def test_terminal_status_survives_linked_worktree_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            start(base)
            linked = add_linked(base, tmp / "linked")
            cli(
                base, "halt",
                "--run-id", "run-1",
                "--status", "done",
                "--reason", "Cleanup may remove intended worktree",
                "--idempotency-key", "halt-1",
            )
            git(base, "worktree", "remove", "--force", str(linked))
            result = inspect(base)
            self.assertEqual((result["action"], result["reason_code"]), ("done", "terminal_done"))


    def test_all_mutations_are_idempotent_without_duplicate_audit_events(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            first = start(base)
            state, audit, _ = state_paths(base)
            before = fingerprint(state), fingerprint(audit)
            second = start(base)
            self.assertFalse(first["idempotent"])
            self.assertTrue(second["idempotent"])
            self.assertEqual((fingerprint(state), fingerprint(audit)), before)

            linked = add_linked(base, tmp / "linked")
            (linked / "owned" / "one.txt").write_text("one\n")
            self.assertEqual(ready(base)[0].returncode, 0)
            before = fingerprint(state), fingerprint(audit)
            self.assertTrue(ready(base)[1]["idempotent"])
            self.assertEqual((fingerprint(state), fingerprint(audit)), before)
            git(linked, "add", "owned/one.txt")
            git(linked, "commit", "-q", "-m", "feat: idempotent unit")
            head = git(linked, "rev-parse", "HEAD").stdout.strip()
            self.assertEqual(record(base, linked, "pr", "open", "pr-1")[0].returncode, 0)
            before = fingerprint(state), fingerprint(audit)
            self.assertTrue(record(base, linked, "pr", "open", "pr-1")[1]["idempotent"])
            self.assertEqual((fingerprint(state), fingerprint(audit)), before)
            args = [
                "--run-id", "run-1", "--status", "done", "--reason", "Idempotent halt",
                "--idempotency-key", "halt-1",
            ]
            self.assertEqual(cli(base, "halt", *args)[0].returncode, 0)
            before = fingerprint(state), fingerprint(audit)
            self.assertTrue(cli(base, "halt", *args)[1]["idempotent"])
            self.assertEqual((fingerprint(state), fingerprint(audit)), before)
            self.assertEqual(len(audit.read_text().splitlines()), 4)
            self.assertEqual(len(head), 40)


class PurityAndStructureTests(unittest.TestCase):
    def test_inspect_is_read_only_and_never_invokes_network_git(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            base, _ = init_repo(tmp / "repo")
            start(base)
            linked = add_linked(base, tmp / "linked")
            state, audit, lock = state_paths(base)
            base_index = Path(git(base, "rev-parse", "--git-path", "index").stdout.strip())
            linked_index = Path(git(linked, "rev-parse", "--git-path", "index").stdout.strip())
            if not base_index.is_absolute():
                base_index = (base / base_index).resolve()
            if not linked_index.is_absolute():
                linked_index = (linked / linked_index).resolve()
            watched = [state, audit, lock, base_index, linked_index]
            before = {path: fingerprint(path) for path in watched}
            real_git = shutil.which("git")
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
            proc, result = cli(base, "inspect", "--run-id", "run-1", check=False, env=env)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(result["action"], "awaiting_work")
            self.assertEqual({path: fingerprint(path) for path in watched}, before)

    def test_controller_is_smaller_and_decision_is_phased(self):
        source = SCRIPT.read_text()
        tree = ast.parse(source)
        functions = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        decide = functions["decide"]
        phases = {"phase_invariants", "phase_stack", "phase_local", "phase_remote", "phase_post_merge"}
        self.assertLess(len(source.splitlines()), 1600)
        self.assertLess(decide.end_lineno - decide.lineno + 1, 30)
        self.assertTrue(phases.issubset(functions))


if __name__ == "__main__":
    unittest.main()
