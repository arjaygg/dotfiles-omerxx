"""Hermetic behavioral tests for the Claude lifecycle adapter."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "ai"))

import git_lifecycle as controller  # noqa: E402
import lifecycle_adapter as adapter  # noqa: E402


def run(cwd: Path, *args: str, check: bool = True, env: dict[str, str] | None = None):
    proc = subprocess.run(
        list(args),
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if check and proc.returncode:
        raise AssertionError(f"{args} failed ({proc.returncode}): {proc.stderr}")
    return proc


def git(cwd: Path, *args: str, check: bool = True):
    return run(cwd, "git", *args, check=check)


def lifecycle_config(enabled: bool = True, stages: str = "auto_stack auto_commit auto_push auto_pr") -> str:
    lines = [
        "lifecycle:",
        f"  enabled: {'true' if enabled else 'false'}",
        "pipeline:",
        "  auto_stack: A2",
        "  auto_commit: A2",
        "  auto_push: A2",
        "  auto_pr: A2",
        "  auto_ship: A2",
        "  auto_clean: A2",
        "autonomy_override:",
        "  tier: A2",
        "  basis: risk-accepted",
        f"  stages: {stages}",
        "  expires: 2099-01-01",
        "  signed_off_by: lifecycle-test",
    ]
    return "\n".join(lines) + "\n"


def init_repo(path: Path, *, opted_in: bool = True) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "adapter-test@example.com")
    git(path, "config", "user.name", "Adapter Test")
    (path / "README.md").write_text("initial\n")
    (path / ".gitignore").write_text(".trees/\n")
    if opted_in:
        (path / ".claude-atomic.yaml").write_text(lifecycle_config())
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "chore: initialize fixture")
    return path


def namespace(**values):
    defaults = {
        "session_id": "session-1",
        "run_id": None,
        "idempotency_key": None,
        "lock_timeout": 10,
    }
    defaults.update(values)
    return argparse.Namespace(**defaults)


def start_run(repo: Path, *, session_id: str = "session-1", run_id: str = "run-1") -> dict:
    return adapter.start(
        namespace(
            session_id=session_id,
            run_id=run_id,
            task="implement lifecycle adapter",
            base_branch="main",
            base_sha=git(repo, "rev-parse", "HEAD").stdout.strip(),
            intended_branch="feature/lifecycle",
            owned_paths=["owned"],
            worktree=None,
            work_unit_id="unit-1",
            work_unit="implement owned lifecycle work",
        ),
        repo,
    )


def add_linked(repo: Path) -> Path:
    linked = repo.parent / "linked"
    git(repo, "worktree", "add", "-q", "-b", "feature/lifecycle", str(linked))
    return linked


def ready_run(repo: Path, linked: Path, *, session_id: str = "session-1") -> dict:
    (linked / "owned").mkdir(exist_ok=True)
    (linked / "owned" / "change.txt").write_text("ready\n")
    return adapter.ready(
        namespace(
            session_id=session_id,
            subject="feat(lifecycle): add adapter behavior",
            body="Lifecycle ownership requires an exact canonical commit.",
            open_tasks=0,
            validations=["unit-tests=pass"],
        ),
        repo,
    )


def completed_process(args=(), returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


class OptInAndBindingTests(unittest.TestCase):
    def test_hooks_are_silent_and_commands_refuse_without_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo", opted_in=False)
            payload = json.dumps(
                {
                    "cwd": str(repo),
                    "session_id": "s",
                    "tool_name": "Write",
                    "tool_input": {"file_path": str(repo / "README.md")},
                }
            )
            hook_args = namespace(event="PreToolUse")
            self.assertIsNone(adapter.hook(hook_args, repo, payload))
            self.assertEqual(
                adapter.status(namespace(session_id="s"), repo),
                {"ok": True, "enabled": False, "bound": False},
            )
            with self.assertRaisesRegex(adapter.AdapterError, "not opted"):
                start_run(repo, session_id="s")

    def test_start_binds_shared_session_and_is_controller_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            first = start_run(repo)
            second = start_run(repo)
            self.assertEqual(first["run_id"], "run-1")
            self.assertTrue(second["controller"]["idempotent"])
            binding = adapter.load_binding(controller.discover_repo(repo), "session-1")
            self.assertEqual(binding["run_id"], "run-1")

            linked = add_linked(repo)
            value = adapter.status(namespace(), linked)
            self.assertTrue(value["bound"])
            self.assertEqual(value["run_id"], "run-1")
            self.assertEqual(value["action"], "awaiting_work")

    def test_new_run_is_halted_when_binding_persistence_fails(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            with mock.patch.object(
                    adapter, "_write_binding_locked",
                    side_effect=adapter.AdapterError("simulated", "binding_write_failed")):
                with self.assertRaises(adapter.AdapterError) as raised:
                    start_run(repo)
            self.assertEqual(raised.exception.code, "binding_persist_failed")
            view = controller.discover_repo(repo)
            state = adapter.load_run_state(view, "run-1")
            self.assertEqual(state["terminal"]["status"], "blocked")
            self.assertEqual(adapter.inspect_bound(view, "run-1")["action"], "blocked")

    def test_ready_and_next_unit_are_bound_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            start_run(repo)
            linked = add_linked(repo)
            first = ready_run(repo, linked)
            second = ready_run(repo, linked)
            self.assertEqual(first["status"]["action"], "commit")
            self.assertTrue(second["idempotent"])

            git(linked, "add", "owned/change.txt")
            git(linked, "commit", "-q", "-m", "feat(lifecycle): add adapter behavior",
                "-m", "Lifecycle ownership requires an exact canonical commit.")
            advanced = adapter.next_unit(
                namespace(
                    work_unit_id="unit-2",
                    description="continue lifecycle coverage",
                ),
                repo,
            )
            self.assertEqual(advanced["status"]["action"], "awaiting_work")
            repeated = adapter.next_unit(
                namespace(
                    work_unit_id="unit-2",
                    description="continue lifecycle coverage",
                ),
                repo,
            )
            self.assertTrue(repeated["idempotent"])


class PreWriteAndContextHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = init_repo(Path(self.temp.name) / "repo")
        start_run(self.repo)
        self.linked = add_linked(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, session: str, tool: str, tool_input: dict) -> dict:
        return {
            "cwd": str(self.linked),
            "session_id": session,
            "tool_name": tool,
            "tool_input": tool_input,
        }

    def test_unbound_owned_and_state_gates_use_exact_deny_schema(self):
        unbound = adapter.hook_pre_write(
            self.payload("other", "Write", {"file_path": str(self.linked / "owned" / "new.txt")}),
            controller.discover_repo(self.linked),
            "other",
        )
        self.assertEqual(
            set(unbound),
            {"hookSpecificOutput"},
        )
        specific = unbound["hookSpecificOutput"]
        self.assertEqual(
            specific,
            {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": specific["permissionDecisionReason"],
            },
        )
        self.assertTrue(specific["permissionDecisionReason"].startswith(adapter.HARD_BLOCK))

        outside = adapter.hook_pre_write(
            self.payload("session-1", "Edit", {"file_path": str(self.linked / "README.md")}),
            controller.discover_repo(self.linked),
            "session-1",
        )
        self.assertEqual(outside["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("owned boundary", outside["hookSpecificOutput"]["permissionDecisionReason"])

        allowed = adapter.hook_pre_write(
            self.payload(
                "session-1",
                "MultiEdit",
                {
                    "edits": [
                        {"file_path": str(self.linked / "owned" / "one.txt")},
                        {"path": str(self.linked / "owned" / "two.txt")},
                    ]
                },
            ),
            controller.discover_repo(self.linked),
            "session-1",
        )
        self.assertIsNone(allowed)

        ready_run(self.repo, self.linked)
        after_ready = adapter.hook_pre_write(
            self.payload("session-1", "Write", {"file_path": str(self.linked / "owned" / "later.txt")}),
            controller.discover_repo(self.linked),
            "session-1",
        )
        self.assertIn("state is commit", after_ready["hookSpecificOutput"]["permissionDecisionReason"])

    def test_corrupt_binding_fails_closed_for_write_and_stop(self):
        repo = controller.discover_repo(self.linked)
        adapter.binding_path(repo.common_dir, "session-1").write_text("{bad")
        payload = self.payload(
            "session-1", "Write", {"file_path": str(self.linked / "owned" / "new.txt")})
        write_result = adapter.hook(namespace(event="PreToolUse"), self.linked, json.dumps(payload))
        self.assertEqual(write_result["hookSpecificOutput"]["permissionDecision"], "deny")
        stop_result = adapter.hook(namespace(event="Stop"), self.linked, json.dumps(payload))
        self.assertEqual(stop_result["decision"], "block")
        self.assertTrue(stop_result["lifecycle_bound"])

    def test_notebook_edit_and_direct_bash_mutations_are_gated(self):
        repo = controller.discover_repo(self.linked)
        allowed = adapter.hook_pre_write(
            self.payload("session-1", "NotebookEdit",
                         {"notebook_path": str(self.linked / "owned" / "notes.ipynb")}),
            repo, "session-1")
        self.assertIsNone(allowed)
        outside = adapter.hook_pre_write(
            self.payload("session-1", "NotebookEdit",
                         {"notebook_path": str(self.linked / "notes.ipynb")}),
            repo, "session-1")
        self.assertEqual(outside["hookSpecificOutput"]["permissionDecision"], "deny")
        blocked = (
            "git add owned/x", "git -C . commit -m x", "git push origin main",
            "gh pr create --fill", "gh pr edit 1 --title x", "gh pr merge 1",
            "gh -R owner/repo pr create --fill", "env -u GH_TOKEN git push origin main",
            "$HOME/.dotfiles/.claude/scripts/stack create feature/x main",
            "stack pr feature/x", "stack merge 1", "stack clean feature/x", "stack update",
            "bash -c 'git push origin main'",
        )
        for command in blocked:
            with self.subTest(command=command):
                value = adapter.hook_pre_write(
                    self.payload("session-1", "Bash", {"command": command}), repo, "session-1")
                self.assertEqual(value["hookSpecificOutput"]["permissionDecision"], "deny")
        for command in ("git status", "git diff", "gh pr view 1", "stack status",
                        "python3 scripts/ai/lifecycle_adapter.py tick", "python3 -m unittest tests"):
            with self.subTest(allowed=command):
                self.assertIsNone(adapter.hook_pre_write(
                    self.payload("session-1", "Bash", {"command": command}), repo, "session-1"))

    def test_prompt_and_session_context_are_concise_and_malformed_input_is_silent(self):
        repo = controller.discover_repo(self.linked)
        for event in ("SessionStart", "UserPromptSubmit"):
            value = adapter.hook_context(event, repo, "session-1")
            specific = value["hookSpecificOutput"]
            self.assertEqual(specific["hookEventName"], event)
            self.assertIn("Lifecycle awaiting_work", specific["additionalContext"])
        malformed = adapter.hook(namespace(event="PreToolUse"), self.repo, "{not-json")
        self.assertEqual(malformed["hookSpecificOutput"]["permissionDecision"], "deny")
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(adapter.hook(namespace(event="PreToolUse"), Path(td), "{not-json"))


class ReversibleActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = init_repo(Path(self.temp.name) / "repo")
        start_run(self.repo)
        self.repo_view = controller.discover_repo(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def test_create_stack_uses_canonical_exact_base_and_a2_gate(self):
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        calls = []

        def record(args, cwd, check=True):
            calls.append(([str(item) for item in args], cwd, check))
            return completed_process(args)

        with mock.patch.object(adapter, "run_command", side_effect=record):
            adapter.action_create_stack(self.repo_view, state, decision)
        self.assertEqual(
            calls[0][0],
            [
                str(adapter.STACK),
                "create",
                "feature/lifecycle",
                "main",
                "--base-sha",
                state["base"]["sha"],
                "--strict",
            ],
        )

        action = mock.Mock()
        with mock.patch.object(adapter, "resolve_autonomy", return_value=(False, "autonomy_below_a2")):
            value = adapter.execute_action(
                self.repo_view,
                "run-1",
                decision,
                state,
                action,
            )
        self.assertEqual(value["outcome"], "approval_required")
        action.assert_not_called()
        self.assertFalse((self.repo_view.common_dir / "autonomy-demoted-auto_stack").exists())

    def test_action_reinspects_and_refuses_stale_evidence_without_demotion(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        (linked / "owned" / "change.txt").write_text("changed after inspection\n")
        action = mock.Mock()
        with mock.patch.object(adapter, "resolve_autonomy", return_value=(True, "authorized")):
            value = adapter.execute_action(self.repo_view, "run-1", decision, state, action)
        self.assertEqual(value["outcome"], "blocked")
        self.assertEqual(value["reason_code"], "stale_inspection")
        action.assert_not_called()
        self.assertFalse((self.repo_view.common_dir / "autonomy-demoted-auto_commit").exists())

    def test_concurrent_ticks_serialize_without_duplicate_action_or_demotion(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        barrier = threading.Barrier(3)
        counts = {"commit": 0, "push": 0}
        count_lock = threading.Lock()
        results: list[dict] = []
        errors: list[BaseException] = []

        def commit_once(_repo, state, _decision):
            with count_lock:
                counts["commit"] += 1
            time.sleep(0.1)
            ready = controller.current_unit(state)["ready"]
            git(linked, "add", "owned/change.txt")
            git(linked, "commit", "-q", "-m", ready["subject"], "-m", ready["body"])

        def push_once(_repo, _state, _decision):
            with count_lock:
                counts["push"] += 1

        def worker():
            try:
                barrier.wait()
                results.append(adapter.tick(namespace(run_id="run-1"), self.repo))
            except BaseException as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        with (
            mock.patch.object(adapter, "resolve_autonomy", return_value=(True, "authorized")),
            mock.patch.object(adapter, "action_commit", side_effect=commit_once),
            mock.patch.object(adapter, "action_push", side_effect=push_once),
        ):
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join(5)
        self.assertFalse(errors)
        self.assertEqual(len(results), 2)
        self.assertEqual(counts["commit"], 1)
        self.assertLessEqual(counts["push"], 1)
        for stage in adapter.ACTION_STAGES.values():
            self.assertFalse((self.repo_view.common_dir / f"autonomy-demoted-{stage}").exists())

    def test_commit_stages_only_ready_paths_validates_and_uses_wrapper(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        calls: list[str] = []

        def canonical(args, cwd, check=True):
            executable = str(args[0])
            calls.append(executable)
            if Path(executable) == adapter.COMMIT:
                git(
                    cwd,
                    "commit",
                    "-q",
                    "-m",
                    str(args[2]),
                    "-m",
                    str(args[4]),
                )
            return completed_process(args, stdout='{"passed":true}\n')

        with mock.patch.object(adapter, "run_command", side_effect=canonical):
            adapter.action_commit(self.repo_view, state, decision)
        self.assertEqual(calls, [str(adapter.VALIDATE), str(adapter.COMMIT)])
        self.assertEqual(
            git(linked, "show", "--pretty=", "--name-only", "HEAD").stdout.split(),
            ["owned/change.txt"],
        )
        self.assertEqual(adapter.inspect_bound(self.repo_view, "run-1")["action"], "push")

    def test_commit_cas_rejects_post_stage_content_mutation(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        commit_called = False

        def mutate_after_stage(args, cwd, check=True):
            nonlocal commit_called
            if Path(str(args[0])) == adapter.VALIDATE:
                (linked / "owned" / "change.txt").write_text("mutated after staging\n")
            if Path(str(args[0])) == adapter.COMMIT:
                commit_called = True
            return completed_process(args, stdout='{"passed":true}\n')

        with mock.patch.object(adapter, "run_command", side_effect=mutate_after_stage):
            with self.assertRaises(adapter.AdapterError) as raised:
                adapter.action_commit(self.repo_view, state, decision)
        self.assertEqual(raised.exception.code, "commit_cas_failed")
        self.assertFalse(commit_called)
        self.assertEqual(git(linked, "rev-parse", "HEAD").stdout.strip(), state["base"]["sha"])

    def test_push_is_ordinary_and_open_pr_reuses_or_calls_canonical_stack(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        git(linked, "add", "owned/change.txt")
        git(linked, "commit", "-q", "-m", "feat(lifecycle): add adapter behavior",
            "-m", "Lifecycle ownership requires an exact canonical commit.")
        bare = Path(self.temp.name) / "origin.git"
        git(Path(self.temp.name), "init", "-q", "--bare", str(bare))
        git(linked, "remote", "add", "origin", str(bare))
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        original_git = controller.git
        with mock.patch.object(controller, "git", wraps=original_git) as git_call:
            adapter.action_push(self.repo_view, state, decision)
        pushes = [call.args[1:] for call in git_call.call_args_list
                  if len(call.args) > 1 and call.args[1] == "push"]
        self.assertEqual(pushes, [("push", "--set-upstream", "origin",
                                  "HEAD:refs/heads/feature/lifecycle")])
        self.assertEqual(
            git(bare, "rev-parse", "refs/heads/feature/lifecycle").stdout.strip(),
            git(linked, "rev-parse", "HEAD").stdout.strip(),
        )

        decision = adapter.inspect_bound(self.repo_view, "run-1")
        head = adapter.decision_head(decision)
        pull_request = {
            "number": 17,
            "state": "OPEN",
            "isDraft": False,
            "headRefOid": head,
            "headRefName": "feature/lifecycle",
            "baseRefName": "main",
            "headRepositoryOwner": {"login": "owner"},
            "repository": "owner/repo",
            "url": "https://example.invalid/pr/17",
        }
        with (
            mock.patch.object(adapter, "query_exact_pr", side_effect=[None, pull_request]),
            mock.patch.object(adapter, "run_command", return_value=completed_process()) as command,
        ):
            adapter.action_open_pr(self.repo_view, state, decision)
        command.assert_called_once_with(
            [adapter.STACK, "pr", "feature/lifecycle", "main",
             "feat(lifecycle): add adapter behavior"],
            linked.resolve(),
        )
        self.assertEqual(adapter.inspect_bound(self.repo_view, "run-1")["action"], "wait_ci")

        with (
            mock.patch.object(adapter, "query_exact_pr", return_value=pull_request),
            mock.patch.object(adapter, "run_command") as command,
        ):
            adapter.action_open_pr(self.repo_view, state, decision)
        command.assert_not_called()

    def test_action_crash_recovers_by_fresh_inspection_and_demotes_only_its_stage(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")

        def committed_then_crashed(_repo, current_state, _decision):
            unit = controller.current_unit(current_state)["ready"]
            git(linked, "add", "owned/change.txt")
            git(linked, "commit", "-q", "-m", unit["subject"], "-m", unit["body"])
            raise adapter.AdapterError("simulated post-commit crash", "post_action_crash")

        with mock.patch.object(adapter, "resolve_autonomy", return_value=(True, "authorized")):
            result = adapter.execute_action(
                self.repo_view,
                "run-1",
                decision,
                state,
                committed_then_crashed,
            )
        self.assertEqual(result["outcome"], "action_failed")
        self.assertEqual(result["after"]["action"], "push")
        self.assertTrue((self.repo_view.common_dir / "autonomy-demoted-auto_commit").exists())
        for other in ("auto_stack", "auto_push", "auto_pr"):
            self.assertFalse((self.repo_view.common_dir / f"autonomy-demoted-{other}").exists())
        audit = (adapter.adapter_root(self.repo_view.common_dir) / "adapter-audit.jsonl").read_text()
        self.assertNotIn("simulated post-commit crash", audit)
        self.assertNotIn("command", audit)

    def test_merge_sync_cleanup_and_remote_settings_are_never_executed(self):
        source = Path(adapter.__file__).read_text()
        for forbidden in (
            "stack-ship",
            "gh pr merge",
            "stack clean",
            "stack-clean",
            "git pull",
            "git rebase",
            "delete-branch",
            "gh api --method",
        ):
            self.assertNotIn(forbidden, source)

        state = adapter.load_run_state(self.repo_view, "run-1")
        for action in ("merge_eligible", "sync", "cleanup"):
            decision = {
                "action": action,
                "reason": "deferred",
                "reason_code": "deferred",
                "evidence": {"git": {"head_sha": state["base"]["sha"]}},
            }
            with (
                mock.patch.object(adapter, "bound_state", return_value=(
                    self.repo_view,
                    {"run_id": "run-1"},
                    state,
                )),
                mock.patch.object(adapter, "inspect_bound", return_value=decision),
                mock.patch.object(adapter, "run_command") as command,
            ):
                value = adapter.tick(namespace(run_id="run-1"), self.repo)
            self.assertEqual(value["outcome"], "approval_required")
            command.assert_not_called()


class AdapterAuditTests(unittest.TestCase):
    def test_audit_is_locked_partial_write_safe_mode_0600_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            view = controller.discover_repo(repo)
            original_write = os.write

            def short_write(fd, data):
                return original_write(fd, data[:max(1, min(7, len(data)))])

            with mock.patch.object(os, "write", side_effect=short_write):
                adapter.append_adapter_audit(view.common_dir, "run-1", "action", "attempt",
                                             action="commit", stage="auto_commit")
                adapter.append_adapter_audit(view.common_dir, "run-1", "action", "attempt",
                                             action="commit", stage="auto_commit")
            path = adapter.adapter_root(view.common_dir) / "adapter-audit.jsonl"
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(records), 1)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertTrue(records[0]["event_id"].startswith("adapter:audit:"))
            serialized = json.dumps(records[0])
            for forbidden in ("command", "environment", "token", "prompt", "path"):
                self.assertNotIn(forbidden, serialized.lower())

    def test_audit_refuses_symlink_target(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            view = controller.discover_repo(repo)
            root = adapter.adapter_root(view.common_dir)
            root.mkdir(parents=True, exist_ok=True)
            target = Path(td) / "outside.log"
            target.write_text("")
            (root / "adapter-audit.jsonl").symlink_to(target)
            with self.assertRaises(OSError):
                adapter.append_adapter_audit(view.common_dir, "run-1", "action", "attempt")
            self.assertEqual(target.read_text(), "")


class CiAndWatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = init_repo(Path(self.temp.name) / "repo")
        start_run(self.repo)
        self.linked = add_linked(self.repo)
        self.repo_view = controller.discover_repo(self.repo)
        self.head = git(self.linked, "rev-parse", "HEAD").stdout.strip()

    def tearDown(self):
        self.temp.cleanup()

    def pull_request(self, **updates):
        value = {
            "number": 9, "state": "OPEN", "isDraft": False,
            "headRefOid": self.head, "headRefName": "feature/lifecycle",
            "baseRefName": "main", "headRepositoryOwner": {"login": "owner"},
            "repository": "owner/repo", "url": "https://example.invalid/pr/9",
        }
        value.update(updates)
        return value

    def test_required_check_matrix_never_passes_missing_unknown_or_pending(self):
        cases = [
            ([], "unknown"),
            ([{"name": "build", "bucket": "mystery"}], "unknown"),
            ([{"name": "build", "bucket": "pending"}], "pending"),
            ([{"name": "build", "bucket": "fail"}], "failed"),
            ([{"name": "build", "bucket": "pass"}], "passing"),
            (
                [
                    {"name": "build", "bucket": "pass"},
                    {"name": "security", "bucket": "pending"},
                ],
                "pending",
            ),
        ]
        for checks, expected in cases:
            with self.subTest(expected=expected, checks=checks):
                self.assertEqual(adapter.classify_required_checks(checks)[0], expected)
        self.assertEqual(adapter.classify_required_checks({"bad": "shape"})[0], "unknown")

    def test_ci_reconciliation_is_exact_head_and_records_only_strict_result(self):
        pull_request = {
            "number": 9,
            "state": "OPEN",
            "isDraft": False,
            "headRefOid": self.head,
            "headRefName": "feature/lifecycle",
            "baseRefName": "main",
            "headRepositoryOwner": {"login": "owner"},
            "repository": "owner/repo",
            "url": "https://example.invalid/pr/9",
        }
        checks = [{"name": "required-build", "state": "SUCCESS", "bucket": "pass"}]
        with (
            mock.patch.object(adapter, "query_exact_pr", return_value=pull_request),
            mock.patch.object(
                adapter,
                "run_command",
                return_value=completed_process(stdout=json.dumps(checks)),
            ) as command,
        ):
            result = adapter.reconcile_ci(self.repo_view, "run-1", self.head)
        self.assertEqual(result["status"], "passing")
        self.assertEqual(result["outcome"], "terminal")
        self.assertIn("--required", command.call_args.args[0])

        with mock.patch.object(adapter, "query_exact_pr") as query:
            stale = adapter.reconcile_ci(self.repo_view, "run-1", "0" * 40)
        self.assertEqual(stale["outcome"], "stale")
        query.assert_not_called()

    def test_pr_identity_rejects_base_owner_and_ignores_other_heads(self):
        state = adapter.load_run_state(self.repo_view, "run-1")
        for updates in ({"baseRefName": "wrong"}, {"headRepositoryOwner": {"login": "fork"}}):
            proc = completed_process(stdout=json.dumps([self.pull_request(**updates)]))
            with self.subTest(updates=updates):
                with self.assertRaises(adapter.AdapterError) as raised:
                    adapter.parse_prs(proc, state, self.head, "owner/repo", "owner")
                self.assertEqual(raised.exception.code, "pr_identity_mismatch")
        other = completed_process(stdout=json.dumps([
            self.pull_request(headRefOid="0" * len(self.head))]))
        self.assertEqual(adapter.parse_prs(other, state, self.head, "owner/repo", "owner"), [])

    def test_passing_ci_rechecks_pr_and_rejects_state_churn(self):
        checks = [{"name": "required-build", "bucket": "pass"}]
        with (
            mock.patch.object(adapter, "query_exact_pr",
                              side_effect=[self.pull_request(), self.pull_request(state="CLOSED")]),
            mock.patch.object(adapter, "run_command",
                              return_value=completed_process(stdout=json.dumps(checks))),
        ):
            result = adapter.reconcile_ci(self.repo_view, "run-1", self.head)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["outcome"], "pending")
        state = adapter.load_run_state(self.repo_view, "run-1")
        self.assertEqual([fact["status"] for fact in state["facts"] if fact["kind"] == "pr"],
                         ["open", "closed"])

    def test_nonzero_check_command_can_never_record_passing(self):
        checks = [{"name": "required-build", "bucket": "pass"}]
        with (
            mock.patch.object(adapter, "query_exact_pr", return_value=self.pull_request()),
            mock.patch.object(adapter, "run_command",
                              return_value=completed_process(returncode=8, stdout=json.dumps(checks))),
        ):
            result = adapter.reconcile_ci(self.repo_view, "run-1", self.head)
        self.assertEqual(result["status"], "unknown")
        self.assertTrue(result["degraded"])

    def test_watcher_handshake_failure_and_poll_budget_terminate(self):
        fake = mock.Mock(pid=4242)
        fake.poll.return_value = None
        with (
            mock.patch.object(subprocess, "Popen", return_value=fake),
            mock.patch.object(adapter, "child_ready", return_value=False),
        ):
            with self.assertRaises(adapter.AdapterError) as raised:
                adapter.spawn_watcher(self.repo_view, "run-1", self.head)
        self.assertEqual(raised.exception.code, "watcher_not_ready")
        fake.terminate.assert_called_once()

        marker, _, _, _ = adapter.watcher_paths(self.repo_view.common_dir, "run-1", self.head)
        marker.unlink()
        pending = {"ok": False, "outcome": "pending", "status": "unknown",
                   "sha": self.head, "degraded": True}
        args = namespace(run_id="run-1", sha=self.head, once=False, interval=0, max_polls=2)
        with mock.patch.object(adapter, "safe_reconcile_ci", return_value=pending) as reconcile:
            result = adapter.watch(args, self.repo)
        self.assertEqual(result["outcome"], "timeout")
        self.assertEqual(reconcile.call_count, 2)
        parsed = adapter.parser().parse_args(["watch", "--run-id", "run-1", "--sha", self.head])
        self.assertEqual(parsed.max_polls, 80)

    def test_one_detached_watcher_per_run_and_sha(self):
        marker, _, _, _ = adapter.watcher_paths(self.repo_view.common_dir, "run-1", self.head)
        marker.parent.mkdir(parents=True)
        controller.atomic_json(
            marker,
            {
                "schema_version": adapter.ADAPTER_SCHEMA_VERSION,
                "run_id": "run-1",
                "sha": self.head,
                "status": "running",
                "pid": os.getpid(),
                "updated_at": adapter.now(),
            },
        )
        with mock.patch.object(subprocess, "Popen") as popen:
            duplicate = adapter.spawn_watcher(self.repo_view, "run-1", self.head)
        self.assertTrue(duplicate["duplicate"])
        popen.assert_not_called()

        marker.unlink()
        fake = mock.Mock(pid=424242)
        with (
            mock.patch.object(subprocess, "Popen", return_value=fake) as popen,
            mock.patch.object(adapter, "child_ready", return_value=True),
        ):
            started = adapter.spawn_watcher(self.repo_view, "run-1", self.head)
        self.assertTrue(started["started"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertIs(popen.call_args.kwargs["stdout"], subprocess.DEVNULL)


class StopTerminationTests(unittest.TestCase):
    def test_detached_watcher_allows_stop_and_deferred_action_blocks_once(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            start_run(repo)
            view = controller.discover_repo(repo)
            head = git(repo, "rev-parse", "HEAD").stdout.strip()
            watching = {
                "outcome": "watching", "after": {"action": "wait_ci", "reason": "pending",
                                                      "evidence": {"git": {"head_sha": head}}},
            }
            with mock.patch.object(adapter, "tick", return_value=watching):
                allowed = adapter.hook_stop(view, "session-1")
            self.assertEqual(allowed, {"lifecycle_bound": True})

            deferred = {
                "outcome": "approval_required", "reason_code": "action_deferred",
                "after": {"action": "merge_eligible", "reason": "deferred",
                          "evidence": {"git": {"head_sha": head}}},
            }
            with mock.patch.object(adapter, "tick", return_value=deferred):
                first = adapter.hook_stop(view, "session-1")
                second = adapter.hook_stop(view, "session-1")
            self.assertEqual(first["decision"], "block")
            self.assertEqual(second, {"lifecycle_bound": True})
            notices = list((adapter.adapter_root(view.common_dir) / "stop-notices").glob("*.json"))
            self.assertEqual(len(notices), 1)


class HookBridgeTests(unittest.TestCase):
    def invoke(self, repo: Path, hook: Path, event: str, env: dict[str, str], payload: str):
        return subprocess.run([str(hook), event], cwd=str(repo), env=env, input=payload,
                              capture_output=True, text=True, check=False)

    def fixture(self, root: Path, config: str):
        repo = init_repo(root / "repo")
        (repo / ".claude-atomic.yaml").write_text(config)
        home = root / "home"
        hook = home / ".dotfiles" / ".claude" / "hooks" / "lifecycle-hook.sh"
        hook.parent.mkdir(parents=True)
        shutil.copy2(ROOT / ".claude" / "hooks" / "lifecycle-hook.sh", hook)
        adapter_path = home / ".dotfiles" / "scripts" / "ai" / "lifecycle_adapter.py"
        adapter_path.parent.mkdir(parents=True)
        env = os.environ.copy()
        env["HOME"] = str(home)
        payload = json.dumps({"cwd": str(repo), "session_id": "bridge-session",
                              "tool_name": "Write", "tool_input": {"file_path": str(repo / "README.md")}})
        return repo, hook, adapter_path, env, payload

    def test_missing_crashing_corrupt_and_malformed_bridge_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            repo, hook, adapter_path, env, payload = self.fixture(Path(td), lifecycle_config())
            missing = self.invoke(repo, hook, "PreToolUse", env, payload)
            self.assertEqual(json.loads(missing.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
            adapter_path.write_text("import sys\nsys.exit(7)\n")
            crashed = self.invoke(repo, hook, "Stop", env, payload)
            self.assertEqual(json.loads(crashed.stdout)["decision"], "block")
            (repo / ".claude-atomic.yaml").write_text("lifecycle: [broken\n")
            corrupt = self.invoke(repo, hook, "PreToolUse", env, payload)
            self.assertEqual(json.loads(corrupt.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
            (repo / ".claude-atomic.yaml").write_text(lifecycle_config())
            malformed = self.invoke(repo, hook, "PreToolUse", env, "{bad")
            self.assertEqual(json.loads(malformed.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_disabled_and_explicit_unbound_stop_use_silent_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            repo, hook, adapter_path, env, payload = self.fixture(
                Path(td), lifecycle_config(enabled=False))
            disabled = self.invoke(repo, hook, "PreToolUse", env, payload)
            self.assertEqual(disabled.stdout, "")
            (repo / ".claude-atomic.yaml").write_text(lifecycle_config())
            adapter_path.write_text('import json\nprint(json.dumps({"lifecycle_bound": False}))\n')
            unbound = self.invoke(repo, hook, "Stop", env, payload)
            self.assertEqual(unbound.stdout, "")


class HookDispatcherAndSettingsTests(unittest.TestCase):
    def dispatcher_fixture(self, root: Path):
        hooks = root / "hooks"
        hooks.mkdir()
        shutil.copy2(ROOT / ".claude" / "hooks" / "stop.sh", hooks / "stop.sh")
        for name in ("session-end.sh", "plan-completion-check.sh", "feedback-capture.sh"):
            (hooks / name).write_text("#!/usr/bin/env bash\nexit 0\n")
        (hooks / "task-gate.sh").write_text(
            "#!/usr/bin/env bash\nprintf '%s' \"${TASK_OUT:-}\"\nprintf x >> \"${TASK_LOG}\"\n"
        )
        (hooks / "lifecycle-hook.sh").write_text(
            "#!/usr/bin/env bash\nprintf '%s' \"${LIFECYCLE_OUT:-}\"\nprintf x >> \"${LIFECYCLE_LOG}\"\n"
        )
        (hooks / "git-pipeline-gate.sh").write_text(
            "#!/usr/bin/env bash\nprintf '%s' \"${GIT_OUT:-}\"\nprintf x >> \"${GIT_LOG}\"\n"
        )
        bin_dir = root / "bin"
        bin_dir.mkdir()
        (bin_dir / "lean-ctx").write_text("#!/usr/bin/env bash\nexit 0\n")
        for path in list(hooks.iterdir()) + [bin_dir / "lean-ctx"]:
            path.chmod(0o755)
        return hooks / "stop.sh", bin_dir

    def run_stop(self, root: Path, **values):
        script, bin_dir = self.dispatcher_fixture(root)
        env = os.environ.copy()
        env.update({key: str(value) for key, value in values.items()})
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        for key in ("TASK_LOG", "LIFECYCLE_LOG", "GIT_LOG"):
            env.setdefault(key, str(root / key.lower()))
        return run(root, str(script), env=env, check=False), env

    def test_stop_is_first_block_wins_and_bound_lifecycle_supersedes_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            task_block = json.dumps({"decision": "block", "reason": "task first"})
            proc, env = self.run_stop(
                root,
                TASK_OUT=task_block,
                LIFECYCLE_OUT=json.dumps(
                    {"decision": "block", "reason": "lifecycle", "lifecycle_bound": True}
                ),
                GIT_OUT=json.dumps({"decision": "block", "reason": "legacy"}),
            )
            self.assertEqual(json.loads(proc.stdout), json.loads(task_block))
            self.assertFalse(Path(env["LIFECYCLE_LOG"]).exists())
            self.assertFalse(Path(env["GIT_LOG"]).exists())

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            lifecycle_block = {
                "decision": "block",
                "reason": "lifecycle first",
                "lifecycle_bound": True,
            }
            proc, env = self.run_stop(
                root,
                TASK_OUT="",
                LIFECYCLE_OUT=json.dumps(lifecycle_block),
                GIT_OUT=json.dumps({"decision": "block", "reason": "legacy"}),
            )
            self.assertEqual(json.loads(proc.stdout), {"decision": "block", "reason": "lifecycle first"})
            self.assertFalse(Path(env["GIT_LOG"]).exists())

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            legacy = {"decision": "block", "reason": "legacy fallback"}
            proc, env = self.run_stop(
                root,
                TASK_OUT="",
                LIFECYCLE_OUT="",
                GIT_OUT=json.dumps(legacy),
            )
            self.assertEqual(json.loads(proc.stdout), legacy)
            self.assertTrue(Path(env["GIT_LOG"]).exists())

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            legacy = {"decision": "block", "reason": "explicit unbound fallback"}
            proc, env = self.run_stop(
                root, TASK_OUT="", LIFECYCLE_OUT=json.dumps({"lifecycle_bound": False}),
                GIT_OUT=json.dumps(legacy))
            self.assertEqual(json.loads(proc.stdout), legacy)
            self.assertTrue(Path(env["GIT_LOG"]).exists())

    def test_canonical_settings_and_dispatchers_use_portable_lifecycle_wiring(self):
        settings_path = ROOT / "ai" / "config" / "claude" / "settings.base.json"
        settings = json.loads(settings_path.read_text())
        entries = settings["hooks"]["PreToolUse"]
        lifecycle_entries = [item for item in entries
                             if item["matcher"] == "Edit|Write|MultiEdit|NotebookEdit|Bash"]
        self.assertEqual(len(lifecycle_entries), 1)
        command = lifecycle_entries[0]["hooks"][0]["command"]
        self.assertEqual(
            command,
            'bash "$HOME/.dotfiles/.claude/hooks/lifecycle-hook.sh" PreToolUse',
        )
        self.assertNotIn("args", lifecycle_entries[0]["hooks"][0])
        self.assertIn("lifecycle-hook.sh\" SessionStart", (ROOT / ".claude/hooks/sessionstart.sh").read_text())
        self.assertIn(
            "lifecycle-hook.sh\" UserPromptSubmit",
            (ROOT / ".claude/hooks/userpromptsubmit.sh").read_text(),
        )

    def test_adapter_is_stdlib_only_phased_and_materially_smaller_than_controller(self):
        adapter_source = Path(adapter.__file__).read_text()
        controller_source = Path(controller.__file__).read_text()
        self.assertLess(len(adapter_source.splitlines()), len(controller_source.splitlines()) * 0.8)
        self.assertIn("def execute_action(", adapter_source)
        self.assertIn("def reconcile_ci(", adapter_source)
        self.assertIn("def hook_pre_write(", adapter_source)


if __name__ == "__main__":
    unittest.main()
