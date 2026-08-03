"""Hermetic behavioral tests for the Claude lifecycle adapter."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "ai"))

import git_lifecycle as controller  # noqa: E402
import lifecycle_adapter as adapter  # noqa: E402


def run(cwd: Path, *args: str, check: bool = True, env: dict[str, str] | None = None,
        stdin: str | None = None):
    # stdin defaults to DEVNULL, never the parent's. The hook scripts under test open
    # with `_INPUT="$(cat)"`, so an inherited stdin makes them block on the test
    # runner's own terminal forever rather than failing -- which is how
    # HookDispatcherAndSettingsTests came to hang the whole suite.
    proc = subprocess.run(
        list(args),
        cwd=str(cwd),
        env=env,
        input=stdin,
        stdin=None if stdin is not None else subprocess.DEVNULL,
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
        "  rollout_approved: true",
        "  rollout_approved_by: lifecycle-test",
        "  github_actor: owner",
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
        "  decision: lifecycle adapter hermetic test approval",
    ]
    return "\n".join(lines) + "\n"


def init_repo(path: Path, *, opted_in: bool = True) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "adapter-test@example.com")
    git(path, "config", "user.name", "Adapter Test")
    git(path, "remote", "add", "origin", "https://user@github.com/owner/repo.git")
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

    def test_reverse_binding_requires_explicit_release_and_takeover(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            start_run(repo, session_id="session-a", run_id="run-a")
            view = controller.discover_repo(repo)
            with self.assertRaises(adapter.AdapterError) as shared:
                adapter.write_binding(view, "session-b", "run-a")
            self.assertEqual(shared.exception.code, "run_already_bound")

            released = adapter.release_session(
                namespace(session_id="session-a", run_id="run-a", reason="handoff"), repo)
            self.assertFalse(released["bound"])
            with self.assertRaises(adapter.AdapterError) as implicit:
                adapter.write_binding(view, "session-b", "run-a")
            self.assertEqual(implicit.exception.code, "takeover_required")

            taken = adapter.takeover_session(
                namespace(
                    session_id="session-b", from_session_id="session-a",
                    run_id="run-a", reason="continue approved run",
                ),
                repo,
            )
            self.assertTrue(taken["bound"])
            self.assertEqual(adapter.load_binding(view, "session-b")["run_id"], "run-a")
            audit = (adapter.adapter_root(view.common_dir) / "adapter-audit.jsonl").read_text()
            self.assertIn("session_release", audit)
            self.assertIn("session_takeover", audit)

    def test_takeover_cannot_orphan_the_new_sessions_other_live_run(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            start_run(repo, session_id="session-a", run_id="run-a")
            adapter.release_session(
                namespace(session_id="session-a", run_id="run-a", reason="handoff"), repo)
            base = git(repo, "rev-parse", "HEAD").stdout.strip()
            adapter.start(
                namespace(
                    session_id="session-b", run_id="run-b", task="second run",
                    base_branch="main", base_sha=base, intended_branch="feature/second",
                    owned_paths=["other"], worktree=None, work_unit_id="unit-b",
                    work_unit="second run work",
                ),
                repo,
            )
            with self.assertRaises(adapter.AdapterError) as raised:
                adapter.takeover_session(
                    namespace(
                        session_id="session-b", from_session_id="session-a",
                        run_id="run-a", reason="invalid handoff",
                    ),
                    repo,
                )
            self.assertEqual(raised.exception.code, "session_already_bound")


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
        self.assertEqual(set(unbound), {"lifecycle_hook", "hookSpecificOutput"})
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
        self.assertEqual(allowed["lifecycle_hook"]["binding"], "bound")

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
        self.assertEqual(stop_result["lifecycle_hook"]["binding"], "bound")

    def test_notebook_edit_and_direct_bash_mutations_are_gated(self):
        repo = controller.discover_repo(self.linked)
        allowed = adapter.hook_pre_write(
            self.payload("session-1", "NotebookEdit",
                         {"notebook_path": str(self.linked / "owned" / "notes.ipynb")}),
            repo, "session-1")
        self.assertEqual(allowed["lifecycle_hook"]["binding"], "bound")
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
        exact_adapter = str(Path(adapter.__file__).resolve())
        allowed_commands = (
            "git status", "git diff", "gh pr view 1",
            f"python3 {exact_adapter} status --session-id session-1",
            f"{adapter.VALIDATE} --json",
            "bash -n scripts/ai/commit.sh",
            "shellcheck scripts/ai/commit.sh",
            "python3 -m json.tool ai/config/claude/settings.base.json",
        )
        for command in allowed_commands:
            with self.subTest(allowed=command):
                result = adapter.hook_pre_write(
                    self.payload("session-1", "Bash", {"command": command}), repo, "session-1")
                self.assertEqual(result["lifecycle_hook"]["binding"], "bound")

    def test_bash_default_deny_rejects_final_review_bypasses(self):
        repo = controller.discover_repo(self.linked)
        exact_adapter = str(Path(adapter.__file__).resolve())
        lookalike = self.linked / "owned" / "lifecycle_adapter.py"
        lookalike.parent.mkdir(exist_ok=True)
        lookalike.write_text("#!/usr/bin/env python3\n")
        blocked = (
            f"python3 {lookalike} status --session-id session-1",
            f"python3 {exact_adapter} status --session-id wrong-session",
            "/tmp/git status",
            "/tmp/gh pr view 1",
            "/tmp/python3 -m unittest scripts.test_lifecycle_adapter",
            f"{adapter.COMMIT} -m 'fix: bypass' -m bypass",
            f"{adapter.STACK} create feature/bypass main",
            "bash -c 'python3 -m unittest scripts.test_lifecycle_adapter'",
            "python3 -c 'import os; os.system(\"git add -A\")'",
            "git -c alias.read=!touch read",
            "git update-ref refs/heads/main HEAD",
            "git symbolic-ref HEAD refs/heads/main",
            "git worktree add /tmp/bypass main",
            "git hash-object -w README.md",
            "git diff --out=/tmp/leak",
            "git show --textconv HEAD:README.md",
            "gh api --method POST repos/owner/repo/issues",
            "gh pr edit 1 --add-label bypass",
            "gh pr view 1 --web=true",
            "python3 -m unittest /tmp/evil.py",
            "python3 -m unittest evil",
            "python3 -m unittest scripts.test_lifecycle_adapter",
            "python3 -m unittest scripts.test_lifecycle_adapter.HookTests.test_payload",
            "python3 -m scripts.test_lifecycle_adapter",
            "python3 scripts/test_lifecycle_adapter.py",
            "git diff *",
            "git diff '?'",
            "git diff [a-z]",
            "git diff '{--output,/tmp/x}'",
            "git diff \\*",
            "git diff ~",
            "git diff HEAD~1",
            "git --paginate diff",
            "git -c core.pager='touch /tmp/payload' diff",
            "git diff --output=/tmp/payload",
            "alias git='touch /tmp/bypass'",
            "git status > /tmp/status",
            "git status && git add -A",
        )
        for command in blocked:
            with self.subTest(command=command):
                result = adapter.hook_pre_write(
                    self.payload("session-1", "Bash", {"command": command}), repo, "session-1")
                self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

        expansion_probes = (
            "git diff *", "git diff '?'", "git diff [a-z]",
            "git diff {--output,/tmp/x}", 'git diff "{--output,/tmp/x}"',
            "git diff \\*", "git diff ~", "git diff HEAD~1",
        )
        with mock.patch.object(adapter, "run_command") as external_process:
            for command in expansion_probes:
                with self.subTest(expansion=command):
                    self.assertIsNone(adapter.command_tokens(command))
                    result = adapter.hook_pre_write(
                        self.payload("session-1", "Bash", {"command": command}),
                        repo,
                        "session-1",
                    )
                    self.assertEqual(
                        result["hookSpecificOutput"]["permissionDecision"], "deny")
            external_process.assert_not_called()

        with mock.patch.dict(os.environ, {"BASH_FUNC_git%%": "() { touch /tmp/bypass; }"}):
            aliased = adapter.hook_pre_write(
                self.payload("session-1", "Bash", {"command": "git status"}),
                repo,
                "session-1",
            )
        self.assertEqual(aliased["hookSpecificOutput"]["permissionDecision"], "deny")

        for tool_name in ("EnterWorktree", "ExitWorktree"):
            with self.subTest(tool_name=tool_name):
                worktree = adapter.hook_pre_write(
                    self.payload("session-1", tool_name, {"path": str(self.linked)}),
                    repo,
                    "session-1",
                )
                self.assertEqual(
                    worktree["hookSpecificOutput"]["permissionDecision"], "deny")
                self.assertIn(
                    "Worktree", worktree["hookSpecificOutput"]["permissionDecisionReason"])
        settings = json.loads((ROOT / "ai/config/claude/settings.base.json").read_text())
        matchers = [item["matcher"] for item in settings["hooks"]["PreToolUse"]]
        self.assertTrue(any("EnterWorktree" in matcher for matcher in matchers))
        self.assertFalse(any("pctx" in matcher for matcher in matchers))

    def test_control_plane_is_rejected_at_start_and_every_write_gate(self):
        repo = controller.discover_repo(self.linked)
        for path in (
            ".claude", ".claude/settings.json", ".claude/settings.local.json",
            ".CLAUDE/SETTINGS.JSON", "scripts",
            "scripts/ai/lifecycle_adapter.py", "SCRIPTS/AI/COMMIT.SH", "ai/config/claude",
        ):
            with self.subTest(path=path):
                with self.assertRaises(adapter.AdapterError) as raised:
                    adapter.validate_owned_paths([path])
                self.assertEqual(raised.exception.code, "control_plane_owned")
        control_dir = self.repo / ".claude"
        control_dir.mkdir(exist_ok=True)
        alias = self.repo / "owned-control-alias"
        alias.symlink_to(control_dir, target_is_directory=True)
        with self.assertRaises(adapter.AdapterError) as alias_error:
            adapter.validate_owned_paths([alias.name], self.repo)
        self.assertEqual(alias_error.exception.code, "control_plane_owned")
        with self.assertRaises(adapter.AdapterError) as start_error:
            adapter.start(
                namespace(
                    session_id="other-session", run_id="other-run", task="invalid ownership",
                    base_branch="main", base_sha=git(self.repo, "rev-parse", "HEAD").stdout.strip(),
                    intended_branch="feature/invalid", owned_paths=[".claude"], worktree=None,
                    work_unit_id="invalid", work_unit="must not start",
                ),
                self.repo,
            )
        self.assertEqual(start_error.exception.code, "control_plane_owned")
        result = adapter.hook_pre_write(
            self.payload(
                "session-1", "Write",
                {"file_path": str(self.linked / ".claude" / "settings.json")},
            ),
            repo,
            "session-1",
        )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("control-plane", result["hookSpecificOutput"]["permissionDecisionReason"])

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

    def stack_action_decision(self, decision):
        journal = adapter.begin_action_journal(
            self.repo_view, "run-1", decision, "auto_stack",
        )
        return journal, {
            **decision,
            "_adapter_action_attempt": {
                "run_id": "run-1",
                "attempt_id": journal["attempt_id"],
                "evidence_id": journal["evidence_id"],
            },
        }

    def install_stack_tracking(self):
        (self.repo / ".git" / ".graphite_repo_config").write_text("{}\n")
        bin_dir = Path(self.temp.name) / "stack-bin"
        bin_dir.mkdir(exist_ok=True)
        log = Path(self.temp.name) / "gt-commands.log"
        gt = bin_dir / "gt"
        gt.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\n' \"$*\" >> \"$GT_LOG\"\n"
            "case \"$1 $2\" in\n"
            "  'branch track') exit 0 ;;\n"
            "  'branch info') printf 'Parent: main\n'; exit 0 ;;\n"
            "  *) exit 1 ;;\n"
            "esac\n"
        )
        gt.chmod(0o755)
        bare = Path(self.temp.name) / "stack-origin.git"
        if not bare.exists():
            git(Path(self.temp.name), "init", "-q", "--bare", str(bare))
            git(
                self.repo, "push", "-q", str(bare),
                "refs/heads/main:refs/heads/main",
            )
        return {
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GT_LOG": str(log),
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"url.file://{bare}.insteadOf",
            "GIT_CONFIG_VALUE_0": "https://user@github.com/owner/repo.git",
        }, log

    def test_create_stack_uses_canonical_exact_base_and_a2_gate(self):
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        calls = []

        def record(args, cwd, check=True, **kwargs):
            calls.append(([str(item) for item in args], cwd, check, kwargs))
            return completed_process(args)

        journal, action_decision = self.stack_action_decision(decision)
        facts = {"strict": "verified"}
        with (
            mock.patch.object(adapter, "run_command", side_effect=record),
            mock.patch.object(adapter, "stack_completion_facts", return_value=facts),
            mock.patch.object(adapter, "write_stack_completion_receipt") as receipt,
        ):
            adapter.action_create_stack(self.repo_view, state, action_decision)
        receipt.assert_called_once_with(
            self.repo_view,
            state,
            action_decision["_adapter_action_attempt"],
            facts,
        )
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
        stack_env = calls[0][3]["env"]
        hook_config_index = int(stack_env["GIT_CONFIG_COUNT"]) - 1
        self.assertEqual(stack_env[f"GIT_CONFIG_KEY_{hook_config_index}"], "core.hooksPath")
        self.assertEqual(stack_env[f"GIT_CONFIG_VALUE_{hook_config_index}"], "/dev/null")

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

    def test_lifecycle_stack_disables_checkout_and_reference_hooks_only_for_action(self):
        state = adapter.load_run_state(self.repo_view, "run-1")
        git(self.repo, "remote", "remove", "origin")
        hooks = self.repo / ".git" / "hooks"
        hook_log = Path(self.temp.name) / "stack-hooks.log"
        descendant_log = Path(self.temp.name) / "stack-descendant.log"
        hook_source = """#!/usr/bin/env bash
printf '%s|%s|%s\n' "$(basename "$0")" "${GH_TOKEN:-}" "${LIFECYCLE_GITHUB_TOKEN:-}" >> "$HOOK_LOG"
(sleep 0.2; printf 'detached\n' >> "$DESCENDANT_LOG") &
"""
        for name in ("post-checkout", "reference-transaction"):
            path = hooks / name
            path.write_text(hook_source)
            path.chmod(0o755)
        action_env, _ = self.install_stack_tracking()
        action_env.update({
            "HOOK_LOG": str(hook_log),
            "DESCENDANT_LOG": str(descendant_log),
        })
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        _, action_decision = self.stack_action_decision(decision)
        with mock.patch.dict(os.environ, action_env):
            adapter.action_create_stack(self.repo_view, state, action_decision)
            time.sleep(0.4)
            self.assertFalse(hook_log.exists())
            self.assertFalse(descendant_log.exists())

            git(self.repo, "checkout", "-q", "-b", "feature/ordinary-hooks")
            time.sleep(0.4)
        lines = hook_log.read_text().splitlines()
        self.assertTrue(any(line.startswith("reference-transaction|") for line in lines))
        self.assertTrue(any(line.startswith("post-checkout|") for line in lines))
        self.assertTrue(descendant_log.is_file())

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

    def test_policy_actor_is_required_and_contract_ignores_mutable_auth(self):
        linked = add_linked(self.repo)
        policy_path = linked / ".claude-atomic.yaml"
        original = policy_path.read_text()
        invalid_policies = (
            original.replace("  github_actor: owner\n", ""),
            original.replace("  github_actor: owner\n", "  github_actor: wrong actor\n"),
        )
        for invalid in invalid_policies:
            with self.subTest(policy=invalid):
                policy_path.write_text(invalid)
                with self.assertRaises(adapter.AdapterError) as raised:
                    adapter.policy_snapshot(linked)
                self.assertEqual(raised.exception.code, "invalid_lifecycle_config")
        policy_path.write_text(original)

        with mock.patch.dict(
            os.environ,
            {"GH_ACTOR": "wrong-active-actor", "GITHUB_ACTOR": "wrong-ci-actor"},
        ):
            contract = adapter.capture_contract(
                self.repo_view, "run-1", controller.discover_repo(linked))
        self.assertEqual(contract["policy"]["github_actor"], "owner")
        self.assertEqual(contract["expected_actor"], "owner")

        with (
            mock.patch.dict(os.environ, {"GH_ACTOR": "", "GITHUB_ACTOR": ""}),
            mock.patch.object(
                adapter,
                "run_command",
                return_value=completed_process(stdout="wrong-current-actor\n"),
            ) as current_auth,
        ):
            contract = adapter.capture_contract(
                self.repo_view, "run-1", controller.discover_repo(linked))
        current_auth.assert_not_called()
        self.assertEqual(contract["expected_actor"], "owner")

    def test_policy_remote_gate_and_sha_drift_fail_closed(self):
        linked = add_linked(self.repo)
        original_policy = (linked / ".claude-atomic.yaml").read_text()
        (linked / ".claude-atomic.yaml").write_text(original_policy + "# drift\n")
        with self.assertRaises(adapter.AdapterError) as policy:
            adapter.tick(namespace(run_id="run-1"), linked)
        self.assertEqual(policy.exception.code, "policy_drift")

        (linked / ".claude-atomic.yaml").write_text(original_policy)
        bare = Path(self.temp.name) / "drift.git"
        git(Path(self.temp.name), "init", "-q", "--bare", str(bare))
        git(linked, "remote", "set-url", "origin", str(bare))
        with self.assertRaises(adapter.AdapterError) as remote:
            adapter.tick(namespace(run_id="run-1"), linked)
        self.assertEqual(remote.exception.code, "remote_drift")
        git(linked, "remote", "set-url", "origin", "https://user@github.com/owner/repo.git")

        state = adapter.load_run_state(self.repo_view, "run-1")
        with mock.patch.object(adapter, "pipeline_gate_level", return_value="off"):
            with self.assertRaises(adapter.AdapterError) as gate:
                adapter.verify_contract(self.repo_view, state, controller.discover_repo(linked))
        self.assertEqual(gate.exception.code, "pipeline_gate_off")

        ready_run(self.repo, linked)
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        git(linked, "commit", "-q", "--allow-empty", "-m", "chore: concurrent head drift")
        action = mock.Mock()
        with mock.patch.object(adapter, "resolve_autonomy", return_value=(True, "authorized")):
            result = adapter.execute_action(self.repo_view, "run-1", decision, state, action)
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(result["reason_code"], "stale_inspection")
        action.assert_not_called()

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

        def canonical(args, cwd, check=True, **kwargs):
            executable = str(args[0])
            calls.append(executable)
            if Path(executable) == adapter.COMMIT:
                run(
                    cwd,
                    "git", "commit", "-q", "-m", str(args[2]), "-m", str(args[4]),
                    env=adapter.process_environment(kwargs.get("env")),
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

    def test_failed_commit_validation_requires_explicit_recovery_to_editable(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)

        def fail_validation(args, cwd, check=True, **kwargs):
            if Path(str(args[0])) == adapter.VALIDATE:
                raise adapter.AdapterError("validation failed", "action_command_failed")
            return completed_process(args)

        with mock.patch.object(adapter, "run_command", side_effect=fail_validation):
            failed = adapter.tick(namespace(run_id="run-1"), linked)
        self.assertEqual(failed["outcome"], "action_failed")
        self.assertEqual(failed["reason_code"], "commit_validation_failed")
        self.assertEqual(failed["after"]["action"], "commit")
        self.assertTrue((self.repo_view.common_dir / "autonomy-demoted-auto_commit").is_file())

        recovered = adapter.recover_edit(
            namespace(
                run_id="run-1",
                reason="repair the failed validation before declaring readiness again",
            ),
            linked,
        )
        self.assertEqual(recovered["status"]["action"], "editing")
        self.assertTrue((linked / "owned" / "change.txt").is_file())

    def test_commit_cas_rejects_post_stage_content_mutation(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        commit_called = False

        def mutate_after_stage(args, cwd, check=True, **kwargs):
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

    def test_concurrent_default_index_mutation_cannot_enter_private_commit(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")

        def concurrent_index_then_commit(args, cwd, check=True, **kwargs):
            executable = Path(str(args[0]))
            if executable == adapter.COMMIT:
                (linked / "README.md").write_text("concurrent default-index change\n")
                git(linked, "add", "README.md")
                run(
                    cwd,
                    "git", "commit", "-q", "-m", str(args[2]), "-m", str(args[4]),
                    env=adapter.process_environment(kwargs.get("env")),
                )
            return completed_process(args, stdout='{"passed":true}\n')

        with mock.patch.object(adapter, "run_command", side_effect=concurrent_index_then_commit):
            adapter.action_commit(self.repo_view, state, decision)
        self.assertEqual(
            git(linked, "show", "HEAD:README.md").stdout,
            "initial\n",
            "concurrent default-index content entered the approved commit",
        )
        self.assertIn("README.md", git(linked, "diff", "--cached", "--name-only").stdout.split())
        self.assertEqual((linked / "README.md").read_text(), "concurrent default-index change\n")

    def test_push_refuses_fresh_actor_or_repository_drift(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        git(linked, "add", "owned/change.txt")
        git(linked, "commit", "-q", "-m", "feat(lifecycle): prepare identity gate",
            "-m", "Push requires the immutable policy-owned GitHub identity.")
        adapter.capture_contract(self.repo_view, "run-1", controller.discover_repo(linked))
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")

        for identity in (("other/repo", "owner"), ("owner/repo", "wrong-actor")):
            with self.subTest(identity=identity):
                with (
                    mock.patch.object(
                        adapter, "pinned_github_environment", return_value={"GH_TOKEN": "test-token"}),
                    mock.patch.object(adapter, "repository_identity", return_value=identity),
                    mock.patch.object(adapter, "run_command") as command,
                ):
                    with self.assertRaises(adapter.AdapterError) as raised:
                        adapter.action_push(self.repo_view, state, decision)
                self.assertEqual(raised.exception.code, "github_identity_drift")
                command.assert_not_called()

    def test_lifecycle_push_disables_prepush_and_reference_hooks_without_token_leak(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        git(linked, "add", "owned/change.txt")
        git(linked, "commit", "-q", "-m", "feat(lifecycle): prepare hook-safe push",
            "-m", "Lifecycle pushes must not execute repository-owned Git hooks.")
        bare = Path(self.temp.name) / "hook-origin.git"
        git(Path(self.temp.name), "init", "-q", "--bare", str(bare))
        github_origin = "https://github.com/owner/repo.git"
        git(linked, "remote", "set-url", "origin", github_origin)
        adapter.capture_contract(self.repo_view, "run-1", controller.discover_repo(linked))
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        head = adapter.decision_head(decision)
        credential = "fixture" + "-credential"
        hook_log = Path(self.temp.name) / "push-hooks.log"
        descendant_log = Path(self.temp.name) / "push-descendant.log"
        hooks = self.repo / ".git" / "hooks"
        hook_source = """#!/usr/bin/env bash
printf '%s|%s|%s\n' "$(basename "$0")" "${GH_TOKEN:-}" "${LIFECYCLE_GITHUB_TOKEN:-}" >> "$HOOK_LOG"
(sleep 0.2; printf 'detached\n' >> "$DESCENDANT_LOG") &
"""
        for name in ("pre-push", "reference-transaction"):
            path = hooks / name
            path.write_text(hook_source)
            path.chmod(0o755)
        network_env = {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"url.{bare}.insteadOf",
            "GIT_CONFIG_VALUE_0": github_origin,
            "HOOK_LOG": str(hook_log),
            "DESCENDANT_LOG": str(descendant_log),
        }
        original_command = adapter.run_command
        with (
            mock.patch.dict(os.environ, network_env),
            mock.patch.object(
                adapter, "pinned_github_environment", return_value={"GH_TOKEN": credential}),
            mock.patch.object(
                adapter, "repository_identity", return_value=("owner/repo", "owner")),
            mock.patch.object(adapter, "run_command", wraps=original_command) as command_call,
        ):
            adapter.action_push(self.repo_view, state, decision)
            time.sleep(0.4)
        self.assertFalse(hook_log.exists())
        self.assertFalse(descendant_log.exists())
        push_call = next(
            call for call in command_call.call_args_list
            if call.args and call.args[0][:4] == [
                "git", "-c", "core.hooksPath=/dev/null", "push"]
        )
        self.assertEqual(push_call.kwargs["env"]["GH_TOKEN"], "")
        self.assertEqual(push_call.kwargs["env"]["LIFECYCLE_GITHUB_TOKEN"], credential)
        self.assertEqual(
            git(bare, "rev-parse", "refs/heads/feature/lifecycle").stdout.strip(), head)

        ordinary_env = os.environ.copy()
        ordinary_env.update(network_env)
        ordinary_env["GH_TOKEN"] = credential
        ordinary_env["LIFECYCLE_GITHUB_TOKEN"] = credential
        run(
            linked, "git", "push", github_origin, f"{head}:refs/heads/ordinary-hooks",
            env=ordinary_env,
        )
        time.sleep(0.4)
        self.assertTrue(any(
            line.startswith("pre-push|") for line in hook_log.read_text().splitlines()))
        self.assertTrue(descendant_log.is_file())

    def test_push_is_ordinary_and_open_pr_reuses_or_calls_canonical_stack(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        git(linked, "add", "owned/change.txt")
        git(linked, "commit", "-q", "-m", "feat(lifecycle): add adapter behavior",
            "-m", "Lifecycle ownership requires an exact canonical commit.")
        bare = Path(self.temp.name) / "origin.git"
        git(Path(self.temp.name), "init", "-q", "--bare", str(bare))
        github_origin = "https://github.com/owner/repo.git"
        git(linked, "remote", "set-url", "origin", github_origin)
        adapter.capture_contract(self.repo_view, "run-1", controller.discover_repo(linked))
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        original_command = adapter.run_command
        network_env = {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"url.{bare}.insteadOf",
            "GIT_CONFIG_VALUE_0": github_origin,
        }
        with (
            mock.patch.dict(os.environ, network_env),
            mock.patch.object(
                adapter, "pinned_github_environment", return_value={"GH_TOKEN": "test-token"}),
            mock.patch.object(
                adapter, "repository_identity", return_value=("owner/repo", "owner")),
            mock.patch.object(adapter, "run_command", wraps=original_command) as command_call,
        ):
            adapter.action_push(self.repo_view, state, decision)
        pushes = [call.args[0] for call in command_call.call_args_list
                  if call.args and call.args[0][:4] == [
                      "git", "-c", "core.hooksPath=/dev/null", "push"]]
        expected_head = adapter.decision_head(decision)
        self.assertEqual(pushes, [[
            "git", "-c", "core.hooksPath=/dev/null", "push", github_origin,
            f"{expected_head}:refs/heads/feature/lifecycle",
        ]])
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
            "author": {"login": "owner"},
            "repository": "owner/repo",
            "url": "https://example.invalid/pr/17",
        }
        with (
            mock.patch.object(
                adapter, "pinned_github_environment", return_value={"GH_TOKEN": "test-token"}),
            mock.patch.object(adapter, "query_exact_pr", side_effect=[None, pull_request]),
            mock.patch.object(adapter, "exact_remote_head", return_value=head),
            mock.patch.object(adapter, "run_command", return_value=completed_process()) as command,
        ):
            adapter.action_open_pr(self.repo_view, state, decision)
        self.assertEqual(command.call_count, 1)
        create_call = command.call_args
        self.assertEqual(
            create_call.args[0],
            [adapter.STACK, "pr", "feature/lifecycle", "main",
             "feat(lifecycle): add adapter behavior", "--no-push"],
        )
        self.assertEqual(create_call.args[1], linked.resolve())
        self.assertFalse(create_call.kwargs["check"])
        self.assertEqual(create_call.kwargs["env"]["GH_TOKEN"], "test-token")
        self.assertEqual(create_call.kwargs["env"]["LIFECYCLE_EXPECTED_ACTOR"], "owner")
        self.assertEqual(create_call.kwargs["env"]["LIFECYCLE_EXPECTED_REPOSITORY"], "owner/repo")
        self.assertEqual(create_call.kwargs["env"]["LIFECYCLE_EXPECTED_SHA"], head)
        self.assertEqual(
            create_call.kwargs["env"]["LIFECYCLE_EXPECTED_URL"], github_origin)
        self.assertEqual(
            create_call.kwargs["env"]["LIFECYCLE_EXPECTED_PUSH_URL"], github_origin)
        self.assertEqual(adapter.inspect_bound(self.repo_view, "run-1")["action"], "wait_ci")

        with (
            mock.patch.object(
                adapter, "pinned_github_environment", return_value={"GH_TOKEN": "test-token"}),
            mock.patch.object(adapter, "query_exact_pr", return_value=pull_request),
            mock.patch.object(adapter, "exact_remote_head", return_value=head),
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

    def test_pending_action_journal_reconciles_base_exception_before_next_action(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")

        def commit_then_interrupt(_repo, current_state, _decision):
            unit = controller.current_unit(current_state)["ready"]
            git(linked, "add", "owned/change.txt")
            git(linked, "commit", "-q", "-m", unit["subject"], "-m", unit["body"])
            raise KeyboardInterrupt

        with mock.patch.object(adapter, "resolve_autonomy", return_value=(True, "authorized")):
            with self.assertRaises(KeyboardInterrupt):
                adapter.execute_action(
                    self.repo_view, "run-1", decision, state, commit_then_interrupt)
        pending = adapter.load_action_journal(self.repo_view, "run-1")
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["audit_status"], "pending")

        reconciled = adapter.tick(namespace(run_id="run-1"), self.repo)
        self.assertEqual(reconciled["outcome"], "reconciled")
        self.assertEqual(reconciled["before"]["action"], "push")
        completed = adapter.load_action_journal(self.repo_view, "run-1")
        self.assertEqual(completed["result"], "success")
        self.assertEqual(completed["audit_status"], "complete")
        audit_path = adapter.adapter_root(self.repo_view.common_dir) / "adapter-audit.jsonl"
        before = audit_path.read_text()
        self.assertFalse(adapter.reconcile_action_journal(self.repo_view, "run-1"))
        self.assertEqual(audit_path.read_text(), before)

    def test_partial_stack_before_strict_tracking_demotes_and_halts(self):
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")

        def create_worktree_then_interrupt(_repo, current_state, _decision):
            trees = self.repo / ".trees"
            trees.mkdir()
            git(
                self.repo,
                "worktree", "add", "-q", "-b", current_state["intended_branch"],
                str(trees / "lifecycle"), current_state["base"]["sha"],
            )
            raise KeyboardInterrupt

        with mock.patch.object(adapter, "resolve_autonomy", return_value=(True, "authorized")):
            with self.assertRaises(KeyboardInterrupt):
                adapter.execute_action(
                    self.repo_view, "run-1", decision, state,
                    create_worktree_then_interrupt,
                )
        pending = adapter.load_action_journal(self.repo_view, "run-1")
        self.assertEqual(pending["status"], "pending")
        self.assertIsNone(adapter.load_stack_completion_receipt(self.repo_view, "run-1"))

        result = adapter.tick(namespace(run_id="run-1"), self.repo)
        self.assertEqual(result["outcome"], "blocked")
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], "partial_stack_creation")
        self.assertEqual(adapter.inspect_bound(self.repo_view, "run-1")["action"], "blocked")
        completed = adapter.load_action_journal(self.repo_view, "run-1")
        self.assertEqual(completed["result"], "failure")
        self.assertEqual(completed["reason_code"], "partial_stack_creation")
        self.assertEqual(completed["audit_status"], "complete")
        self.assertTrue(
            (self.repo_view.common_dir / "autonomy-demoted-auto_stack").is_file())

    def test_stack_command_success_without_receipt_demotes_and_halts(self):
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        action_env, gt_log = self.install_stack_tracking()
        with (
            mock.patch.dict(os.environ, action_env),
            mock.patch.object(adapter, "verify_contract"),
            mock.patch.object(adapter, "resolve_autonomy", return_value=(True, "authorized")),
            mock.patch.object(
                adapter, "write_stack_completion_receipt", side_effect=KeyboardInterrupt,
            ),
        ):
            with self.assertRaises(KeyboardInterrupt):
                adapter.execute_action(
                    self.repo_view, "run-1", decision, state, adapter.action_create_stack)
            result = adapter.tick(namespace(run_id="run-1"), self.repo)

        commands = gt_log.read_text().splitlines()
        self.assertIn("branch track feature/lifecycle --parent main", commands)
        self.assertIn("branch info feature/lifecycle", commands)
        self.assertTrue((self.repo / ".trees" / "lifecycle").is_dir())
        self.assertIsNone(adapter.load_stack_completion_receipt(self.repo_view, "run-1"))
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(result["reason_code"], "partial_stack_creation")
        self.assertEqual(adapter.inspect_bound(self.repo_view, "run-1")["action"], "blocked")
        self.assertTrue(
            (self.repo_view.common_dir / "autonomy-demoted-auto_stack").is_file())

    def test_stale_stack_receipt_from_older_attempt_cannot_reconcile_success(self):
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        journal = adapter.begin_action_journal(
            self.repo_view, "run-1", decision, "auto_stack",
        )
        trees = self.repo / ".trees"
        trees.mkdir()
        git(
            self.repo,
            "worktree", "add", "-q", "-b", state["intended_branch"],
            str(trees / "lifecycle"), state["base"]["sha"],
        )
        action_env, _ = self.install_stack_tracking()
        stale_attempt = "0" * 64
        self.assertNotEqual(journal["attempt_id"], stale_attempt)
        with mock.patch.dict(os.environ, action_env):
            facts = adapter.stack_completion_facts(self.repo_view, state)
            adapter.write_stack_completion_receipt(
                self.repo_view,
                state,
                {
                    "run_id": "run-1",
                    "attempt_id": stale_attempt,
                    "evidence_id": journal["evidence_id"],
                },
                facts,
            )
            with mock.patch.object(adapter, "verify_contract"):
                result = adapter.tick(namespace(run_id="run-1"), self.repo)

        receipt = adapter.load_stack_completion_receipt(self.repo_view, "run-1")
        self.assertEqual(receipt["attempt_id"], stale_attempt)
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(result["reason_code"], "partial_stack_creation")
        self.assertEqual(adapter.inspect_bound(self.repo_view, "run-1")["action"], "blocked")
        completed = adapter.load_action_journal(self.repo_view, "run-1")
        self.assertEqual(completed["result"], "failure")
        self.assertEqual(completed["reason_code"], "partial_stack_creation")

    def test_malformed_stack_receipt_cannot_advance_existing_worktree(self):
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        adapter.begin_action_journal(
            self.repo_view, "run-1", decision, "auto_stack",
        )
        trees = self.repo / ".trees"
        trees.mkdir()
        git(
            self.repo,
            "worktree", "add", "-q", "-b", state["intended_branch"],
            str(trees / "lifecycle"), state["base"]["sha"],
        )
        adapter.atomic_secure_json(
            adapter.stack_receipt_path(self.repo_view.common_dir, "run-1"),
            {},
        )

        result = adapter.tick(namespace(run_id="run-1"), self.repo)
        self.assertEqual(result["outcome"], "blocked")
        self.assertEqual(result["reason_code"], "partial_stack_creation")
        self.assertEqual(adapter.inspect_bound(self.repo_view, "run-1")["action"], "blocked")
        completed = adapter.load_action_journal(self.repo_view, "run-1")
        self.assertEqual(completed["result"], "failure")
        self.assertEqual(completed["reason_code"], "partial_stack_creation")

    def test_exact_stack_receipt_reconciles_idempotently_after_interruption(self):
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        action_env, _ = self.install_stack_tracking()
        with (
            mock.patch.dict(os.environ, action_env),
            mock.patch.object(adapter, "verify_contract"),
            mock.patch.object(adapter, "resolve_autonomy", return_value=(True, "authorized")),
            mock.patch.object(
                adapter, "complete_action_journal", side_effect=KeyboardInterrupt,
            ),
        ):
            with self.assertRaises(KeyboardInterrupt):
                adapter.execute_action(
                    self.repo_view, "run-1", decision, state, adapter.action_create_stack)

        pending = adapter.load_action_journal(self.repo_view, "run-1")
        self.assertEqual(pending["status"], "pending")
        receipt = adapter.load_stack_completion_receipt(self.repo_view, "run-1")
        self.assertEqual(receipt["attempt_id"], pending["attempt_id"])
        with (
            mock.patch.dict(os.environ, action_env),
            mock.patch.object(adapter, "verify_contract"),
        ):
            result = adapter.tick(namespace(run_id="run-1"), self.repo)
        self.assertEqual(result["outcome"], "reconciled")
        self.assertIn(
            adapter.inspect_bound(self.repo_view, "run-1")["action"],
            adapter.ACTION_SUCCESSORS["create_stack"],
        )
        completed = adapter.load_action_journal(self.repo_view, "run-1")
        self.assertEqual(completed["result"], "success")
        self.assertEqual(completed["audit_status"], "complete")
        self.assertFalse(
            (self.repo_view.common_dir / "autonomy-demoted-auto_stack").exists())
        self.assertFalse(adapter.reconcile_action_journal(self.repo_view, "run-1"))

    def test_success_audit_failure_blocks_advancement_until_next_tick_reconciles(self):
        linked = add_linked(self.repo)
        ready_run(self.repo, linked)
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")

        def commit_action(_repo, current_state, _decision):
            unit = controller.current_unit(current_state)["ready"]
            git(linked, "add", "owned/change.txt")
            git(linked, "commit", "-q", "-m", unit["subject"], "-m", unit["body"])

        with (
            mock.patch.object(adapter, "resolve_autonomy", return_value=(True, "authorized")),
            mock.patch.object(
                adapter, "append_adapter_audit", side_effect=[None, OSError("audit unavailable")]),
        ):
            with self.assertRaises(adapter.AdapterError) as raised:
                adapter.execute_action(
                    self.repo_view, "run-1", decision, state, commit_action)
        self.assertEqual(raised.exception.code, "action_audit_pending")
        pending = adapter.load_action_journal(self.repo_view, "run-1")
        self.assertEqual(pending["status"], "completed")
        self.assertEqual(pending["result"], "success")
        self.assertEqual(pending["audit_status"], "pending")

        reconciled = adapter.tick(namespace(run_id="run-1"), self.repo)
        self.assertEqual(reconciled["outcome"], "reconciled")
        self.assertEqual(adapter.load_action_journal(
            self.repo_view, "run-1")["audit_status"], "complete")

    def test_demotion_persists_before_best_effort_audit_failure(self):
        state = adapter.load_run_state(self.repo_view, "run-1")
        decision = adapter.inspect_bound(self.repo_view, "run-1")
        failing_action = mock.Mock(side_effect=adapter.AdapterError("secret detail", "action_failed"))
        with (
            mock.patch.object(adapter, "resolve_autonomy", return_value=(True, "authorized")),
            mock.patch.object(adapter, "append_adapter_audit", side_effect=[None, OSError("audit unavailable")]),
        ):
            result = adapter.execute_action(
                self.repo_view, "run-1", decision, state, failing_action)
        self.assertEqual(result["outcome"], "action_failed")
        self.assertTrue((self.repo_view.common_dir / "autonomy-demoted-auto_stack").is_file())
        pending = adapter.load_action_journal(self.repo_view, "run-1")
        self.assertEqual(pending["result"], "failure")
        self.assertEqual(pending["audit_status"], "pending")
        reconciled = adapter.tick(namespace(run_id="run-1"), self.repo)
        self.assertEqual(reconciled["outcome"], "reconciled")
        self.assertEqual(adapter.load_action_journal(
            self.repo_view, "run-1")["audit_status"], "complete")

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


class NetworkIdentityHardeningTests(unittest.TestCase):
    def test_contract_capture_rejects_missing_ambiguous_unrecognized_and_drifted_origins(self):
        cases = ("missing", "ambiguous", "unrecognized", "drifted")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as td:
                repo = init_repo(Path(td) / "repo")
                if case == "missing":
                    git(repo, "remote", "remove", "origin")
                elif case == "ambiguous":
                    git(repo, "remote", "set-url", "--add", "origin",
                        "https://github.com/owner/other.git")
                elif case == "unrecognized":
                    git(repo, "remote", "set-url", "origin", "git@github.com:owner/repo.git")
                else:
                    git(repo, "remote", "set-url", "--push", "origin",
                        "https://github.com/owner/other.git")
                view = controller.discover_repo(repo)
                with self.assertRaises(adapter.AdapterError) as raised:
                    adapter.capture_contract(view, f"run-{case}", view)
                self.assertIn(raised.exception.code, {
                    "origin_url_ambiguous", "origin_url_unrecognized", "origin_url_drift"})
                self.assertFalse(adapter.contract_path(view.common_dir, f"run-{case}").exists())

        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            git(repo, "remote", "set-url", "--push", "origin",
                "https://push-user@github.com/owner/repo.git")
            view = controller.discover_repo(repo)
            contract = adapter.capture_contract(view, "run-supported", view)
            self.assertEqual(contract["github_repository"], "owner/repo")
            self.assertEqual(contract["github_url"], "https://github.com/owner/repo.git")
            self.assertEqual(contract["origin"]["fetch"], [
                "https://user@github.com/owner/repo.git"])
            self.assertEqual(contract["origin"]["push"], [
                "https://push-user@github.com/owner/repo.git"])

    def test_start_rejects_invalid_origin_before_run_state_or_contract_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            git(repo, "remote", "remove", "origin")
            view = controller.discover_repo(repo)
            with self.assertRaises(adapter.AdapterError) as raised:
                start_run(repo)
            self.assertEqual(raised.exception.code, "origin_url_ambiguous")
            state_path, _, _ = controller.locations(view.common_dir, "run-1")
            self.assertFalse(state_path.exists())
            self.assertFalse(adapter.contract_path(view.common_dir, "run-1").exists())

    def test_pinned_token_is_selected_by_actor_and_verified_without_ambient_auth(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            view = controller.discover_repo(repo)
            contract = adapter.capture_contract(view, "run-token", view)
            responses = [
                completed_process(stdout="github_pat_safe_token\n"),
                completed_process(stdout="owner\n"),
            ]
            with mock.patch.object(adapter, "run_command", side_effect=responses) as command:
                env = adapter.pinned_github_environment(view, contract)
            self.assertEqual(env, {"GH_TOKEN": "github_pat_safe_token"})
            token_call, verify_call = command.call_args_list
            self.assertEqual(token_call.args[0], [
                "gh", "auth", "token", "--hostname", "github.com", "--user", "owner"])
            self.assertEqual(token_call.kwargs["env"]["GH_TOKEN"], "")
            self.assertEqual(verify_call.args[0], [
                "gh", "api", "--hostname", "github.com", "/user", "--jq", ".login"])
            self.assertEqual(verify_call.kwargs["env"]["GH_TOKEN"], "github_pat_safe_token")

            with mock.patch.object(adapter, "run_command", side_effect=[
                completed_process(stdout="github_pat_wrong_token\n"),
                completed_process(stdout="wrong-actor\n"),
            ]):
                with self.assertRaises(adapter.AdapterError) as raised:
                    adapter.pinned_github_environment(view, contract)
            self.assertEqual(raised.exception.code, "github_token_actor_mismatch")
            self.assertNotIn("github_pat_wrong_token", str(raised.exception))

    def test_create_pr_lifecycle_path_preserves_supplied_token_and_verifies_author(self):
        source = (ROOT / ".claude" / "scripts" / "pr-stack" / "create-pr.sh").read_text()
        supplied = source.index('if [ -z "${GH_TOKEN:-}" ]; then')
        fallback = source.index('GH_TOKEN="$(gh_token_for_remote)"', supplied)
        capture = source.index('["gh", *sys.argv[1:]]', fallback)
        self.assertLess(fallback, capture)
        self.assertIn('gh pr view "$PR_URL" --repo "$EXPECTED_REPOSITORY"', source)
        self.assertIn('value.get("author", {}).get("login") == sys.argv[1]', source)
        self.assertIn('GH_ARGS+=(--repo "$EXPECTED_REPOSITORY")', source)

    def test_create_pr_diagnostic_accepts_only_bounded_structured_redaction(self):
        raw = "authorization=github_pat_secret token=ghp_secret"
        structured = json.dumps({
            "lifecycle_pr_error": {"exit_status": 1, "reason": "authorization=[REDACTED]"}})
        proc = completed_process(returncode=1, stderr=f"{raw}\n{structured}\n")
        self.assertEqual(
            adapter.create_pr_diagnostic(proc), "authorization=[REDACTED]")
        unstructured = completed_process(returncode=1, stderr=raw)
        self.assertEqual(
            adapter.create_pr_diagnostic(unstructured),
            "canonical PR creation failed without a valid diagnostic",
        )
        self.assertNotIn("secret", adapter.create_pr_diagnostic(unstructured))
        forged_secret = completed_process(returncode=1, stderr=json.dumps({
            "lifecycle_pr_error": {"exit_status": 1, "reason": "ghp_secret"}}))
        self.assertEqual(
            adapter.create_pr_diagnostic(forged_secret),
            "canonical PR creation failed without a valid diagnostic",
        )


class CanonicalCommitWrapperTests(unittest.TestCase):
    def prepare_private_commit(self, root: Path):
        repo = init_repo(root / "repo")
        git(repo, "checkout", "-q", "-b", "feature/private")
        (repo / "owned.txt").write_text("approved content\n")
        index = root / "private.index"
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(index)
        run(repo, "git", "read-tree", "HEAD", env=env)
        run(repo, "git", "add", "-A", "--", "owned.txt", env=env)
        parent = git(repo, "rev-parse", "HEAD").stdout.strip()
        tree = run(repo, "git", "write-tree", env=env).stdout.strip()
        env.update({
            "LIFECYCLE_COMMIT_MODE": "private-v1",
            "LIFECYCLE_EXPECTED_PARENT": parent,
            "LIFECYCLE_EXPECTED_REF": "refs/heads/feature/private",
            "LIFECYCLE_EXPECTED_TREE": tree,
        })
        return repo, env, parent, tree

    def test_private_wrapper_disables_mutable_hooks_and_detached_descendants(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo, env, parent, tree = self.prepare_private_commit(root)
            hooks = repo / ".git" / "hooks"
            (hooks / "pre-commit").write_text("""#!/usr/bin/env bash
printf 'pre\n' > pre-hook-ran.txt
(sleep 30) &
printf '%s\n' "$!" > hook-child.pid
""")
            (hooks / "post-commit").write_text("""#!/usr/bin/env bash
printf 'post\n' > post-hook-ran.txt
""")
            (hooks / "pre-commit").chmod(0o755)
            (hooks / "post-commit").chmod(0o755)
            result = run(
                repo, str(adapter.COMMIT),
                "-m", "feat(test): private lifecycle commit",
                "-m", "Preserve exact approved tree without mutable repository hooks.",
                env=env, check=False,
            )
            child_file = repo / "hook-child.pid"
            if child_file.exists():
                os.kill(int(child_file.read_text().strip()), 9)
            self.assertEqual(result.returncode, 0, result.stderr)
            head = git(repo, "rev-parse", "HEAD").stdout.strip()
            self.assertEqual(
                git(repo, "rev-list", "--parents", "-n", "1", head).stdout.split()[1], parent)
            self.assertEqual(git(repo, "show", "-s", "--format=%T", head).stdout.strip(), tree)
            self.assertEqual(
                git(repo, "show", "--pretty=", "--name-only", head).stdout.split(), ["owned.txt"])
            self.assertFalse((repo / "pre-hook-ran.txt").exists())
            self.assertFalse((repo / "post-hook-ran.txt").exists())
            self.assertFalse(child_file.exists())

    def test_ordinary_wrapper_preserves_repository_hook_behavior(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            git(repo, "checkout", "-q", "-b", "feature/ordinary")
            (repo / "ordinary.txt").write_text("ordinary hook path\n")
            git(repo, "add", "ordinary.txt")
            hooks = repo / ".git" / "hooks"
            (hooks / "pre-commit").write_text(
                "#!/usr/bin/env bash\nprintf 'pre\n' > ordinary-pre.txt\n")
            (hooks / "post-commit").write_text(
                "#!/usr/bin/env bash\nprintf 'post\n' > ordinary-post.txt\n")
            (hooks / "pre-commit").chmod(0o755)
            (hooks / "post-commit").chmod(0o755)
            result = run(
                repo, str(adapter.COMMIT),
                "-m", "feat(test): ordinary commit",
                "-m", "Ordinary commits retain repository hook behavior.",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((repo / "ordinary-pre.txt").is_file())
            self.assertTrue((repo / "ordinary-post.txt").is_file())

    def test_intent_write_replaces_symlink_without_following_lifecycle_hook(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            git(repo, "checkout", "-q", "-b", "feature/intent")
            hook = repo / ".claude" / "hooks" / "lifecycle-hook.sh"
            hook.parent.mkdir(parents=True)
            hook.write_text("protected lifecycle hook\n")
            intent = repo / ".claude-atomic-intent"
            intent.symlink_to(hook)
            git(repo, "add", ".claude/hooks/lifecycle-hook.sh")
            git(repo, "add", "-f", ".claude-atomic-intent")
            git(repo, "commit", "-q", "-m", "chore: initialize intent symlink fixture")
            (repo / "README.md").write_text("intent regression\n")
            git(repo, "add", "README.md")
            result = run(
                repo, str(adapter.COMMIT),
                "-m", "fix(test): write intent safely",
                "-m", "Intent metadata must never follow a lifecycle hook symlink.",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(hook.read_text(), "protected lifecycle hook\n")
            self.assertFalse(intent.is_symlink())
            self.assertTrue(intent.is_file())
            self.assertIn("LAST_COMMIT_HASH=", intent.read_text())


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

    def test_audit_repairs_incomplete_tail_but_rejects_malformed_complete_records(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            view = controller.discover_repo(repo)
            adapter.append_adapter_audit(
                view.common_dir, "run-1", "action", "attempt", action="commit")
            path = adapter.adapter_root(view.common_dir) / "adapter-audit.jsonl"
            with path.open("ab") as stream:
                stream.write(b'{"event_id":"incomplete"')
            adapter.append_adapter_audit(
                view.common_dir, "run-1", "action", "success", action="commit")
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([record["result"] for record in records], ["attempt", "success"])

            with path.open("ab") as stream:
                stream.write(b'{"event_id":bad}\n')
            with self.assertRaises(adapter.AdapterError) as raised:
                adapter.append_adapter_audit(
                    view.common_dir, "run-1", "action", "failure", action="commit")
            self.assertEqual(raised.exception.code, "audit_file_invalid")

    def test_audit_refuses_symlinked_parent_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            view = controller.discover_repo(repo)
            root = adapter.adapter_root(view.common_dir)
            outside = Path(td) / "outside-state"
            outside.mkdir()
            root.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(OSError):
                adapter.append_adapter_audit(
                    view.common_dir, "run-1", "action", "attempt", action="commit")
            self.assertEqual(list(outside.iterdir()), [])

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
        self.credential_patch = mock.patch.object(
            adapter, "pinned_github_environment", return_value={"GH_TOKEN": "test-token"})
        self.credential_patch.start()

    def tearDown(self):
        self.credential_patch.stop()
        self.temp.cleanup()

    def pull_request(self, **updates):
        value = {
            "number": 9, "state": "OPEN", "isDraft": False,
            "headRefOid": self.head, "headRefName": "feature/lifecycle",
            "baseRefName": "main", "headRepositoryOwner": {"login": "owner"},
            "author": {"login": "owner"}, "repository": "owner/repo", "url": "https://example.invalid/pr/9",
            "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN",
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

    def test_required_check_exit_codes_and_partial_readiness_are_strict(self):
        cases = (
            (1, [{"name": "build", "bucket": "fail"}], "failed"),
            (1, [{"name": "build", "bucket": "pass"}], "unknown"),
            (8, [{"name": "build", "bucket": "pending"}], "pending"),
            (8, [{"name": "build", "bucket": "fail"}], "unknown"),
            (0, [{"name": "build", "bucket": "pass"}], "passing"),
        )
        for returncode, checks, expected in cases:
            with self.subTest(returncode=returncode, expected=expected):
                with mock.patch.object(
                    adapter, "run_command",
                    return_value=completed_process(returncode=returncode, stdout=json.dumps(checks)),
                ):
                    contract = adapter.load_contract(self.repo_view, "run-1")
                    self.assertEqual(adapter.required_checks(
                        self.repo_view, 9, contract, {"GH_TOKEN": "test-token"})[0], expected)

        checks = [{"name": "build", "bucket": "pass"}]
        with (
            mock.patch.object(
                adapter, "query_exact_pr",
                return_value=self.pull_request(mergeStateStatus=None),
            ),
            mock.patch.object(
                adapter, "run_command", return_value=completed_process(stdout=json.dumps(checks)),
            ),
        ):
            result = adapter.reconcile_ci(self.repo_view, "run-1", self.head)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["outcome"], "pending")
        state = adapter.load_run_state(self.repo_view, "run-1")
        ci_facts = [fact for fact in state["facts"] if fact["kind"] == "ci"]
        self.assertEqual(ci_facts[-1]["status"], "unknown")

    def test_ci_reconciliation_is_exact_head_and_records_only_strict_result(self):
        pull_request = {
            "number": 9,
            "state": "OPEN",
            "isDraft": False,
            "headRefOid": self.head,
            "headRefName": "feature/lifecycle",
            "baseRefName": "main",
            "headRepositoryOwner": {"login": "owner"},
            "author": {"login": "owner"},
            "repository": "owner/repo",
            "url": "https://example.invalid/pr/9",
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
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
        check_args = command.call_args.args[0]
        self.assertIn("--required", check_args)
        self.assertIn("--repo", check_args)
        self.assertEqual(check_args[check_args.index("--repo") + 1], "owner/repo")

        with mock.patch.object(adapter, "query_exact_pr") as query:
            stale = adapter.reconcile_ci(self.repo_view, "run-1", "0" * 40)
        self.assertEqual(stale["outcome"], "stale")
        query.assert_not_called()

    def test_pr_identity_rejects_base_owner_and_ignores_other_heads(self):
        state = adapter.load_run_state(self.repo_view, "run-1")
        for updates in (
            {"baseRefName": "wrong"},
            {"headRepositoryOwner": {"login": "fork"}},
            {"author": {"login": "wrong-actor"}},
        ):
            proc = completed_process(stdout=json.dumps([self.pull_request(**updates)]))
            with self.subTest(updates=updates):
                with self.assertRaises(adapter.AdapterError) as raised:
                    adapter.parse_prs(proc, state, self.head, "owner/repo", "owner", "owner")
                self.assertEqual(raised.exception.code, "pr_identity_mismatch")
        other = completed_process(stdout=json.dumps([
            self.pull_request(headRefOid="0" * len(self.head))]))
        self.assertEqual(
            adapter.parse_prs(other, state, self.head, "owner/repo", "owner", "owner"), [])

    def test_open_pr_requires_explicit_non_draft_evidence(self):
        self.assertEqual(adapter.pr_status(self.pull_request(isDraft=False)), "open")
        self.assertEqual(adapter.pr_status(self.pull_request(isDraft=True)), "draft")
        for value in (self.pull_request(isDraft=None), self.pull_request(isDraft="false")):
            with self.subTest(value=value["isDraft"]):
                with self.assertRaises(adapter.AdapterError) as raised:
                    adapter.pr_status(value)
                self.assertEqual(raised.exception.code, "pr_data_malformed")

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
        _, _, execution_lock, ready = adapter.watcher_paths(
            self.repo_view.common_dir, "run-1", self.head)
        controller.atomic_json(ready, {
            "schema_version": adapter.ADAPTER_SCHEMA_VERSION,
            "run_id": "run-1", "sha": self.head, "status": "ready", "pid": os.getpid(),
        })
        lease_fd = adapter.secure_file(execution_lock, os.O_RDWR)
        try:
            import fcntl
            fcntl.flock(lease_fd, fcntl.LOCK_EX)
            with mock.patch.object(subprocess, "Popen") as popen:
                duplicate = adapter.spawn_watcher(self.repo_view, "run-1", self.head)
            self.assertTrue(duplicate["duplicate"])
            popen.assert_not_called()
        finally:
            fcntl.flock(lease_fd, fcntl.LOCK_UN)
            os.close(lease_fd)

        marker.unlink()
        ready.unlink()
        fake = mock.Mock(pid=424242)
        with (
            mock.patch.object(subprocess, "Popen", return_value=fake) as popen,
            mock.patch.object(adapter, "child_ready", return_value=True),
            mock.patch.object(adapter, "watcher_active", return_value=True),
        ):
            started = adapter.spawn_watcher(self.repo_view, "run-1", self.head)
        self.assertTrue(started["started"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertIs(popen.call_args.kwargs["stdout"], subprocess.DEVNULL)
    def test_dead_stale_and_malformed_watcher_markers_restart_under_spawn_lock(self):
        marker, _, _, ready = adapter.watcher_paths(
            self.repo_view.common_dir, "run-1", self.head)
        marker.parent.mkdir(parents=True, exist_ok=True)
        stale = (adapter.dt.datetime.now(adapter.dt.timezone.utc) - adapter.dt.timedelta(hours=1))
        cases = (
            {
                "schema_version": adapter.ADAPTER_SCHEMA_VERSION, "run_id": "run-1",
                "sha": self.head, "status": "running", "pid": 99999999,
                "updated_at": adapter.now(),
            },
            {
                "schema_version": adapter.ADAPTER_SCHEMA_VERSION, "run_id": "run-1",
                "sha": self.head, "status": "running", "pid": os.getpid(),
                "updated_at": stale.isoformat().replace("+00:00", "Z"),
            },
            {"schema_version": 999, "run_id": "wrong"},
        )
        for value in cases:
            with self.subTest(value=value):
                controller.atomic_json(marker, value)
                ready.unlink(missing_ok=True)
                self.assertFalse(adapter.watcher_active(
                    self.repo_view, "run-1", self.head))
                original_active = adapter.watcher_active
                observations = 0

                def active(repo, run_id, sha):
                    nonlocal observations
                    observations += 1
                    return original_active(repo, run_id, sha) if observations == 1 else True

                fake = mock.Mock(pid=424242)
                with (
                    mock.patch.object(subprocess, "Popen", return_value=fake) as popen,
                    mock.patch.object(adapter, "child_ready", return_value=True),
                    mock.patch.object(adapter, "watcher_active", side_effect=active),
                ):
                    result = adapter.spawn_watcher(self.repo_view, "run-1", self.head)
                self.assertTrue(result["started"])
                popen.assert_called_once()


class WorktreeHookContainmentTests(unittest.TestCase):
    def invoke(self, repo: Path, name: str):
        return subprocess.run(
            [str(ROOT / ".claude" / "hooks" / "worktree-create.sh")],
            cwd=str(repo),
            input=json.dumps({"cwd": str(repo), "name": name}),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_symlinked_trees_root_is_refused_without_touching_target(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = init_repo(root / "repo")
            outside = root / "outside"
            outside.mkdir()
            (repo / ".trees").symlink_to(outside, target_is_directory=True)
            result = self.invoke(repo, "feature/escape")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("non-symlink", result.stderr)
            self.assertEqual(list(outside.iterdir()), [])

    def test_existing_worktree_outside_contained_root_is_not_reused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = init_repo(root / "repo")
            (repo / ".trees").mkdir()
            outside = root / "outside-worktree"
            git(repo, "worktree", "add", "-q", "-b", "feature/escape", str(outside))
            result = self.invoke(repo, "feature/escape")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("outside", result.stderr)
            self.assertNotEqual(result.stdout.strip(), str(outside))


class ProcessIsolationTests(unittest.TestCase):
    def assert_pid_exits(self, pid: int) -> None:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and adapter.process_alive(pid):
            time.sleep(0.02)
        self.assertFalse(adapter.process_alive(pid), f"descendant {pid} survived process cleanup")

    def test_timeout_and_success_both_reap_lingering_process_groups(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for parent_delay, timeout, should_timeout in ((30, 0.2, True), (0, 2, False)):
                pid_file = root / f"child-{parent_delay}.pid"
                script = """
import pathlib, signal, subprocess, sys, time
child = subprocess.Popen(
    [sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"],
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
pathlib.Path(sys.argv[1]).write_text(str(child.pid))
time.sleep(float(sys.argv[2]))
"""
                if should_timeout:
                    with self.assertRaises(adapter.AdapterError) as raised:
                        adapter.bounded_process(
                            [sys.executable, "-c", script, str(pid_file), str(parent_delay)],
                            root,
                            timeout=timeout,
                        )
                    self.assertEqual(raised.exception.code, "action_command_timeout")
                else:
                    result = adapter.bounded_process(
                        [sys.executable, "-c", script, str(pid_file), str(parent_delay)],
                        root,
                        timeout=timeout,
                    )
                    self.assertEqual(result.returncode, 0)
                self.assertTrue(pid_file.is_file())
                self.assert_pid_exits(int(pid_file.read_text()))

    def test_base_exception_reaps_signal_ignoring_descendant(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pid_file = root / "base-exception-child.pid"
            script = """
import pathlib, signal, subprocess, sys, time
child = subprocess.Popen(
    [sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"],
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
pathlib.Path(sys.argv[1]).write_text(str(child.pid))
time.sleep(30)
"""

            def interrupted(_proc, *args, **kwargs):
                deadline = time.monotonic() + 2
                while not pid_file.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                raise KeyboardInterrupt

            with mock.patch.object(subprocess.Popen, "communicate", interrupted):
                with self.assertRaises(KeyboardInterrupt):
                    adapter.bounded_process(
                        [sys.executable, "-c", script, str(pid_file)], root, timeout=5)
            self.assertTrue(pid_file.is_file())
            self.assert_pid_exits(int(pid_file.read_text()))

    def test_signal_between_spawn_and_handle_assignment_reaps_process_tree(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pid_file = root / "spawn-window-pids"
            script = r"""
import os, pathlib, signal, subprocess, sys, time
for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
    signal.signal(signum, signal.SIG_IGN)
grandchild_source = "import signal,time; [signal.signal(s, signal.SIG_IGN) for s in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)]; time.sleep(30)"
grandchild = subprocess.Popen(
    [sys.executable, "-c", grandchild_source],
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
blocked = signal.pthread_sigmask(signal.SIG_BLOCK, set())
cleanup_blocked = int(any(signum in blocked for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)))
pathlib.Path(sys.argv[1]).write_text(f"{os.getpid()} {grandchild.pid} {cleanup_blocked}")
time.sleep(30)
"""
            original_popen = subprocess.Popen
            previous_handlers = {
                signum: signal.getsignal(signum)
                for signum in adapter.PROCESS_CLEANUP_SIGNALS
            }

            def signal_before_return(*args, **kwargs):
                self.assertNotEqual(
                    signal.getsignal(signal.SIGHUP), previous_handlers[signal.SIGHUP],
                )
                spawned = original_popen(*args, **kwargs)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if pid_file.is_file() and len(pid_file.read_text().split()) == 3:
                        break
                    if spawned.poll() is not None:
                        break
                    time.sleep(0.01)
                else:
                    os.killpg(spawned.pid, signal.SIGKILL)
                    spawned.wait(timeout=3)
                    raise AssertionError("spawned process tree did not become ready")
                os.kill(os.getpid(), signal.SIGHUP)
                os.kill(os.getpid(), signal.SIGTERM)
                return spawned

            with mock.patch.object(subprocess, "Popen", side_effect=signal_before_return):
                with self.assertRaises(SystemExit) as raised:
                    adapter.bounded_process(
                        [sys.executable, "-c", script, str(pid_file)],
                        root,
                        timeout=30,
                    )
            self.assertEqual(raised.exception.code, 128 + signal.SIGHUP)
            values = [int(item) for item in pid_file.read_text().split()]
            self.assertEqual(len(values), 3)
            pids, child_masked = values[:2], values[2]
            self.assertEqual(child_masked, 0)
            for pid in pids:
                self.assert_pid_exits(pid)
            for signum, handler in previous_handlers.items():
                self.assertEqual(signal.getsignal(signum), handler)

            with mock.patch.object(
                subprocess, "Popen", side_effect=OSError("simulated spawn failure"),
            ):
                with self.assertRaises(adapter.AdapterError) as failed:
                    adapter.bounded_process([sys.executable, "-c", "pass"], root)
            self.assertEqual(failed.exception.code, "action_command_start_failed")
            for signum, handler in previous_handlers.items():
                self.assertEqual(signal.getsignal(signum), handler)

    def test_repeated_mixed_signals_cannot_interrupt_process_group_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pid_file = root / "signal-cleanup-pids"
            harness = r'''
import pathlib, sys
sys.path.insert(0, sys.argv[1])
import lifecycle_adapter as adapter
child_source = r"""
import os, pathlib, signal, subprocess, sys, time
for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
    signal.signal(signum, signal.SIG_IGN)
grandchild_source = "import signal,time; [signal.signal(s, signal.SIG_IGN) for s in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)]; time.sleep(30)"
grandchild = subprocess.Popen(
    [sys.executable, "-c", grandchild_source],
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)
pathlib.Path(sys.argv[1]).write_text(f"{os.getpid()} {grandchild.pid}")
time.sleep(30)
"""
adapter.bounded_process(
    [sys.executable, "-c", child_source, sys.argv[2]],
    pathlib.Path(sys.argv[3]),
    timeout=30,
)
'''
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    harness,
                    str(ROOT / "scripts" / "ai"),
                    str(pid_file),
                    str(root),
                ],
                cwd=str(root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                close_fds=True,
            )
            pids = []
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if pid_file.is_file():
                        parts = pid_file.read_text().split()
                        if len(parts) == 2:
                            pids = [int(item) for item in parts]
                            break
                    if proc.poll() is not None:
                        break
                    time.sleep(0.01)
                self.assertEqual(len(pids), 2, proc.stderr.read() if proc.poll() is not None else "")
                time.sleep(0.05)
                os.kill(proc.pid, signal.SIGHUP)
                time.sleep(0.05)
                mixed = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
                for index in range(60):
                    if proc.poll() is not None:
                        break
                    try:
                        os.kill(proc.pid, mixed[index % len(mixed)])
                    except ProcessLookupError:
                        break
                    time.sleep(0.005)
                stdout, stderr = proc.communicate(timeout=8)
                self.assertEqual(proc.returncode, 128 + signal.SIGHUP, stdout + stderr)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=3)
            for pid in pids:
                self.assert_pid_exits(pid)


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
            self.assertEqual(allowed["lifecycle_hook"]["binding"], "bound")

            deferred = {
                "outcome": "approval_required", "reason_code": "action_deferred",
                "after": {"action": "merge_eligible", "reason": "deferred",
                          "evidence": {"git": {"head_sha": head}}},
            }
            with mock.patch.object(adapter, "tick", return_value=deferred):
                first = adapter.hook_stop(view, "session-1")
                second = adapter.hook_stop(view, "session-1")
            self.assertEqual(first["decision"], "block")
            self.assertEqual(second["decision"], "block")
            self.assertEqual(first["lifecycle_hook"]["binding"], "bound")
            notices = list((adapter.adapter_root(view.common_dir) / "stop-notices").glob("*.json"))
            self.assertEqual(len(notices), 0)

    @staticmethod
    def awaiting(head: str, declared: str, *, clean: bool = True) -> dict:
        return {
            "outcome": "idle",
            "after": {
                "action": "awaiting_work",
                "reason": "current work unit is not semantically ready",
                "evidence": {"git": {
                    "head_sha": head, "clean": clean,
                    "base": {"branch": "main", "declared_sha": declared, "current_sha": declared},
                }},
            },
        }

    def test_stop_allows_a_bound_run_that_authored_nothing(self):
        # hook_stop allows only action == "done", which comes solely from
        # lifecycle.halt_run -- and the adapter CLI exposes no halt. So binding a run and
        # then doing read-only work used to block Stop with `release` as the only exit.
        # A clean tree sitting on the declared base has nothing to commit, push, or lose.
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            start_run(repo)
            view = controller.discover_repo(repo)
            head = git(repo, "rev-parse", "HEAD").stdout.strip()
            with mock.patch.object(adapter, "tick", return_value=self.awaiting(head, head)):
                allowed = adapter.hook_stop(view, "session-1")
            self.assertNotIn("decision", allowed)
            self.assertEqual(allowed["lifecycle_hook"]["binding"], "bound")

    def test_stop_still_blocks_awaiting_work_that_hides_an_unpushed_commit(self):
        # phase_local returns awaiting_work as soon as a new unit opens, short-circuiting
        # the remote phases -- so a run that committed unit 1 and started unit 2 reports
        # awaiting_work with commits still unpushed. HEAD must equal the run's declared
        # base, not merely the unit base, or the allow would leak exactly that work.
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            start_run(repo)
            view = controller.discover_repo(repo)
            declared = git(repo, "rev-parse", "HEAD").stdout.strip()
            advanced = "0" * 40
            with mock.patch.object(adapter, "tick", return_value=self.awaiting(advanced, declared)):
                blocked = adapter.hook_stop(view, "session-1")
            self.assertEqual(blocked["decision"], "block")

    def test_stop_still_blocks_awaiting_work_with_a_dirty_tree(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td) / "repo")
            start_run(repo)
            view = controller.discover_repo(repo)
            head = git(repo, "rev-parse", "HEAD").stdout.strip()
            value = self.awaiting(head, head, clean=False)
            with mock.patch.object(adapter, "tick", return_value=value):
                blocked = adapter.hook_stop(view, "session-1")
            self.assertEqual(blocked["decision"], "block")

    def test_unauthored_run_rejects_other_actions_and_malformed_evidence(self):
        head = "a" * 40
        good = self.awaiting(head, head)["after"]
        self.assertTrue(adapter.unauthored_run(good))
        for mutate in (
            lambda d: d.update(action="editing"),
            lambda d: d.update(evidence={}),
            lambda d: d.update(evidence={"git": "not-a-dict"}),
            lambda d: d["evidence"]["git"].update(base=None),
            lambda d: d["evidence"]["git"].update(base={}),
            lambda d: d["evidence"]["git"]["base"].update(declared_sha=None),
            lambda d: d["evidence"]["git"].pop("clean"),
        ):
            value = copy.deepcopy(good)
            mutate(value)
            self.assertFalse(adapter.unauthored_run(value), value)


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
        dotfiles = home / ".dotfiles"
        adapter_path = dotfiles / "scripts" / "ai" / "lifecycle_adapter.py"
        adapter_path.parent.mkdir(parents=True)
        git(dotfiles, "init", "-q", "-b", "main")
        git(dotfiles, "config", "user.email", "bridge-test@example.com")
        git(dotfiles, "config", "user.name", "Bridge Test")
        git(dotfiles, "add", ".claude/hooks/lifecycle-hook.sh")
        git(dotfiles, "commit", "-q", "-m", "test: track bridge")
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
            git(adapter_path.parents[2], "add", "scripts/ai/lifecycle_adapter.py")
            crashed = self.invoke(repo, hook, "Stop", env, payload)
            self.assertEqual(json.loads(crashed.stdout)["decision"], "block")
            (repo / ".claude-atomic.yaml").write_text("lifecycle: [broken\n")
            corrupt = self.invoke(repo, hook, "PreToolUse", env, payload)
            self.assertEqual(json.loads(corrupt.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
            (repo / ".claude-atomic.yaml").write_text(lifecycle_config())
            malformed = self.invoke(repo, hook, "PreToolUse", env, "{bad")
            self.assertEqual(json.loads(malformed.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
            malformed_outside = self.invoke(Path(td), hook, "PreToolUse", env, "{bad")
            self.assertEqual(
                json.loads(malformed_outside.stdout)["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )

    def test_forged_wrong_shaped_and_empty_adapter_envelopes_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            repo, hook, adapter_path, env, payload = self.fixture(Path(td), lifecycle_config())
            dotfiles = adapter_path.parents[2]
            values = (
                "",
                json.dumps({
                    "lifecycle_hook": {
                        "schema_version": 1, "processed": True,
                        "event": "PreToolUse", "binding": "bound",
                    }
                }),
                json.dumps({
                    "lifecycle_hook": {
                        "schema_version": 1, "processed": True,
                        "event": "Stop", "binding": "bound", "run_id": "run-1",
                    }
                }),
                json.dumps({
                    "lifecycle_hook": {
                        "schema_version": 1, "processed": True,
                        "event": "PreToolUse", "binding": "bound", "run_id": "run-1",
                    },
                    "hookSpecificOutput": {"hookEventName": "PreToolUse"},
                }),
                json.dumps({
                    "lifecycle_hook": {
                        "schema_version": 1, "processed": True,
                        "event": "PreToolUse", "binding": "bound", "run_id": "run-1",
                    },
                    "unexpected": True,
                }),
            )
            for output in values:
                with self.subTest(output=output):
                    adapter_path.write_text(
                        "import sys\nsys.stdout.write(" + repr(output) + ")\n")
                    git(dotfiles, "add", "scripts/ai/lifecycle_adapter.py")
                    result = self.invoke(repo, hook, "PreToolUse", env, payload)
                    parsed = json.loads(result.stdout)
                    self.assertEqual(parsed["hookSpecificOutput"]["permissionDecision"], "deny")

            forged_unbound = {
                "lifecycle_hook": {
                    "schema_version": 1, "processed": True,
                    "event": "Stop", "binding": "unbound",
                },
                "reason": "forged silent fallback",
            }
            adapter_path.write_text(
                "import json\nprint(json.dumps(" + repr(forged_unbound) + "))\n")
            git(dotfiles, "add", "scripts/ai/lifecycle_adapter.py")
            stopped = self.invoke(repo, hook, "Stop", env, payload)
            self.assertEqual(json.loads(stopped.stdout)["decision"], "block")

    def test_disabled_and_explicit_unbound_stop_emit_the_unbound_envelope(self):
        # The unbound Stop envelope must reach stdout. stop.sh resolves
        # "unbound, defer to the legacy gate" from the envelope alone, so a
        # silent fallback here is indistinguishable from a broken bridge and
        # makes the dispatcher fail closed on every unbound session.
        with tempfile.TemporaryDirectory() as td:
            repo, hook, adapter_path, env, payload = self.fixture(
                Path(td), lifecycle_config(enabled=False))
            disabled = self.invoke(repo, hook, "PreToolUse", env, payload)
            self.assertEqual(json.loads(disabled.stdout)["lifecycle_hook"]["binding"], "unbound")
            (repo / ".claude-atomic.yaml").write_text(lifecycle_config())
            adapter_path.write_text(
                'import json\nprint(json.dumps({"lifecycle_hook":{"schema_version":1,"processed":True,"event":"Stop","binding":"unbound"}}))\n'
            )
            git(adapter_path.parents[2], "add", "scripts/ai/lifecycle_adapter.py")
            unbound = self.invoke(repo, hook, "Stop", env, payload)
            self.assertEqual(
                json.loads(unbound.stdout),
                {"lifecycle_hook": {
                    "schema_version": 1, "processed": True,
                    "event": "Stop", "binding": "unbound",
                }},
            )


class HookDispatcherAndSettingsTests(unittest.TestCase):
    def dispatcher_fixture(self, root: Path):
        hooks = root / "hooks"
        hooks.mkdir()
        shutil.copy2(ROOT / ".claude" / "hooks" / "stop.sh", hooks / "stop.sh")
        shutil.copy2(ROOT / ".claude" / "hooks" / "lifecycle-envelope.py", hooks / "lifecycle-envelope.py")
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

    def run_stop(self, root: Path, session_id: str | None = None, **values):
        script, bin_dir = self.dispatcher_fixture(root)
        env = os.environ.copy()
        env.update({key: str(value) for key, value in values.items()})
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        for key in ("TASK_LOG", "LIFECYCLE_LOG", "GIT_LOG"):
            env.setdefault(key, str(root / key.lower()))
        # A distinct session id per call keeps stop.sh's loop-breaker counter
        # (/tmp/.claude-lifecycle-stop-<session>) isolated. Sharing one id would let
        # blocks accumulate across tests until the third asserted block degrades to an
        # allow instead -- an order-dependent failure that only appears on reruns.
        session_id = session_id or f"test-stop-{uuid.uuid4().hex}"
        payload = json.dumps({
            "session_id": session_id,
            "cwd": str(root),
            "stop_hook_active": False,
        })
        self.addCleanup(
            lambda: Path(f"/tmp/.claude-lifecycle-stop-{session_id}").unlink(missing_ok=True))
        return run(root, str(script), env=env, check=False, stdin=payload), env

    def test_stop_is_first_block_wins_and_bound_lifecycle_supersedes_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            task_block = json.dumps({"decision": "block", "reason": "task first"})
            proc, env = self.run_stop(
                root,
                TASK_OUT=task_block,
                LIFECYCLE_OUT=json.dumps(
                    {"lifecycle_hook": {"schema_version": 1, "processed": True, "event": "Stop", "binding": "bound", "run_id": "run-1"},
                     "decision": "block", "reason": "lifecycle"}
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
                "lifecycle_hook": {"schema_version": 1, "processed": True, "event": "Stop", "binding": "bound", "run_id": "run-1"},
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
            legacy = {"decision": "block", "reason": "must not run"}
            proc, env = self.run_stop(
                root,
                TASK_OUT="",
                LIFECYCLE_OUT="",
                GIT_OUT=json.dumps(legacy),
            )
            self.assertIn("invalid", json.loads(proc.stdout)["reason"].lower())
            self.assertFalse(Path(env["GIT_LOG"]).exists())

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            legacy = {"decision": "block", "reason": "explicit unbound fallback"}
            unbound = {"lifecycle_hook": {
                "schema_version": 1, "processed": True, "event": "Stop", "binding": "unbound"}}
            proc, env = self.run_stop(
                root, TASK_OUT="", LIFECYCLE_OUT=json.dumps(unbound),
                GIT_OUT=json.dumps(legacy))
            self.assertEqual(json.loads(proc.stdout), legacy)
            self.assertTrue(Path(env["GIT_LOG"]).exists())

    def test_stop_dispatcher_rejects_forged_bound_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            forged = json.dumps({
                "lifecycle_hook": {
                    "schema_version": 1, "processed": True,
                    "event": "Stop", "binding": "bound",
                }
            })
            proc, env = self.run_stop(
                root, TASK_OUT="", LIFECYCLE_OUT=forged,
                GIT_OUT=json.dumps({"decision": "block", "reason": "legacy"}),
            )
            self.assertEqual(json.loads(proc.stdout)["decision"], "block")
            self.assertIn("invalid", json.loads(proc.stdout)["reason"].lower())
            self.assertFalse(Path(env["GIT_LOG"]).exists())

    def test_stop_lifecycle_block_degrades_after_two_denies(self):
        # The lifecycle branch returns before git-pipeline-gate.sh, so it inherits
        # neither that gate's stop_hook_active short-circuit nor its degradation. Without
        # its own breaker a lifecycle block repeats every turn until the client's block
        # cap -- the loop observed in sessions 6e8af5a5 and 8232f66a.
        forged = json.dumps({
            "lifecycle_hook": {
                "schema_version": 1, "processed": True,
                "event": "Stop", "binding": "bound",
            }
        })
        session_id = f"degrade-{uuid.uuid4().hex}"
        self.addCleanup(
            lambda: Path(f"/tmp/.claude-lifecycle-stop-{session_id}").unlink(missing_ok=True))

        decisions = []
        for _ in range(4):
            with tempfile.TemporaryDirectory() as td:
                proc, _env = self.run_stop(
                    Path(td), session_id=session_id, TASK_OUT="", LIFECYCLE_OUT=forged,
                    GIT_OUT=json.dumps({"decision": "block", "reason": "legacy"}),
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                stdout = proc.stdout.strip()
                decisions.append(json.loads(stdout)["decision"] if stdout else "allow")

        self.assertEqual(decisions, ["block", "block", "allow", "allow"])

    def test_stop_lifecycle_degradation_is_scoped_per_session(self):
        # A per-reason counter keyed on one shared session would let unrelated sessions
        # consume each other's budget and degrade a first-ever block into an allow.
        forged = json.dumps({
            "lifecycle_hook": {
                "schema_version": 1, "processed": True,
                "event": "Stop", "binding": "bound",
            }
        })
        exhausted = f"exhausted-{uuid.uuid4().hex}"
        self.addCleanup(
            lambda: Path(f"/tmp/.claude-lifecycle-stop-{exhausted}").unlink(missing_ok=True))

        for _ in range(3):
            with tempfile.TemporaryDirectory() as td:
                self.run_stop(
                    Path(td), session_id=exhausted, TASK_OUT="", LIFECYCLE_OUT=forged,
                    GIT_OUT=json.dumps({"decision": "block", "reason": "legacy"}))

        with tempfile.TemporaryDirectory() as td:
            proc, _env = self.run_stop(
                Path(td), TASK_OUT="", LIFECYCLE_OUT=forged,
                GIT_OUT=json.dumps({"decision": "block", "reason": "legacy"}))
            self.assertEqual(json.loads(proc.stdout)["decision"], "block")

    def test_stop_dispatcher_blocks_when_lifecycle_bridge_is_missing(self):
        # A payload without session_id falls into stop.sh's shared "nosession" bucket
        # (/tmp/.claude-lifecycle-stop-nosession), which outlives the process and is
        # shared with every other sessionless invocation. Two prior blocks anywhere on
        # the machine would degrade this one into an allow. Real Stop payloads always
        # carry a session_id, so send one and scope the counter to this test.
        session_id = f"missing-bridge-{uuid.uuid4().hex}"
        self.addCleanup(
            lambda: Path(f"/tmp/.claude-lifecycle-stop-{session_id}").unlink(missing_ok=True))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script, bin_dir = self.dispatcher_fixture(root)
            (script.parent / "lifecycle-hook.sh").unlink()
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"
            for key in ("TASK_LOG", "LIFECYCLE_LOG", "GIT_LOG"):
                env[key] = str(root / key.lower())
            proc = subprocess.run(
                [str(script)], cwd=str(root), env=env,
                input=json.dumps({"session_id": session_id}),
                capture_output=True, text=True, check=False,
            )
            output = json.loads(proc.stdout)
            self.assertEqual(output["decision"], "block")
            self.assertIn("unavailable", output["reason"].lower())
            self.assertFalse(Path(env["GIT_LOG"]).exists())

    def test_all_outer_dispatchers_fail_closed_for_empty_nonzero_object_and_malformed_bridges(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            home = root / "home"
            hooks = home / ".dotfiles" / ".claude" / "hooks"
            hooks.mkdir(parents=True)
            for name in (
                "lifecycle-pretool.sh", "lifecycle-envelope.py", "sessionstart.sh",
                "userpromptsubmit.sh", "stop.sh",
            ):
                shutil.copy2(ROOT / ".claude" / "hooks" / name, hooks / name)
            (hooks / "lifecycle-hook.sh").write_text("""#!/usr/bin/env bash
case "${BRIDGE_MODE:-}" in
  empty) exit 0 ;;
  nonzero)
    printf '{"lifecycle_hook":{"schema_version":1,"processed":true,"event":"%s","binding":"unbound"}}\n' "$1"
    exit 7
    ;;
  object) printf '{}\n' ;;
  malformed) printf '{bad\n' ;;
esac
""")
            stubs = (
                "settings-symlink-guard.sh", "session-init.sh", "supermemory-project-check.sh",
                "model-availability-check.sh", "hook-graduate.sh", "session-init-enforcer.sh",
                "session-duration-guard.sh", "plans-healthcheck.sh", "prompt-parallelism-hint.sh",
                "plan-todowrite-reminder.sh", "prompt-capture.sh", "prompt-score-correction.sh",
                "symbol-intent.sh", "env-preflight.sh", "session-end.sh",
                "plan-completion-check.sh", "feedback-capture.sh", "task-gate.sh",
            )
            for name in stubs:
                (hooks / name).write_text("#!/usr/bin/env bash\nexit 0\n")
            (hooks / "git-pipeline-gate.sh").write_text(
                """#!/usr/bin/env bash
printf '%s\n' '{"decision":"block","reason":"legacy must not run"}'
""")
            tmux = home / ".dotfiles" / "tmux" / "scripts"
            tmux.mkdir(parents=True)
            (tmux / "claude-tmux-bridge.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (bin_dir / "lean-ctx").write_text("#!/usr/bin/env bash\nexit 0\n")
            for path in (*hooks.iterdir(), tmux / "claude-tmux-bridge.sh", bin_dir / "lean-ctx"):
                path.chmod(0o755)

            scripts = {
                "PreToolUse": hooks / "lifecycle-pretool.sh",
                "SessionStart": hooks / "sessionstart.sh",
                "UserPromptSubmit": hooks / "userpromptsubmit.sh",
                "Stop": hooks / "stop.sh",
            }
            for mode in ("empty", "nonzero", "object", "malformed"):
                for event, script in scripts.items():
                    with self.subTest(mode=mode, event=event):
                        # Fresh session id per subtest. All four modes drive Stop down
                        # the same fail-closed path, so a shared id would let stop.sh's
                        # loop-breaker degrade the third and fourth block into an allow
                        # and this test would stop measuring fail-closed at all.
                        session_id = f"outer-{mode}-{event}-{uuid.uuid4().hex}"
                        self.addCleanup(
                            lambda s=session_id: Path(
                                f"/tmp/.claude-lifecycle-stop-{s}").unlink(missing_ok=True))
                        payload = json.dumps({
                            "cwd": str(root), "session_id": session_id,
                            "tool_name": "Write", "tool_input": {"file_path": str(root / "x")},
                            "prompt": "test", "stop_hook_active": False,
                        })
                        env = os.environ.copy()
                        env.update({
                            "HOME": str(home), "BRIDGE_MODE": mode,
                            "PATH": f"{bin_dir}:{env['PATH']}",
                        })
                        proc = subprocess.run(
                            [str(script)], cwd=str(root), env=env, input=payload,
                            capture_output=True, text=True, check=False,
                        )
                        self.assertEqual(proc.returncode, 0, proc.stderr)
                        value = json.loads(proc.stdout)
                        if event == "PreToolUse":
                            self.assertEqual(
                                value["hookSpecificOutput"]["permissionDecision"], "deny")
                        elif event == "Stop":
                            self.assertEqual(value["decision"], "block")
                            self.assertIn("invalid", value["reason"].lower())
                        else:
                            context = value["hookSpecificOutput"]["additionalContext"]
                            self.assertIn("unavailable or invalid", context)

    def test_settings_pretool_command_independently_validates_dispatcher_output(self):
        settings = json.loads(
            (ROOT / "ai" / "config" / "claude" / "settings.base.json").read_text()
        )
        lifecycle_entry = next(
            item for item in settings["hooks"]["PreToolUse"]
            if item["matcher"] == (
                "Edit|Write|MultiEdit|NotebookEdit|Bash|EnterWorktree|ExitWorktree"
            )
        )
        command = lifecycle_entry["hooks"][0]["command"]
        valid_allow = {
            "lifecycle_hook": {
                "schema_version": 1, "processed": True, "event": "PreToolUse",
                "binding": "unbound",
            }
        }
        valid_deny = {
            "lifecycle_hook": {
                "schema_version": 1, "processed": True, "event": "PreToolUse",
                "binding": "bound", "run_id": "run-1",
            },
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": "[HARD-BLOCK — DO NOT RETRY] fixture deny",
            },
        }
        invalid_outputs = {
            "empty": ("#!/usr/bin/env bash\nexit 0\n", None),
            "exit-7": (
                "#!/usr/bin/env bash\nprintf '%s\n' '" + json.dumps(valid_allow) + "'\nexit 7\n",
                None,
            ),
            "object": ("#!/usr/bin/env bash\nprintf '%s\n' '{}'\n", None),
            "malformed": ("#!/usr/bin/env bash\nprintf '%s\n' '{bad'\n", None),
            "wrong-event": (
                "#!/usr/bin/env bash\nprintf '%s\n' "
                "'{\"lifecycle_hook\":{\"schema_version\":1,\"processed\":true,"
                "\"event\":\"Stop\",\"binding\":\"unbound\"}}'\n",
                None,
            ),
            "missing-run-id": (
                "#!/usr/bin/env bash\nprintf '%s\n' "
                "'{\"lifecycle_hook\":{\"schema_version\":1,\"processed\":true,"
                "\"event\":\"PreToolUse\",\"binding\":\"bound\"}}'\n",
                None,
            ),
            "wrong-binding": (
                "#!/usr/bin/env bash\nprintf '%s\n' "
                "'{\"lifecycle_hook\":{\"schema_version\":1,\"processed\":true,"
                "\"event\":\"PreToolUse\",\"binding\":\"forged\"}}'\n",
                None,
            ),
            "invalid-native": (
                "#!/usr/bin/env bash\nprintf '%s\n' "
                "'{\"lifecycle_hook\":{\"schema_version\":1,\"processed\":true,"
                "\"event\":\"PreToolUse\",\"binding\":\"unbound\"},"
                "\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\","
                "\"permissionDecision\":\"allow\","
                "\"permissionDecisionReason\":\"not a deny\"}}'\n",
                None,
            ),
        }
        payload = json.dumps({
            "cwd": "/tmp", "session_id": "settings-test", "tool_name": "Write",
            "tool_input": {"file_path": "/tmp/x"},
        })
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            home = root / "home"
            hooks = home / ".dotfiles" / ".claude" / "hooks"
            hooks.mkdir(parents=True)
            dispatcher = hooks / "lifecycle-pretool.sh"
            env = os.environ.copy()
            env["HOME"] = str(home)

            for name, (source, _) in invalid_outputs.items():
                with self.subTest(name=name):
                    dispatcher.write_text(source)
                    dispatcher.chmod(0o755)
                    proc = subprocess.run(
                        command, shell=True, cwd=str(root), env=env, input=payload,
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    value = json.loads(proc.stdout)
                    self.assertEqual(
                        value["hookSpecificOutput"]["permissionDecision"], "deny")
                    self.assertIn(
                        "independent settings validation",
                        value["hookSpecificOutput"]["permissionDecisionReason"],
                    )

            hook = hooks / "lifecycle-hook.sh"
            validator = hooks / "lifecycle-envelope.py"
            hook.write_text("#!/usr/bin/env bash\nprintf '%s\n' '{jointly-corrupt'\n")
            validator.write_text(
                "#!/usr/bin/env python3\nimport sys\nsys.stdin.read()\nraise SystemExit(0)\n")
            dispatcher.write_text(
                "#!/usr/bin/env bash\n"
                "output=\"$(bash \"$HOME/.dotfiles/.claude/hooks/lifecycle-hook.sh\")\"\n"
                "printf '%s' \"$output\" | python3 "
                "\"$HOME/.dotfiles/.claude/hooks/lifecycle-envelope.py\" >/dev/null\n"
                "printf '%s\n' \"$output\"\n"
            )
            for path in (hook, validator, dispatcher):
                path.chmod(0o755)
            corrupt = subprocess.run(
                command, shell=True, cwd=str(root), env=env, input=payload,
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(corrupt.returncode, 0, corrupt.stderr)
            self.assertEqual(
                json.loads(corrupt.stdout)["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )

            for expected in (valid_allow, valid_deny):
                with self.subTest(valid=expected):
                    dispatcher.write_text(
                        "#!/usr/bin/env bash\nprintf '%s\n' '" + json.dumps(expected) + "'\n")
                    dispatcher.chmod(0o755)
                    proc = subprocess.run(
                        command, shell=True, cwd=str(root), env=env, input=payload,
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(json.loads(proc.stdout), expected)

    def test_canonical_settings_and_dispatchers_use_portable_lifecycle_wiring(self):
        settings_path = ROOT / "ai" / "config" / "claude" / "settings.base.json"
        settings = json.loads(settings_path.read_text())
        entries = settings["hooks"]["PreToolUse"]
        lifecycle_entries = [item for item in entries
                             if item["matcher"] == "Edit|Write|MultiEdit|NotebookEdit|Bash|EnterWorktree|ExitWorktree"]
        self.assertEqual(len(lifecycle_entries), 1)
        command = lifecycle_entries[0]["hooks"][0]["command"]
        self.assertIn('dispatcher="$HOME/.dotfiles/.claude/hooks/lifecycle-pretool.sh"', command)
        self.assertIn("output failed independent settings validation; failed closed.", command)
        self.assertIn("LIFECYCLE_DISPATCH_RC", command)
        self.assertIn('/bin/bash "$dispatcher"', command)
        self.assertIn("/usr/bin/python3 -c", command)
        self.assertIn("object_pairs_hook=unique", command)
        self.assertNotIn("lifecycle-envelope.py", command)
        self.assertNotIn("args", lifecycle_entries[0]["hooks"][0])
        self.assertIn('_LIFECYCLE_BRIDGE="$SCRIPT_DIR/lifecycle-hook.sh"',
                      (ROOT / ".claude/hooks/sessionstart.sh").read_text())
        self.assertIn(
            '_LIFECYCLE_BRIDGE="$HOME/.dotfiles/.claude/hooks/lifecycle-hook.sh"',
            (ROOT / ".claude/hooks/userpromptsubmit.sh").read_text(),
        )
        with tempfile.TemporaryDirectory() as td:
            env = os.environ.copy()
            env["HOME"] = td
            missing = subprocess.run(
                command, shell=True, cwd=td, env=env, input="{}",
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(missing.returncode, 0)
        self.assertEqual(json.loads(missing.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_adapter_is_stdlib_only_phased_and_materially_smaller_than_controller(self):
        adapter_source = Path(adapter.__file__).read_text()
        controller_source = Path(controller.__file__).read_text()
        tree = __import__("ast").parse(adapter_source)
        imports = {
            alias.name.split(".", 1)[0]
            for node in tree.body if isinstance(node, (__import__("ast").Import, __import__("ast").ImportFrom))
            for alias in node.names
        }
        self.assertNotIn("requests", imports)
        self.assertNotIn("yaml", imports)
        self.assertIn("def execute_action(", adapter_source)
        self.assertIn("def reconcile_ci(", adapter_source)
        self.assertIn("def hook_pre_write(", adapter_source)


if __name__ == "__main__":
    unittest.main()
