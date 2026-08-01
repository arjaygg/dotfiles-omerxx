#!/usr/bin/env python3
"""Claude Code adapter for the shared deterministic git lifecycle controller."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import git_lifecycle as lifecycle  # noqa: E402


ADAPTER_SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parents[2]
STACK = ROOT / ".claude" / "scripts" / "stack"
COMMIT = ROOT / "scripts" / "ai" / "commit.sh"
VALIDATE = ROOT / "scripts" / "ai" / "validate-changeset.sh"
AUTONOMY = ROOT / "scripts" / "ai" / "autonomy-tier.sh"
HARD_BLOCK = "[HARD-BLOCK — DO NOT RETRY]"
ACTION_STAGES = {
    "create_stack": "auto_stack",
    "commit": "auto_commit",
    "push": "auto_push",
    "open_pr": "auto_pr",
}
EDITING_ACTIONS = frozenset({"editing", "awaiting_work"})
PROHIBITED_ACTIONS = frozenset({"merge_eligible", "sync", "cleanup"})
SUCCESS_CHECK_STATES = frozenset({"pass", "passed", "success", "successful", "completed"})
FAILED_CHECK_STATES = frozenset(
    {"fail", "failed", "failure", "cancel", "cancelled", "canceled", "timed_out", "error"}
)
PENDING_CHECK_STATES = frozenset(
    {"pending", "queued", "waiting", "requested", "in_progress", "in-progress", "running"}
)
OID_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class AdapterError(RuntimeError):
    def __init__(self, message: str, code: str = "adapter_error"):
        super().__init__(message)
        self.code = code


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def stable_key(prefix: str, payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return f"adapter:{prefix}:{hashlib.sha256(encoded).hexdigest()}"


def run_command(
    args: Sequence[str | Path],
    cwd: Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        [str(item) for item in args],
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if check and proc.returncode:
        raise AdapterError(
            f"canonical action failed with exit status {proc.returncode}",
            "action_command_failed",
        )
    return proc


def lifecycle_opted_in(root: Path) -> bool:
    config = root / ".claude-atomic.yaml"
    try:
        lines = config.read_text().splitlines()
    except (FileNotFoundError, OSError, UnicodeError):
        return False
    block: list[str] | None = None
    for index, raw in enumerate(lines):
        line = raw.split("#", 1)[0].rstrip()
        if line == "lifecycle:":
            block = []
            for nested in lines[index + 1 :]:
                clean = nested.split("#", 1)[0].rstrip()
                if clean and not clean[0].isspace():
                    break
                block.append(clean)
            break
    if block is None:
        return False
    enabled: str | None = None
    for raw in block:
        match = re.fullmatch(r"\s+enabled:\s*([^\s]+)\s*", raw)
        if match:
            enabled = match.group(1).strip("\"'").lower()
            break
    if enabled is None:
        return True
    return enabled in {"true", "yes", "on", "1"}


def require_opt_in(cwd: Path | str) -> lifecycle.Repo:
    try:
        repo = lifecycle.discover_repo(cwd)
    except Exception as exc:
        raise AdapterError("not a git repository", "not_git_repository") from exc
    if not lifecycle_opted_in(repo.root):
        raise AdapterError("repository has not opted into lifecycle control", "not_opted_in")
    return repo


def effective_session(value: str | None) -> str:
    result = value or os.environ.get("CLAUDE_SESSION_ID") or "default"
    if not isinstance(result, str) or not result.strip() or "\x00" in result:
        raise AdapterError("invalid Claude session identity", "invalid_session")
    return result.strip()


def session_key(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


def adapter_root(common_dir: Path) -> Path:
    return common_dir / lifecycle.STATE_DIR


def binding_path(common_dir: Path, session_id: str) -> Path:
    return adapter_root(common_dir) / "sessions" / f"{session_key(session_id)}.json"


def adapter_lock_path(common_dir: Path) -> Path:
    return adapter_root(common_dir) / "adapter.lock"


def read_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise AdapterError("Claude session has no bound lifecycle run", "run_unbound") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AdapterError("lifecycle adapter state is unreadable", code) from exc
    if not isinstance(value, dict):
        raise AdapterError("lifecycle adapter state is malformed", code)
    return value


def load_binding(repo: lifecycle.Repo, session_id: str) -> dict[str, Any]:
    value = read_json(binding_path(repo.common_dir, session_id), "invalid_binding")
    if (
        value.get("schema_version") != ADAPTER_SCHEMA_VERSION
        or value.get("session_key") != session_key(session_id)
        or not isinstance(value.get("run_id"), str)
    ):
        raise AdapterError("lifecycle session binding is malformed", "invalid_binding")
    return value


def load_run_state(repo: lifecycle.Repo, run_id: str) -> dict[str, Any]:
    state_path, _, _ = lifecycle.locations(repo.common_dir, run_id)
    state = lifecycle.load_state(state_path)
    lifecycle.validate_state(state, run_id)
    if state["repository"]["git_common_dir"] != str(repo.common_dir):
        raise AdapterError("bound run belongs to another repository", "binding_repository_mismatch")
    return state


def bound_state(
    cwd: Path | str,
    session_id: str,
    requested_run_id: str | None = None,
) -> tuple[lifecycle.Repo, dict[str, Any], dict[str, Any]]:
    repo = require_opt_in(cwd)
    binding = load_binding(repo, session_id)
    if requested_run_id is not None and requested_run_id != binding["run_id"]:
        raise AdapterError("requested run does not match the Claude session binding", "run_binding_mismatch")
    return repo, binding, load_run_state(repo, binding["run_id"])


def write_binding(repo: lifecycle.Repo, session_id: str, run_id: str) -> dict[str, Any]:
    path = binding_path(repo.common_dir, session_id)
    with lifecycle.RepoLock(adapter_lock_path(repo.common_dir), 10):
        if path.exists():
            current = load_binding(repo, session_id)
            if current["run_id"] == run_id:
                return current
            prior = load_run_state(repo, current["run_id"])
            if prior["terminal"] is None:
                raise AdapterError(
                    "Claude session is already bound to a nonterminal lifecycle run",
                    "session_already_bound",
                )
        value = {
            "schema_version": ADAPTER_SCHEMA_VERSION,
            "session_key": session_key(session_id),
            "run_id": run_id,
            "bound_at": now(),
        }
        lifecycle.atomic_json(path, value)
        return value


def append_adapter_audit(
    common_dir: Path,
    run_id: str,
    event: str,
    result: str,
    *,
    action: str | None = None,
    stage: str | None = None,
    reason_code: str | None = None,
    head_sha: str | None = None,
) -> None:
    allowed = {
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "timestamp": now(),
        "run_id": run_id,
        "event": event,
        "result": result,
    }
    optional = {
        "action": action,
        "stage": stage,
        "reason_code": reason_code,
        "head_sha": head_sha if head_sha and OID_RE.fullmatch(head_sha) else None,
    }
    allowed.update({key: value for key, value in optional.items() if value is not None})
    path = adapter_root(common_dir) / "adapter-audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(allowed, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def decision_head(decision: dict[str, Any]) -> str | None:
    git_view = decision.get("evidence", {}).get("git")
    return git_view.get("head_sha") if isinstance(git_view, dict) else None


def inspect_bound(repo: lifecycle.Repo, run_id: str) -> dict[str, Any]:
    return lifecycle.inspect_run(repo.root, run_id)


def start(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    repo = require_opt_in(cwd)
    session_id = effective_session(args.session_id)
    payload = {
        "task": args.task, "base_branch": args.base_branch, "base_sha": args.base_sha,
        "intended_branch": args.intended_branch, "owned_paths": sorted(args.owned_paths),
        "worktree": args.worktree, "unit_id": args.work_unit_id, "unit": args.work_unit,
    }
    result = lifecycle.start_run(
        repo.root, run_id=args.run_id, task=args.task, base_branch=args.base_branch,
        base_sha=args.base_sha, intended_branch=args.intended_branch,
        owned_paths=args.owned_paths, worktree=args.worktree, unit_id=args.work_unit_id,
        unit_description=args.work_unit,
        key=args.idempotency_key or stable_key("start", payload), timeout=args.lock_timeout,
    )
    run_id = result["run_id"]
    write_binding(repo, session_id, run_id)
    if not result.get("idempotent"):
        append_adapter_audit(repo.common_dir, run_id, "session_bind", "success")
    return {
        "ok": True, "enabled": True, "bound": True, "run_id": run_id,
        "controller": result, "status": inspect_bound(repo, run_id),
    }


def ready(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    session_id = effective_session(args.session_id)
    repo, binding, state = bound_state(cwd, session_id, args.run_id)
    payload = {
        "work_unit": state["current_unit_id"], "subject": args.subject, "body": args.body,
        "open_tasks": args.open_tasks, "validations": args.validations,
    }
    result = lifecycle.ready_run(
        repo.root,
        run_id=binding["run_id"],
        subject=args.subject,
        body=args.body,
        open_tasks=args.open_tasks,
        validations=args.validations,
        key=args.idempotency_key or stable_key("ready", payload),
        timeout=args.lock_timeout,
    )
    return {**result, "status": inspect_bound(repo, binding["run_id"])}


def next_unit(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    session_id = effective_session(args.session_id)
    repo, binding, _ = bound_state(cwd, session_id, args.run_id)
    payload = {"unit_id": args.work_unit_id, "description": args.description}
    result = lifecycle.next_unit_run(
        repo.root,
        run_id=binding["run_id"],
        unit_id=args.work_unit_id,
        description=args.description,
        key=args.idempotency_key or stable_key("next-unit", payload),
        timeout=args.lock_timeout,
    )
    return {**result, "status": inspect_bound(repo, binding["run_id"])}


def status(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    try:
        repo = require_opt_in(cwd)
    except AdapterError as exc:
        if exc.code == "not_opted_in":
            return {"ok": True, "enabled": False, "bound": False}
        raise
    session_id = effective_session(args.session_id)
    try:
        binding = load_binding(repo, session_id)
    except AdapterError as exc:
        if exc.code == "run_unbound":
            return {
                "ok": True,
                "enabled": True,
                "bound": False,
                "action": "start_required",
                "reason_code": "run_unbound",
                "reason": "start and bind a lifecycle run before editing",
            }
        raise
    if args.run_id is not None and args.run_id != binding["run_id"]:
        raise AdapterError("requested run does not match the Claude session binding", "run_binding_mismatch")
    return {
        **inspect_bound(repo, binding["run_id"]),
        "ok": True,
        "enabled": True,
        "bound": True,
    }


def resolve_autonomy(repo: lifecycle.Repo, stage: str) -> tuple[bool, str]:
    proc = run_command([AUTONOMY, "--stage", stage, "--json"], repo.root, check=False)
    if proc.returncode:
        return False, "autonomy_resolver_failed"
    try:
        value = json.loads(proc.stdout)
        effective = value["effective"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return False, "autonomy_resolver_invalid"
    match = re.fullmatch(r"A([0-4])", effective) if isinstance(effective, str) else None
    if match is None:
        return False, "autonomy_resolver_invalid"
    return (int(match.group(1)) >= 2, "authorized" if int(match.group(1)) >= 2 else "autonomy_below_a2")


def action_target(repo: lifecycle.Repo, state: dict[str, Any]) -> lifecycle.Repo:
    target, _ = lifecycle.target_repo(state, repo)
    return target


def action_create_stack(repo: lifecycle.Repo, state: dict[str, Any], _: dict[str, Any]) -> None:
    start_root = Path(state["repository"]["start_worktree"])
    run_command(
        [
            STACK,
            "create",
            state["intended_branch"],
            state["base"]["branch"],
            "--base-sha",
            state["base"]["sha"],
        ],
        start_root,
    )


def staged_paths(repo: lifecycle.Repo) -> list[str]:
    raw = lifecycle.git(
        repo.root,
        "diff",
        "--cached",
        "--name-status",
        "-z",
        "--find-renames",
        text=False,
    ).stdout
    return lifecycle.parse_name_status(raw)


def action_commit(
    repo: lifecycle.Repo,
    state: dict[str, Any],
    decision: dict[str, Any],
) -> None:
    target = action_target(repo, state)
    unit = lifecycle.current_unit(state)
    ready_fact = unit.get("ready")
    if unit.get("status") != "ready" or not isinstance(ready_fact, dict):
        raise AdapterError("controller did not provide ready commit evidence", "ready_evidence_missing")
    approved = sorted(ready_fact.get("paths", []))
    observed = sorted(decision.get("evidence", {}).get("owned_dirty_paths", []))
    if not approved or approved != observed:
        raise AdapterError("ready paths do not match fresh controller evidence", "approved_paths_changed")
    pathspecs = [f":(literal){path}" for path in approved]
    lifecycle.git(target.root, "add", "-A", "--", *pathspecs)
    if staged_paths(target) != approved:
        raise AdapterError("staged paths differ from the exact approved set", "staged_paths_mismatch")
    run_command([VALIDATE, "--json"], target.root)
    run_command(
        [COMMIT, "-m", ready_fact["subject"], "-m", ready_fact["body"]],
        target.root,
    )


def action_push(repo: lifecycle.Repo, state: dict[str, Any], decision: dict[str, Any]) -> None:
    target = action_target(repo, state)
    git_view = decision["evidence"]["git"]
    if git_view["branch"] != state["intended_branch"]:
        raise AdapterError("refusing to push an unexpected branch", "unexpected_branch")
    if git_view["upstream"]["name"] is None:
        lifecycle.git(target.root, "push", "--set-upstream", "origin", state["intended_branch"])
    else:
        lifecycle.git(target.root, "push")


def parse_prs(proc: subprocess.CompletedProcess[str], branch: str, head: str) -> list[dict[str, Any]]:
    if proc.returncode:
        raise AdapterError("GitHub PR inspection failed", "pr_inspection_failed")
    try:
        values = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AdapterError("GitHub PR inspection returned malformed data", "pr_data_malformed") from exc
    if not isinstance(values, list):
        raise AdapterError("GitHub PR inspection returned malformed data", "pr_data_malformed")
    exact: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            raise AdapterError("GitHub PR inspection returned malformed data", "pr_data_malformed")
        if value.get("headRefName") == branch and value.get("headRefOid") == head:
            exact.append(value)
    if len(exact) > 1:
        raise AdapterError("multiple exact-head pull requests are ambiguous", "pr_ambiguous")
    return exact


def query_exact_pr(target: lifecycle.Repo, branch: str, head: str) -> dict[str, Any] | None:
    proc = run_command(
        [
            "gh",
            "pr",
            "list",
            "--head",
            branch,
            "--state",
            "all",
            "--limit",
            "100",
            "--json",
            "number,state,isDraft,headRefOid,headRefName,url",
        ],
        target.root,
        check=False,
    )
    exact = parse_prs(proc, branch, head)
    return exact[0] if exact else None


def pr_status(value: dict[str, Any]) -> str:
    state = value.get("state")
    if state == "OPEN":
        return "draft" if value.get("isDraft") is True else "open"
    if state == "MERGED":
        return "merged"
    if state == "CLOSED":
        return "closed"
    raise AdapterError("pull request state is unknown", "pr_data_malformed")


def record_pr(
    repo: lifecycle.Repo,
    run_id: str,
    head: str,
    value: dict[str, Any],
) -> None:
    number = value.get("number")
    if not isinstance(number, int) or number <= 0:
        raise AdapterError("pull request identity is malformed", "pr_data_malformed")
    lifecycle.record_run(
        repo.root,
        run_id=run_id,
        kind="pr",
        status_value=pr_status(value),
        source="github-pr",
        sha=head,
        authoritative=True,
        receipt_sha=None,
        metadata={"number": number, "url": value.get("url") if isinstance(value.get("url"), str) else ""},
        key=stable_key("pr-fact", {"head": head, "number": number, "status": pr_status(value)}),
        timeout=10,
    )


def action_open_pr(
    repo: lifecycle.Repo,
    state: dict[str, Any],
    decision: dict[str, Any],
) -> None:
    target = action_target(repo, state)
    head = decision_head(decision)
    if head is None:
        raise AdapterError("controller did not provide an exact HEAD", "missing_head")
    branch = state["intended_branch"]
    pull_request = query_exact_pr(target, branch, head)
    if pull_request is None:
        run_command([STACK, "pr", branch], target.root)
        pull_request = query_exact_pr(target, branch, head)
    if pull_request is None:
        raise AdapterError("canonical PR creation produced no exact-head PR", "pr_exact_head_missing")
    record_pr(repo, state["run_id"], head, pull_request)


def demote_stage(common_dir: Path, stage: str, run_id: str) -> None:
    if stage not in ACTION_STAGES.values():
        raise AdapterError("invalid demotion stage", "invalid_stage")
    path = common_dir / f"autonomy-demoted-{stage}"
    lifecycle.atomic_json(
        path,
        {
            "schema_version": ADAPTER_SCHEMA_VERSION,
            "stage": stage,
            "run_id": run_id,
            "demoted_at": now(),
            "source": "lifecycle_adapter",
        },
    )


def adapter_result(
    run_id: str, outcome: str, before: dict[str, Any], *,
    after: dict[str, Any] | None = None, ok: bool = True, **extra: Any,
) -> dict[str, Any]:
    return {
        "ok": ok, "enabled": True, "bound": True, "run_id": run_id,
        "outcome": outcome, "before": before, "after": after or before, **extra,
    }


def action_audit(
    repo: lifecycle.Repo, run_id: str, decision: dict[str, Any], result: str,
    *, stage: str | None = None, reason_code: str | None = None,
) -> None:
    append_adapter_audit(
        repo.common_dir, run_id, "action", result, action=decision["action"],
        stage=stage, reason_code=reason_code, head_sha=decision_head(decision),
    )


def decision_token(decision: dict[str, Any]) -> tuple[Any, ...]:
    evidence = decision.get("evidence", {})
    return (
        decision.get("action"), decision_head(decision), evidence.get("run_revision"),
        tuple(evidence.get("owned_dirty_paths", [])),
    )


def execute_action(
    repo: lifecycle.Repo, run_id: str, decision: dict[str, Any], state: dict[str, Any],
    action_fn: Callable[[lifecycle.Repo, dict[str, Any], dict[str, Any]], None],
) -> dict[str, Any]:
    stage = ACTION_STAGES[decision["action"]]
    authorized, code = resolve_autonomy(repo, stage)
    if not authorized:
        action_audit(repo, run_id, decision, "approval_required", stage=stage, reason_code=code)
        return adapter_result(
            run_id, "approval_required", decision, after=inspect_bound(repo, run_id),
            stage=stage, reason_code=code,
        )
    fresh = inspect_bound(repo, run_id)
    if decision_token(fresh) != decision_token(decision):
        action_audit(repo, run_id, fresh, "refused", stage=stage, reason_code="stale_inspection")
        return adapter_result(
            run_id, "blocked", decision, after=fresh, reason_code="stale_inspection",
        )
    decision = fresh
    action_audit(repo, run_id, decision, "attempt", stage=stage)
    try:
        action_fn(repo, state, decision)
    except Exception as exc:
        code = exc.code if isinstance(exc, (AdapterError, lifecycle.LifecycleError)) else "action_failed"
        action_audit(repo, run_id, decision, "failure", stage=stage, reason_code=code)
        demote_stage(repo.common_dir, stage, run_id)
        return adapter_result(
            run_id, "action_failed", decision, after=inspect_bound(repo, run_id),
            ok=False, stage=stage, reason_code=code,
        )
    action_audit(repo, run_id, decision, "success", stage=stage)
    return adapter_result(
        run_id, "advanced", decision, after=inspect_bound(repo, run_id), stage=stage,
    )


def watcher_paths(common_dir: Path, run_id: str, sha: str) -> tuple[Path, Path]:
    safe_run = hashlib.sha256(run_id.encode()).hexdigest()
    root = adapter_root(common_dir) / "watchers" / safe_run
    return root / f"{sha}.json", root / f"{sha}.lock"


def pid_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError, PermissionError):
        return False
    return True


def write_watcher_marker(path: Path, run_id: str, sha: str, status: str, pid: int | None) -> None:
    lifecycle.atomic_json(path, {
        "schema_version": ADAPTER_SCHEMA_VERSION, "run_id": run_id, "sha": sha,
        "status": status, "pid": pid, "updated_at": now(),
    })


def spawn_watcher(repo: lifecycle.Repo, run_id: str, sha: str) -> dict[str, Any]:
    marker, lock_path = watcher_paths(repo.common_dir, run_id, sha)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if marker.exists():
            prior = read_json(marker, "watcher_state_invalid")
            if prior.get("status") in {"starting", "running"} and pid_alive(prior.get("pid")):
                return {"started": False, "duplicate": True, "sha": sha}
        write_watcher_marker(marker, run_id, sha, "starting", None)
        try:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "watch",
                    "--run-id",
                    run_id,
                    "--sha",
                    sha,
                ],
                cwd=str(repo.root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
        except OSError as exc:
            write_watcher_marker(marker, run_id, sha, "failed", None)
            raise AdapterError("unable to start detached CI watcher", "watcher_spawn_failed") from exc
        write_watcher_marker(marker, run_id, sha, "running", proc.pid)
        return {"started": True, "duplicate": False, "sha": sha}
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def tick(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    repo, binding, state = bound_state(cwd, effective_session(args.session_id), args.run_id)
    run_id = binding["run_id"]
    decision = inspect_bound(repo, run_id)
    action = decision["action"]
    action_fn = {
        "create_stack": action_create_stack, "commit": action_commit,
        "push": action_push, "open_pr": action_open_pr,
    }.get(action)
    if action_fn:
        return execute_action(repo, run_id, decision, state, action_fn)
    if action == "wait_ci":
        head = decision_head(decision)
        if head is None:
            raise AdapterError("CI wait lacks an exact HEAD", "missing_head")
        watcher = spawn_watcher(repo, run_id, head)
        append_adapter_audit(
            repo.common_dir, run_id, "watcher",
            "started" if watcher["started"] else "duplicate", action=action, head_sha=head,
        )
        return adapter_result(
            run_id, "watching", decision, after=inspect_bound(repo, run_id), watcher=watcher,
        )
    if action in PROHIBITED_ACTIONS:
        action_audit(repo, run_id, decision, "approval_required", reason_code="action_deferred")
        return adapter_result(run_id, "approval_required", decision, reason_code="action_deferred")
    outcome = "done" if action == "done" else "blocked" if action == "blocked" else "idle"
    return adapter_result(run_id, outcome, decision, ok=action != "blocked")


def classify_required_checks(value: Any) -> tuple[str, dict[str, Any]]:
    if not isinstance(value, list) or not value:
        return "unknown", {"required_count": 0, "check_names": []}
    states: list[str] = []
    names: list[str] = []
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            return "unknown", {"required_count": len(value), "check_names": sorted(names)}
        name = item["name"].strip()
        raw = item.get("bucket", item.get("state"))
        if not isinstance(raw, str):
            return "unknown", {"required_count": len(value), "check_names": sorted(names + [name])}
        state_value = raw.strip().lower().replace(" ", "_")
        if state_value in SUCCESS_CHECK_STATES:
            states.append("passing")
        elif state_value in FAILED_CHECK_STATES:
            states.append("failed")
        elif state_value in PENDING_CHECK_STATES:
            states.append("pending")
        else:
            states.append("unknown")
        names.append(name)
    metadata = {"required_count": len(value), "check_names": sorted(set(names))}
    if "failed" in states:
        return "failed", metadata
    if "unknown" in states:
        return "unknown", metadata
    if "pending" in states:
        return "pending", metadata
    return "passing", metadata


def reconcile_ci(repo: lifecycle.Repo, run_id: str, expected_sha: str) -> dict[str, Any]:
    state = load_run_state(repo, run_id)
    target = action_target(repo, state)
    current_head = lifecycle.exact_head(target)
    if current_head != expected_sha:
        return {"ok": True, "outcome": "stale", "status": "unknown", "sha": expected_sha}
    pull_request = query_exact_pr(target, state["intended_branch"], expected_sha)
    if pull_request is None:
        check_status, metadata = "unknown", {"required_count": 0, "check_names": []}
    else:
        number = pull_request.get("number")
        if not isinstance(number, int) or number <= 0:
            check_status, metadata = "unknown", {"required_count": 0, "check_names": []}
        else:
            proc = run_command(
                [
                    "gh",
                    "pr",
                    "checks",
                    str(number),
                    "--required",
                    "--json",
                    "name,state,bucket",
                ],
                target.root,
                check=False,
            )
            try:
                checks = json.loads(proc.stdout)
            except json.JSONDecodeError:
                checks = None
            check_status, metadata = classify_required_checks(checks)
            metadata["pr_number"] = number
    lifecycle.record_run(
        repo.root,
        run_id=run_id,
        kind="ci",
        status_value=check_status,
        source="github-required-checks",
        sha=expected_sha,
        authoritative=True,
        receipt_sha=None,
        metadata=metadata,
        key=stable_key(
            "ci-fact",
            {"head": expected_sha, "status": check_status, "metadata": metadata},
        ),
        timeout=10,
    )
    append_adapter_audit(
        repo.common_dir,
        run_id,
        "ci_reconcile",
        check_status,
        action="wait_ci",
        head_sha=expected_sha,
    )
    return {
        "ok": True,
        "outcome": "terminal" if check_status in {"passing", "failed"} else "pending",
        "status": check_status,
        "sha": expected_sha,
        "decision": inspect_bound(repo, run_id),
    }


def update_watcher_marker(repo: lifecycle.Repo, run_id: str, sha: str, status_value: str) -> None:
    marker, _ = watcher_paths(repo.common_dir, run_id, sha)
    write_watcher_marker(marker, run_id, sha, status_value, os.getpid())


def safe_reconcile_ci(repo: lifecycle.Repo, run_id: str, sha: str) -> dict[str, Any]:
    try:
        return reconcile_ci(repo, run_id, sha)
    except Exception as exc:
        code = exc.code if isinstance(exc, (AdapterError, lifecycle.LifecycleError)) else "ci_reconcile_failed"
        append_adapter_audit(
            repo.common_dir, run_id, "ci_reconcile", "failure",
            action="wait_ci", reason_code=code, head_sha=sha,
        )
        return {"ok": False, "outcome": "pending", "status": "unknown", "sha": sha}


def watch(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    repo = require_opt_in(cwd)
    lifecycle.validate_name(args.run_id, lifecycle.RUN_ID_RE, "run id")
    lifecycle.validate_oid(args.sha)
    state = load_run_state(repo, args.run_id)
    if state["repository"]["git_common_dir"] != str(repo.common_dir):
        raise AdapterError("watch run belongs to another repository", "binding_repository_mismatch")
    _, lock_path = watcher_paths(repo.common_dir, args.run_id, args.sha)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"ok": True, "outcome": "duplicate", "sha": args.sha}
        update_watcher_marker(repo, args.run_id, args.sha, "running")
        polls = 0
        while True:
            polls += 1
            result = safe_reconcile_ci(repo, args.run_id, args.sha)
            if result["outcome"] in {"terminal", "stale"} or args.once:
                update_watcher_marker(repo, args.run_id, args.sha, result["outcome"])
                return result
            if args.max_polls and polls >= args.max_polls:
                update_watcher_marker(repo, args.run_id, args.sha, "timeout")
                return {**result, "outcome": "timeout"}
            time.sleep(args.interval)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"{HARD_BLOCK} {reason}",
        }
    }


def hook_paths(payload: dict[str, Any]) -> list[str]:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    paths: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in {"file_path", "path"} and isinstance(nested, str):
                    paths.append(nested)
                elif key in {"edits", "files"}:
                    collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)

    collect(tool_input)
    return list(dict.fromkeys(paths))


def hook_repo(payload: dict[str, Any], cwd: Path) -> lifecycle.Repo | None:
    candidate = payload.get("cwd")
    root = Path(candidate) if isinstance(candidate, str) and candidate else cwd
    try:
        repo = lifecycle.discover_repo(root)
    except Exception:
        return None
    return repo if lifecycle_opted_in(repo.root) else None


def audit_hook(
    repo: lifecycle.Repo,
    run_id: str,
    result: str,
    reason_code: str,
    decision: dict[str, Any] | None = None,
) -> None:
    append_adapter_audit(
        repo.common_dir,
        run_id,
        "hook",
        result,
        action=decision.get("action") if decision else None,
        reason_code=reason_code,
        head_sha=decision_head(decision) if decision else None,
    )


def hook_pre_write(
    payload: dict[str, Any],
    repo: lifecycle.Repo,
    session_id: str,
) -> dict[str, Any] | None:
    if payload.get("tool_name") not in {"Edit", "Write", "MultiEdit"}:
        return None
    try:
        binding = load_binding(repo, session_id)
    except AdapterError:
        return deny("Lifecycle run is not bound to this Claude session; run lifecycle_adapter.py start first.")
    run_id = binding["run_id"]
    decision = inspect_bound(repo, run_id)
    if decision["action"] not in EDITING_ACTIONS:
        audit_hook(repo, run_id, "deny", "invalid_editing_state", decision)
        return deny(
            f"Lifecycle state is {decision['action']}; refresh readiness or start the next work unit before writing."
        )
    try:
        state = load_run_state(repo, run_id)
        target = action_target(repo, state)
    except Exception:
        audit_hook(repo, run_id, "deny", "invalid_binding", decision)
        return deny("Bound lifecycle state is invalid; inspect and repair the run before writing.")
    raw_paths = hook_paths(payload)
    if not raw_paths:
        audit_hook(repo, run_id, "deny", "write_path_missing", decision)
        return deny("Write tool input does not identify a path inside the run-owned boundary.")
    for raw in raw_paths:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = repo.root / candidate
        resolved = candidate.resolve(strict=False)
        try:
            relative = resolved.relative_to(target.root.resolve()).as_posix()
        except ValueError:
            audit_hook(repo, run_id, "deny", "path_outside_worktree", decision)
            return deny("Write path is outside the lifecycle run worktree.")
        if not lifecycle.owns(relative, state["owned_paths"]):
            audit_hook(repo, run_id, "deny", "path_not_owned", decision)
            return deny("Write path is outside the lifecycle run-owned boundary.")
    audit_hook(repo, run_id, "allow", "editing_state_valid", decision)
    return None


def status_instruction(value: dict[str, Any]) -> str:
    if not value.get("bound"):
        return "Lifecycle enabled: bind a run with lifecycle_adapter.py start before editing tracked work."
    action = value.get("action", "blocked")
    reason = value.get("reason", "fresh lifecycle inspection required")
    instructions = {
        "create_stack": "Advance lifecycle to create the exact-base linked stack before editing.",
        "editing": "Continue only within owned paths; call ready when this work unit is complete.",
        "awaiting_work": "Begin the current work unit only within owned paths.",
        "commit": "Run lifecycle tick; direct writes are blocked until the ready commit is consumed.",
        "push": "Run lifecycle tick to push the exact committed HEAD.",
        "open_pr": "Run lifecycle tick to reconcile or create the exact-head PR.",
        "wait_ci": "CI is observed asynchronously; do not poll in the hook.",
        "merge_eligible": "Merge is deferred and requires the bounded-merge implementation.",
        "sync": "Sync is deferred and will not execute in this adapter.",
        "cleanup": "Cleanup is deferred and will not execute in this adapter.",
        "blocked": "Resolve the reported lifecycle invariant before continuing.",
        "done": "Lifecycle run is complete.",
    }
    return f"Lifecycle {action}: {reason}. {instructions.get(action, 'Inspect the lifecycle run before continuing.')}"


def hook_context(
    event: str,
    repo: lifecycle.Repo,
    session_id: str,
) -> dict[str, Any]:
    probe = argparse.Namespace(session_id=session_id, run_id=None)
    value = status(probe, repo.root)
    if value.get("bound"):
        audit_hook(repo, value["run_id"], "inject", "status_context", value)
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": status_instruction(value),
        }
    }


def stop_reason(value: dict[str, Any]) -> str:
    outcome = value.get("outcome")
    after = value.get("after", {})
    action = after.get("action", "blocked")
    reason = after.get("reason", value.get("reason_code", "lifecycle transition incomplete"))
    if outcome == "approval_required":
        return f"Lifecycle approval required before {value.get('stage', action)}: {reason}"
    if outcome == "action_failed":
        return f"Lifecycle action failed and its stage was demoted: {value.get('reason_code', action)}"
    if outcome == "watching":
        return "Lifecycle CI watcher is detached; required checks are not yet proven terminal."
    return f"Lifecycle is not complete ({action}): {reason}"


def hook_stop(
    repo: lifecycle.Repo,
    session_id: str,
) -> dict[str, Any] | None:
    try:
        binding = load_binding(repo, session_id)
    except AdapterError:
        return None
    args = argparse.Namespace(session_id=session_id, run_id=binding["run_id"])
    try:
        value = tick(args, repo.root)
    except Exception as exc:
        code = exc.code if isinstance(exc, (AdapterError, lifecycle.LifecycleError)) else "tick_failed"
        audit_hook(repo, binding["run_id"], "block", code)
        return {
            "decision": "block",
            "reason": f"Lifecycle tick failed closed: {code}",
            "lifecycle_bound": True,
        }
    if value.get("outcome") == "done" or value.get("after", {}).get("action") == "done":
        audit_hook(repo, binding["run_id"], "allow", "terminal_done", value.get("after"))
        return {"lifecycle_bound": True}
    audit_hook(repo, binding["run_id"], "block", value.get("reason_code", "lifecycle_incomplete"), value.get("after"))
    return {"decision": "block", "reason": stop_reason(value), "lifecycle_bound": True}


def hook_failure(event: str) -> dict[str, Any] | None:
    if event == "PreToolUse":
        return deny("Lifecycle pre-write inspection failed closed.")
    if event == "Stop":
        return {"decision": "block", "reason": "Lifecycle Stop inspection failed closed.",
                "lifecycle_bound": True}
    return None


def dispatch_hook_event(event: str, payload: dict[str, Any], repo: lifecycle.Repo,
                        session_id: str) -> dict[str, Any] | None:
    if event == "PreToolUse":
        return hook_pre_write(payload, repo, session_id)
    if event in {"SessionStart", "UserPromptSubmit"}:
        return hook_context(event, repo, session_id)
    return hook_stop(repo, session_id) if event == "Stop" else None


def hook(args: argparse.Namespace, cwd: Path, raw: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    repo = hook_repo(payload, cwd)
    if repo is None:
        return None
    raw_session = payload.get("session_id")
    try:
        session_id = effective_session(raw_session if isinstance(raw_session, str) else args.session_id)
        return dispatch_hook_event(args.event, payload, repo, session_id)
    except Exception:
        return hook_failure(args.event)


def timeout_value(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be numeric") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("value may not be negative")
    return value


def session_args(command: argparse.ArgumentParser) -> None:
    command.add_argument("--session-id")
    command.add_argument("--run-id")


def mutation_args(command: argparse.ArgumentParser) -> None:
    session_args(command)
    command.add_argument("--idempotency-key")
    command.add_argument("--lock-timeout", type=timeout_value, default=10)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Claude adapter for deterministic git lifecycle control")
    commands = root.add_subparsers(dest="command", required=True)

    start_parser = commands.add_parser("start")
    start_parser.add_argument("--session-id")
    start_parser.add_argument("--run-id")
    start_parser.add_argument("--task", required=True)
    start_parser.add_argument("--base-branch", required=True)
    start_parser.add_argument("--base-sha", required=True)
    start_parser.add_argument("--intended-branch", "--branch", dest="intended_branch", required=True)
    start_parser.add_argument("--owned-path", "--owned", dest="owned_paths", action="append", required=True)
    start_parser.add_argument("--worktree")
    start_parser.add_argument("--work-unit-id", default="work-1")
    start_parser.add_argument("--work-unit")
    start_parser.add_argument("--idempotency-key")
    start_parser.add_argument("--lock-timeout", type=timeout_value, default=10)

    ready_parser = commands.add_parser("ready")
    mutation_args(ready_parser)
    ready_parser.add_argument("--subject", required=True)
    ready_parser.add_argument("--body", required=True)
    ready_parser.add_argument("--open-tasks", type=int, required=True)
    ready_parser.add_argument("--validation", dest="validations", action="append", required=True)

    next_parser = commands.add_parser("next-unit")
    mutation_args(next_parser)
    next_parser.add_argument("--work-unit-id", required=True)
    next_parser.add_argument("--work-unit", "--description", dest="description", required=True)

    status_parser = commands.add_parser("status")
    session_args(status_parser)

    tick_parser = commands.add_parser("tick")
    session_args(tick_parser)

    watch_parser = commands.add_parser("watch")
    watch_parser.add_argument("--run-id", required=True)
    watch_parser.add_argument("--sha", required=True)
    watch_parser.add_argument("--once", action="store_true")
    watch_parser.add_argument("--interval", type=timeout_value, default=30)
    watch_parser.add_argument("--max-polls", type=int, default=0)

    hook_parser = commands.add_parser("hook")
    hook_parser.add_argument(
        "--event",
        choices=("PreToolUse", "SessionStart", "UserPromptSubmit", "Stop"),
        required=True,
    )
    hook_parser.add_argument("--session-id")
    return root


def dispatch(args: argparse.Namespace, cwd: Path, raw_stdin: str = "") -> dict[str, Any] | None:
    handlers: dict[str, Callable[[argparse.Namespace, Path], dict[str, Any]]] = {
        "start": start,
        "ready": ready,
        "next-unit": next_unit,
        "status": status,
        "tick": tick,
        "watch": watch,
    }
    if args.command == "hook":
        return hook(args, cwd, raw_stdin)
    return handlers[args.command](args, cwd)


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    raw = sys.stdin.read() if args.command == "hook" else ""
    try:
        value = dispatch(args, Path.cwd(), raw)
    except (AdapterError, lifecycle.LifecycleError) as exc:
        print(json.dumps({"ok": False, "error_code": exc.code, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    except Exception as exc:
        print(
            json.dumps({"ok": False, "error_code": "adapter_error", "error": type(exc).__name__}, sort_keys=True),
            file=sys.stderr,
        )
        return 2
    if value is not None:
        print(json.dumps(value, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
