#!/usr/bin/env python3
"""Claude Code adapter for the shared deterministic git lifecycle controller."""
from __future__ import annotations
import argparse, fcntl, hashlib, json, os, re, shlex, stat, subprocess, sys, time
import datetime as dt
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
ACTION_STAGES = {"create_stack": "auto_stack", "commit": "auto_commit",
                 "push": "auto_push", "open_pr": "auto_pr"}
EDITING_ACTIONS = frozenset({"editing", "awaiting_work"})
PROHIBITED_ACTIONS = frozenset({"merge_eligible", "sync", "cleanup"})
SUCCESS_CHECK_STATES = frozenset({"pass", "passed", "success", "successful", "completed"})
FAILED_CHECK_STATES = frozenset({"fail", "failed", "failure", "cancel", "cancelled",
                                 "canceled", "timed_out", "error"})
PENDING_CHECK_STATES = frozenset({"pending", "queued", "waiting", "requested",
                                  "in_progress", "in-progress", "running"})
OID_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
SAFE_AUDIT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
WATCHER_DEFAULT_POLLS = 80
WATCHER_READY_TIMEOUT = 3.0
COMMAND_TIMEOUT = 30.0

class AdapterError(RuntimeError):
    def __init__(self, message: str, code: str = "adapter_error"):
        super().__init__(message)
        self.code = code
def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
def stable_key(prefix: str, payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return f"adapter:{prefix}:{hashlib.sha256(encoded).hexdigest()}"
def run_command(args: Sequence[str | Path], cwd: Path, *, check: bool = True,
                timeout: float = COMMAND_TIMEOUT) -> subprocess.CompletedProcess[str]:
    try:
        proc = subprocess.run(
            [str(item) for item in args], cwd=str(cwd), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise AdapterError("canonical action timed out", "action_command_timeout") from exc
    if check and proc.returncode:
        raise AdapterError(
            f"canonical action failed with exit status {proc.returncode}",
            "action_command_failed",
        )
    return proc
def lifecycle_config_lines(root: Path) -> list[str] | None:
    config = root / ".claude-atomic.yaml"
    try:
        metadata = config.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise AdapterError("lifecycle config is unreadable", "invalid_lifecycle_config") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise AdapterError("lifecycle config is not regular", "invalid_lifecycle_config")
    try:
        return config.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise AdapterError("lifecycle config is unreadable", "invalid_lifecycle_config") from exc
def lifecycle_headers(lines: list[str]) -> list[tuple[int, str]]:
    return [(index, raw.split("#", 1)[0].rstrip()) for index, raw in enumerate(lines)
            if raw.split("#", 1)[0].rstrip()
            and not raw.split("#", 1)[0].rstrip()[0].isspace()
            and raw.split("#", 1)[0].rstrip().startswith("lifecycle")]
def lifecycle_enabled(lines: list[str], start: int) -> list[str]:
    values: list[str] = []
    for raw in lines[start + 1:]:
        clean = raw.split("#", 1)[0].rstrip()
        if clean and not clean[0].isspace():
            break
        if clean.lstrip().startswith("enabled"):
            match = re.fullmatch(r"\s+enabled:\s*([^\s]+)\s*", clean)
            if not match:
                raise AdapterError("lifecycle enabled value is malformed", "invalid_lifecycle_config")
            values.append(match.group(1).strip("\"'").lower())
    return values
def lifecycle_mode(root: Path) -> str:
    try:
        lines = lifecycle_config_lines(root)
        if lines is None:
            return "disabled"
        headers = lifecycle_headers(lines)
        if not headers:
            return "disabled"
        if len(headers) != 1 or headers[0][1] != "lifecycle:":
            return "error"
        enabled = lifecycle_enabled(lines, headers[0][0])
    except AdapterError:
        return "error"
    if len(enabled) != 1:
        return "error"
    if enabled[0] in {"true", "yes", "on", "1"}:
        return "enabled"
    return "disabled" if enabled[0] in {"false", "no", "off", "0"} else "error"
def lifecycle_opted_in(root: Path) -> bool:
    return lifecycle_mode(root) == "enabled"
def require_opt_in(cwd: Path | str) -> lifecycle.Repo:
    try:
        repo = lifecycle.discover_repo(cwd)
    except Exception as exc:
        raise AdapterError("not a git repository", "not_git_repository") from exc
    mode = lifecycle_mode(repo.root)
    if mode == "error":
        raise AdapterError("lifecycle opt-in configuration is invalid", "invalid_lifecycle_config")
    if mode != "enabled":
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
def action_lock_path(common_dir: Path, run_id: str) -> Path:
    lifecycle.validate_name(run_id, lifecycle.RUN_ID_RE, "run id")
    return adapter_root(common_dir) / "action-locks" / f"{run_id}.lock"
def audit_lock_path(common_dir: Path) -> Path:
    return adapter_root(common_dir) / "adapter-audit.lock"
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
def bound_state(cwd: Path | str, session_id: str, requested_run_id: str | None = None,
                ) -> tuple[lifecycle.Repo, dict[str, Any], dict[str, Any]]:
    repo = require_opt_in(cwd)
    binding = load_binding(repo, session_id)
    if requested_run_id is not None and requested_run_id != binding["run_id"]:
        raise AdapterError("requested run does not match the Claude session binding", "run_binding_mismatch")
    return repo, binding, load_run_state(repo, binding["run_id"])
def _write_binding_locked(repo: lifecycle.Repo, session_id: str, run_id: str) -> dict[str, Any]:
    path = binding_path(repo.common_dir, session_id)
    if path.exists():
        current = load_binding(repo, session_id)
        if current["run_id"] == run_id:
            return current
        if load_run_state(repo, current["run_id"])["terminal"] is None:
            raise AdapterError(
                "Claude session is already bound to a nonterminal lifecycle run",
                "session_already_bound",
            )
    value = {
        "schema_version": ADAPTER_SCHEMA_VERSION, "session_key": session_key(session_id),
        "run_id": run_id, "bound_at": now(),
    }
    lifecycle.atomic_json(path, value)
    return value
def write_binding(repo: lifecycle.Repo, session_id: str, run_id: str) -> dict[str, Any]:
    with lifecycle.RepoLock(adapter_lock_path(repo.common_dir), 10):
        return _write_binding_locked(repo, session_id, run_id)
def secure_file(path: Path, flags: int) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, flags | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    metadata = os.fstat(fd)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(fd)
        raise AdapterError("adapter audit target is not a regular file", "audit_file_invalid")
    os.fchmod(fd, 0o600)
    if stat.S_IMODE(os.fstat(fd).st_mode) != 0o600:
        os.close(fd)
        raise AdapterError("adapter audit permissions are unsafe", "audit_mode_invalid")
    return fd
def write_all(fd: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(fd, data[offset:])
        if written <= 0:
            raise AdapterError("adapter audit append was incomplete", "audit_write_failed")
        offset += written
def audit_has_event(fd: int, event_id: str) -> bool:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    needle = f'"event_id":"{event_id}"'.encode()
    return needle in b"".join(chunks)
def append_adapter_audit(common_dir: Path, run_id: str, event: str, result: str, *,
    action: str | None = None, stage: str | None = None,
    reason_code: str | None = None, head_sha: str | None = None) -> None:
    optional = {"action": action, "stage": stage, "reason_code": reason_code}
    values = [run_id, event, result, *(value for value in optional.values() if value is not None)]
    if any(not SAFE_AUDIT_RE.fullmatch(value) for value in values):
        raise AdapterError("adapter audit field is invalid", "audit_field_invalid")
    if head_sha is not None and not OID_RE.fullmatch(head_sha):
        raise AdapterError("adapter audit SHA is invalid", "audit_field_invalid")
    identity = {"run_id": run_id, "event": event, "result": result, **optional, "head_sha": head_sha}
    event_id = stable_key("audit", identity)
    record = {
        "adapter_schema_version": ADAPTER_SCHEMA_VERSION, "event_id": event_id,
        "timestamp": now(), "run_id": run_id, "event": event, "result": result,
        **{key: value for key, value in optional.items() if value is not None},
        **({"head_sha": head_sha} if head_sha else {}),
    }
    path = adapter_root(common_dir) / "adapter-audit.jsonl"
    lock_fd = secure_file(audit_lock_path(common_dir), os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        fd = secure_file(path, os.O_APPEND | os.O_RDWR)
        try:
            if audit_has_event(fd, event_id):
                return
            write_all(fd, (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode())
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
def decision_head(decision: dict[str, Any]) -> str | None:
    git_view = decision.get("evidence", {}).get("git")
    return git_view.get("head_sha") if isinstance(git_view, dict) else None
def inspect_bound(repo: lifecycle.Repo, run_id: str) -> dict[str, Any]:
    return lifecycle.inspect_run(repo.root, run_id)
def precheck_binding(repo: lifecycle.Repo, session_id: str, requested: str | None) -> str | None:
    if not binding_path(repo.common_dir, session_id).exists():
        return requested
    current = load_binding(repo, session_id)
    if load_run_state(repo, current["run_id"])["terminal"] is not None:
        return requested
    if requested is not None and requested != current["run_id"]:
        raise AdapterError(
            "Claude session is already bound to a nonterminal lifecycle run",
            "session_already_bound",
        )
    return current["run_id"]
def halt_unbound_run(repo: lifecycle.Repo, run_id: str, timeout: float) -> None:
    lifecycle.halt_run(
        repo.root, run_id=run_id, status_value="blocked",
        reason="Claude session binding persistence failed",
        key=stable_key("binding-failure", {"run_id": run_id}), timeout=timeout,
    )
def start(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    repo, session_id = require_opt_in(cwd), effective_session(args.session_id)
    payload = {
        "task": args.task, "base_branch": args.base_branch, "base_sha": args.base_sha,
        "intended_branch": args.intended_branch, "owned_paths": sorted(args.owned_paths),
        "worktree": args.worktree, "unit_id": args.work_unit_id, "unit": args.work_unit,
    }
    key = args.idempotency_key or stable_key("start", payload)
    with lifecycle.RepoLock(adapter_lock_path(repo.common_dir), args.lock_timeout):
        run_id = precheck_binding(repo, session_id, args.run_id)
        result = lifecycle.start_run(
            repo.root, run_id=run_id, task=args.task, base_branch=args.base_branch,
            base_sha=args.base_sha, intended_branch=args.intended_branch,
            owned_paths=args.owned_paths, worktree=args.worktree, unit_id=args.work_unit_id,
            unit_description=args.work_unit, key=key, timeout=args.lock_timeout,
        )
        run_id = result["run_id"]
        try:
            _write_binding_locked(repo, session_id, run_id)
        except Exception as exc:
            if not result.get("idempotent"):
                halt_unbound_run(repo, run_id, args.lock_timeout)
            raise AdapterError("Claude session binding could not be persisted", "binding_persist_failed") from exc
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
    run_command([STACK, "create", state["intended_branch"], state["base"]["branch"],
                 "--base-sha", state["base"]["sha"], "--strict"], start_root)
def staged_paths(repo: lifecycle.Repo) -> list[str]:
    raw = lifecycle.git(repo.root, "diff", "--cached", "--name-status", "-z",
                        "--find-renames", text=False).stdout
    return lifecycle.parse_name_status(raw)
def commit_guard(state: dict[str, Any]) -> tuple[str, tuple[str, ...], str, str]:
    unit = lifecycle.current_unit(state)
    ready = unit.get("ready")
    if unit.get("status") != "ready" or not isinstance(ready, dict):
        raise AdapterError("controller did not provide ready commit evidence", "ready_evidence_missing")
    paths = tuple(sorted(ready.get("paths", [])))
    values = (ready.get("head_sha"), paths, ready.get("diff_fingerprint"), ready.get("event_id"))
    if not paths or not all(isinstance(value, str) for value in (values[0], values[2], values[3])):
        raise AdapterError("controller ready evidence is malformed", "ready_evidence_missing")
    return values  # type: ignore[return-value]
def verify_commit_cas(repo: lifecycle.Repo, state: dict[str, Any], decision: dict[str, Any],
    expected: tuple[str, tuple[str, ...], str, str]) -> tuple[lifecycle.Repo, dict[str, Any]]:
    target, actual = action_target(repo, state), commit_guard(state)
    ready = lifecycle.current_unit(state)["ready"]
    observed = tuple(sorted(decision.get("evidence", {}).get("owned_dirty_paths", [])))
    unchanged = (actual == expected and decision.get("action") == "commit"
        and lifecycle.exact_head(target) == expected[0] and observed == expected[1]
        and lifecycle.worktree_fingerprint(target, expected[1]) == expected[2])
    if not unchanged:
        raise AdapterError("ready commit evidence changed after inspection", "commit_cas_failed")
    return target, ready
def action_commit(repo: lifecycle.Repo, state: dict[str, Any], decision: dict[str, Any]) -> None:
    expected = commit_guard(state)
    target, ready = verify_commit_cas(repo, state, decision, expected)
    pathspecs = [f":(literal){path}" for path in expected[1]]
    lifecycle.git(target.root, "add", "-A", "--", *pathspecs)
    if tuple(staged_paths(target)) != expected[1]:
        raise AdapterError("staged paths differ from the exact approved set", "staged_paths_mismatch")
    run_command([VALIDATE, "--json"], target.root)
    current = load_run_state(repo, state["run_id"])
    verify_commit_cas(repo, current, inspect_bound(repo, state["run_id"]), expected)
    if tuple(staged_paths(target)) != expected[1]:
        raise AdapterError("staged paths changed before commit", "commit_cas_failed")
    run_command([COMMIT, "-m", ready["subject"], "-m", ready["body"]], target.root)
def one_remote_url(target: lifecycle.Repo, *args: str) -> str:
    proc = lifecycle.git(target.root, "remote", "get-url", *args, "origin", check=False)
    values = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if proc.returncode or len(values) != 1:
        raise AdapterError("origin URL is missing or ambiguous", "origin_url_ambiguous")
    return values[0]
def action_push(repo: lifecycle.Repo, state: dict[str, Any], decision: dict[str, Any]) -> None:
    target, branch = action_target(repo, state), state["intended_branch"]
    lifecycle.validate_branch(target, branch, intended=True)
    if decision["evidence"]["git"]["branch"] != branch:
        raise AdapterError("refusing to push an unexpected branch", "unexpected_branch")
    if one_remote_url(target, "--all") != one_remote_url(target, "--push", "--all"):
        raise AdapterError("origin push URL differs from fetch URL", "origin_url_mismatch")
    lifecycle.git(target.root, "push", "--set-upstream", "origin", f"HEAD:refs/heads/{branch}")
def repository_identity(target: lifecycle.Repo) -> tuple[str, str]:
    proc = run_command(["gh", "repo", "view", "--json", "nameWithOwner"], target.root, check=False)
    try:
        value = json.loads(proc.stdout)
        name = value["nameWithOwner"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AdapterError("GitHub repository inspection returned malformed data", "repo_data_malformed") from exc
    if proc.returncode or not isinstance(name, str) or name.count("/") != 1:
        raise AdapterError("GitHub repository identity is unavailable", "repo_inspection_failed")
    return name, name.split("/", 1)[0]
def pr_owner(value: dict[str, Any]) -> str | None:
    owner = value.get("headRepositoryOwner")
    return owner.get("login") if isinstance(owner, dict) else owner if isinstance(owner, str) else None
def parse_prs(proc: subprocess.CompletedProcess[str], state: dict[str, Any], head: str,
              repository: str, owner: str) -> list[dict[str, Any]]:
    if proc.returncode:
        raise AdapterError("GitHub PR inspection failed", "pr_inspection_failed")
    try:
        values = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AdapterError("GitHub PR inspection returned malformed data", "pr_data_malformed") from exc
    if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
        raise AdapterError("GitHub PR inspection returned malformed data", "pr_data_malformed")
    candidates = [value for value in values if value.get("headRefName") == state["intended_branch"]
                  and value.get("headRefOid") == head]
    exact = [value for value in candidates if value.get("baseRefName") == state["base"]["branch"]
             and pr_owner(value) == owner]
    if len(exact) != len(candidates):
        raise AdapterError("pull request owner or base does not match the controller", "pr_identity_mismatch")
    if len(exact) > 1:
        raise AdapterError("multiple exact-head pull requests are ambiguous", "pr_ambiguous")
    return [{**value, "repository": repository} for value in exact]
def query_exact_pr(target: lifecycle.Repo, state: dict[str, Any], head: str) -> dict[str, Any] | None:
    repository, owner = repository_identity(target)
    proc = run_command([
        "gh", "pr", "list", "--repo", repository, "--head", state["intended_branch"],
        "--state", "all", "--limit", "100", "--json",
        "number,state,isDraft,headRefOid,headRefName,baseRefName,headRepositoryOwner,url",
    ], target.root, check=False)
    exact = parse_prs(proc, state, head, repository, owner)
    return exact[0] if exact else None
def pr_status(value: dict[str, Any]) -> str:
    state = value.get("state")
    if state == "OPEN":
        return "draft" if value.get("isDraft") is True else "open"
    if state in {"MERGED", "CLOSED"}:
        return state.lower()
    raise AdapterError("pull request state is unknown", "pr_data_malformed")
def pr_snapshot(value: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(value.get(key) for key in (
        "repository", "number", "state", "isDraft", "headRefOid", "headRefName", "baseRefName",
    )) + (pr_owner(value),)
def record_pr(repo: lifecycle.Repo, run_id: str, head: str, value: dict[str, Any]) -> None:
    number, snapshot = value.get("number"), pr_snapshot(value)
    if not isinstance(number, int) or number <= 0:
        raise AdapterError("pull request identity is malformed", "pr_data_malformed")
    metadata = {"number": number, "repository": value["repository"],
                "base": value["baseRefName"], "head": value["headRefName"]}
    lifecycle.record_run(
        repo.root, run_id=run_id, kind="pr", status_value=pr_status(value),
        source="github-pr", sha=head, authoritative=True, receipt_sha=None,
        metadata=metadata, key=stable_key("pr-fact", snapshot), timeout=10,
    )
def action_open_pr(repo: lifecycle.Repo, state: dict[str, Any], decision: dict[str, Any]) -> None:
    target, head = action_target(repo, state), decision_head(decision)
    if head is None:
        raise AdapterError("controller did not provide an exact HEAD", "missing_head")
    pull_request = query_exact_pr(target, state, head)
    if pull_request is None:
        ready = lifecycle.current_unit(state).get("ready")
        if not isinstance(ready, dict) or not isinstance(ready.get("subject"), str):
            raise AdapterError("conventional PR title evidence is missing", "ready_evidence_missing")
        run_command([STACK, "pr", state["intended_branch"], state["base"]["branch"], ready["subject"]], target.root)
        pull_request = query_exact_pr(target, state, head)
    if pull_request is None:
        raise AdapterError("canonical PR creation produced no exact-head PR", "pr_exact_head_missing")
    record_pr(repo, state["run_id"], head, pull_request)
def demote_stage(common_dir: Path, stage: str, run_id: str) -> None:
    if stage not in ACTION_STAGES.values():
        raise AdapterError("invalid demotion stage", "invalid_stage")
    path = common_dir / f"autonomy-demoted-{stage}"
    lifecycle.atomic_json(path, {
        "schema_version": ADAPTER_SCHEMA_VERSION, "stage": stage, "run_id": run_id,
        "demoted_at": now(), "source": "lifecycle_adapter"})
def adapter_result(run_id: str, outcome: str, before: dict[str, Any], *,
    after: dict[str, Any] | None = None, ok: bool = True, **extra: Any) -> dict[str, Any]:
    return {"ok": ok, "enabled": True, "bound": True, "run_id": run_id,
        "outcome": outcome, "before": before, "after": after or before, **extra}
def action_audit(repo: lifecycle.Repo, run_id: str, decision: dict[str, Any], result: str,
    *, stage: str | None = None, reason_code: str | None = None) -> None:
    append_adapter_audit(repo.common_dir, run_id, "action", result, action=decision["action"],
        stage=stage, reason_code=reason_code, head_sha=decision_head(decision))
def decision_token(decision: dict[str, Any]) -> tuple[Any, ...]:
    evidence = decision.get("evidence", {})
    return (decision.get("action"), decision_head(decision), evidence.get("run_revision"),
            tuple(evidence.get("owned_dirty_paths", [])))
def execute_action(repo: lifecycle.Repo, run_id: str, decision: dict[str, Any], state: dict[str, Any],
    action_fn: Callable[[lifecycle.Repo, dict[str, Any], dict[str, Any]], None]) -> dict[str, Any]:
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
    decision, state = fresh, load_run_state(repo, run_id)
    action_audit(repo, run_id, decision, "attempt", stage=stage)
    try:
        action_fn(repo, state, decision)
    except Exception as exc:
        code = exc.code if isinstance(exc, (AdapterError, lifecycle.LifecycleError)) else "action_failed"
        action_audit(repo, run_id, decision, "failure", stage=stage, reason_code=code)
        demote_stage(repo.common_dir, stage, run_id)
        after = inspect_bound(repo, run_id)
        if decision["action"] == "create_stack" and after.get("action") != "create_stack":
            lifecycle.halt_run(
                repo.root, run_id=run_id, status_value="blocked",
                reason="Strict stack creation failed after the worktree appeared",
                key=stable_key("strict-stack-failure", {"run_id": run_id}), timeout=10,
            )
            after = inspect_bound(repo, run_id)
        return adapter_result(
            run_id, "action_failed", decision, after=after,
            ok=False, stage=stage, reason_code=code,
        )
    action_audit(repo, run_id, decision, "success", stage=stage)
    return adapter_result(run_id, "advanced", decision, after=inspect_bound(repo, run_id), stage=stage)
def watcher_paths(common_dir: Path, run_id: str, sha: str) -> tuple[Path, Path, Path, Path]:
    safe_run = hashlib.sha256(run_id.encode()).hexdigest()
    root = adapter_root(common_dir) / "watchers" / safe_run
    return (root / f"{sha}.json", root / f"{sha}.spawn.lock",
            root / f"{sha}.execution.lock", root / f"{sha}.ready.json")
def write_watcher_marker(path: Path, run_id: str, sha: str, status: str, pid: int | None) -> None:
    lifecycle.atomic_json(path, {
        "schema_version": ADAPTER_SCHEMA_VERSION, "run_id": run_id, "sha": sha,
        "status": status, "pid": pid, "updated_at": now(),
    })
def child_ready(path: Path, proc: subprocess.Popen[Any]) -> bool:
    deadline = time.monotonic() + WATCHER_READY_TIMEOUT
    while time.monotonic() < deadline:
        if path.exists():
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.02)
    return False
def stop_unready_child(proc: subprocess.Popen[Any]) -> None:
    try:
        proc.terminate()
        proc.wait(timeout=1)
    except (OSError, subprocess.SubprocessError):
        pass
def spawn_watcher(repo: lifecycle.Repo, run_id: str, sha: str) -> dict[str, Any]:
    marker, spawn_lock, _, ready = watcher_paths(repo.common_dir, run_id, sha)
    fd = secure_file(spawn_lock, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if marker.exists():
            read_json(marker, "watcher_state_invalid")
            return {"started": False, "duplicate": True, "sha": sha}
        ready.unlink(missing_ok=True)
        write_watcher_marker(marker, run_id, sha, "starting", None)
        try:
            proc = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "watch",
                 "--run-id", run_id, "--sha", sha], cwd=str(repo.root),
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True,
            )
        except OSError as exc:
            write_watcher_marker(marker, run_id, sha, "failed", None)
            raise AdapterError("unable to start detached CI watcher", "watcher_spawn_failed") from exc
        write_watcher_marker(marker, run_id, sha, "starting", proc.pid)
        if not child_ready(ready, proc):
            stop_unready_child(proc)
            write_watcher_marker(marker, run_id, sha, "failed", proc.pid)
            raise AdapterError("detached CI watcher did not become ready", "watcher_not_ready")
        return {"started": True, "duplicate": False, "sha": sha}
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
def tick_locked(repo: lifecycle.Repo, run_id: str) -> dict[str, Any]:
    decision, state = inspect_bound(repo, run_id), load_run_state(repo, run_id)
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
        return adapter_result(run_id, "watching", decision,
                              after=inspect_bound(repo, run_id), watcher=watcher)
    if action in PROHIBITED_ACTIONS:
        action_audit(repo, run_id, decision, "approval_required", reason_code="action_deferred")
        return adapter_result(run_id, "approval_required", decision, reason_code="action_deferred")
    outcome = "done" if action == "done" else "blocked" if action == "blocked" else "idle"
    return adapter_result(run_id, outcome, decision, ok=action != "blocked")
def tick(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    session_id = effective_session(args.session_id)
    repo, binding, _ = bound_state(cwd, session_id, args.run_id)
    run_id, timeout = binding["run_id"], getattr(args, "lock_timeout", 10)
    with lifecycle.RepoLock(action_lock_path(repo.common_dir, run_id), timeout):
        repo, current, _ = bound_state(cwd, session_id, args.run_id)
        if current["run_id"] != run_id:
            raise AdapterError("Claude session binding changed during tick", "run_binding_mismatch")
        return tick_locked(repo, run_id)
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
def required_checks(target: lifecycle.Repo, number: int) -> tuple[str, dict[str, Any]]:
    proc = run_command([
        "gh", "pr", "checks", str(number), "--required", "--json", "name,state,bucket",
    ], target.root, check=False)
    try:
        checks = json.loads(proc.stdout)
    except json.JSONDecodeError:
        checks = None
    status_value, metadata = classify_required_checks(checks)
    if proc.returncode:
        status_value = "unknown"
        metadata["command_status"] = "nonzero"
    metadata["pr_number"] = number
    return status_value, metadata
def record_ci(repo: lifecycle.Repo, run_id: str, sha: str,
              status_value: str, metadata: dict[str, Any]) -> None:
    lifecycle.record_run(
        repo.root, run_id=run_id, kind="ci", status_value=status_value,
        source="github-required-checks", sha=sha, authoritative=True, receipt_sha=None,
        metadata=metadata, key=stable_key(
            "ci-fact", {"head": sha, "status": status_value, "metadata": metadata}), timeout=10,
    )
    append_adapter_audit(repo.common_dir, run_id, "ci_reconcile", status_value,
                         action="wait_ci", head_sha=sha)
def observe_pr(target: lifecycle.Repo, state: dict[str, Any], sha: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return query_exact_pr(target, state, sha), None
    except AdapterError as exc:
        return None, exc.code
def reconcile_ci(repo: lifecycle.Repo, run_id: str, expected_sha: str) -> dict[str, Any]:
    state = load_run_state(repo, run_id)
    target = action_target(repo, state)
    if lifecycle.exact_head(target) != expected_sha:
        return {"ok": True, "outcome": "stale", "status": "unknown", "sha": expected_sha}
    pull_request, query_error = observe_pr(target, state, expected_sha)
    metadata: dict[str, Any] = {"required_count": 0, "check_names": []}
    check_status = "unknown"
    if query_error:
        metadata["reason_code"] = query_error
    elif pull_request is not None:
        record_pr(repo, run_id, expected_sha, pull_request)
        number = pull_request.get("number")
        if isinstance(number, int) and number > 0 and pr_status(pull_request) == "open":
            check_status, metadata = required_checks(target, number)
        if check_status == "passing":
            confirmed, confirm_error = observe_pr(target, state, expected_sha)
            if confirmed is not None:
                record_pr(repo, run_id, expected_sha, confirmed)
            stable = confirmed is not None and pr_snapshot(confirmed) == pr_snapshot(pull_request)
            if confirm_error or not stable or pr_status(confirmed) != "open":
                check_status, metadata = "unknown", {"required_count": 0, "check_names": [],
                                                     "reason_code": confirm_error or "pr_changed"}
    record_ci(repo, run_id, expected_sha, check_status, metadata)
    return {
        "ok": True, "outcome": "terminal" if check_status in {"passing", "failed"} else "pending",
        "status": check_status, "sha": expected_sha, "decision": inspect_bound(repo, run_id),
        "degraded": bool(query_error or metadata.get("command_status")),
    }
def update_watcher_marker(repo: lifecycle.Repo, run_id: str, sha: str, status_value: str) -> None:
    marker, _, _, _ = watcher_paths(repo.common_dir, run_id, sha)
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
def watcher_delay(interval: float, failures: int) -> float:
    return min(interval * (2 ** min(failures, 3)), max(interval, 120.0))
def watch(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    repo = require_opt_in(cwd)
    lifecycle.validate_name(args.run_id, lifecycle.RUN_ID_RE, "run id")
    lifecycle.validate_oid(args.sha)
    if args.max_polls < 1:
        raise AdapterError("watcher poll budget must be positive", "watcher_budget_invalid")
    state = load_run_state(repo, args.run_id)
    if state["repository"]["git_common_dir"] != str(repo.common_dir):
        raise AdapterError("watch run belongs to another repository", "binding_repository_mismatch")
    _, _, execution_lock, ready = watcher_paths(repo.common_dir, args.run_id, args.sha)
    fd = secure_file(execution_lock, os.O_RDWR)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"ok": True, "outcome": "duplicate", "sha": args.sha}
        update_watcher_marker(repo, args.run_id, args.sha, "running")
        lifecycle.atomic_json(ready, {"schema_version": ADAPTER_SCHEMA_VERSION,
                                      "status": "ready", "pid": os.getpid()})
        failures = 0
        for poll in range(1, args.max_polls + 1):
            result = safe_reconcile_ci(repo, args.run_id, args.sha)
            if result["outcome"] in {"terminal", "stale"} or args.once:
                update_watcher_marker(repo, args.run_id, args.sha, result["outcome"])
                return result
            failures = failures + 1 if not result.get("ok") or result.get("degraded") else 0
            if poll == args.max_polls:
                update_watcher_marker(repo, args.run_id, args.sha, "timeout")
                return {**result, "outcome": "timeout"}
            time.sleep(watcher_delay(args.interval, failures))
        raise AdapterError("watcher poll budget is invalid", "watcher_budget_invalid")
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
                if key in {"file_path", "notebook_path", "path"} and isinstance(nested, str):
                    paths.append(nested)
                elif key in {"edits", "files"}:
                    collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)
    collect(tool_input)
    return list(dict.fromkeys(paths))
def hook_repo(payload: dict[str, Any], cwd: Path) -> tuple[str, lifecycle.Repo | None]:
    candidate = payload.get("cwd")
    root = Path(candidate) if isinstance(candidate, str) and candidate else cwd
    try:
        repo = lifecycle.discover_repo(root)
    except Exception:
        return "disabled", None
    return lifecycle_mode(repo.root), repo
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
def shell_segments(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split, lexer.commenters = True, ""
    segments: list[list[str]] = [[]]
    for token in lexer:
        if token and all(character in ";&|()" for character in token):
            segments.append([])
        else:
            segments[-1].append(token)
    return [segment for segment in segments if segment]
def command_start(tokens: list[str]) -> int:
    index = 0
    while index < len(tokens) and ("=" in tokens[index] and not tokens[index].startswith(("/", "./"))):
        index += 1
    while index < len(tokens) and Path(tokens[index]).name in {"command", "env", "sudo"}:
        index += 1
        while index < len(tokens) and (tokens[index].startswith("-") or "=" in tokens[index]):
            takes_value = tokens[index] in {"-u", "--unset", "-C", "--chdir"}
            index += 2 if takes_value else 1
    return index
def git_subcommand(tokens: list[str], index: int) -> str | None:
    index += 1
    options_with_values = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
    while index < len(tokens):
        token = tokens[index]
        if token in options_with_values:
            index += 2
        elif token.startswith("-"):
            index += 1
        else:
            return token
    return None
def segment_mutates(tokens: list[str], depth: int) -> bool:
    index = command_start(tokens)
    if index >= len(tokens):
        return False
    executable = Path(tokens[index]).name
    adapter_call = executable == "lifecycle_adapter.py" or (
        executable.startswith("python") and index + 1 < len(tokens)
        and Path(tokens[index + 1]).name == "lifecycle_adapter.py"
    )
    if adapter_call:
        return False
    if executable == "git":
        return git_subcommand(tokens, index) in {"add", "commit", "push"}
    if executable == "gh":
        return bool(re.search(r"(?:^|\s)pr\s+(?:create|edit|merge)(?:\s|$)", " ".join(tokens[index + 1:])))
    if executable == "stack" or tokens[index].endswith("/.claude/scripts/stack"):
        return len(tokens) > index + 1 and tokens[index + 1] in {"create", "pr", "merge", "clean", "update"}
    if depth < 2 and executable in {"bash", "sh", "zsh"} and "-c" in tokens[index + 1:]:
        position = tokens.index("-c", index + 1)
        return position + 1 < len(tokens) and direct_lifecycle_mutation(tokens[position + 1], depth + 1)
    return False
def direct_lifecycle_mutation(command: str, depth: int = 0) -> bool:
    try:
        return any(segment_mutates(segment, depth) for segment in shell_segments(command))
    except ValueError:
        return bool(re.search(r"(?:^|[;&|]\s*)(?:git\s+(?:add|commit|push)|gh\s+pr\s+(?:create|edit|merge))\b", command))
def bash_hook(payload: dict[str, Any]) -> dict[str, Any] | None:
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if isinstance(command, str) and direct_lifecycle_mutation(command):
        return deny("Direct lifecycle mutation is blocked; invoke lifecycle_adapter.py instead.")
    return None
def owned_path_gate(
    payload: dict[str, Any], repo: lifecycle.Repo, target: lifecycle.Repo,
    state: dict[str, Any], run_id: str, decision: dict[str, Any],
) -> dict[str, Any] | None:
    raw_paths = hook_paths(payload)
    if not raw_paths:
        audit_hook(repo, run_id, "deny", "write_path_missing", decision)
        return deny("Write tool input does not identify a path inside the run-owned boundary.")
    for raw in raw_paths:
        candidate = Path(raw).expanduser()
        candidate = candidate if candidate.is_absolute() else repo.root / candidate
        try:
            relative = candidate.resolve(strict=False).relative_to(target.root.resolve()).as_posix()
        except ValueError:
            audit_hook(repo, run_id, "deny", "path_outside_worktree", decision)
            return deny("Write path is outside the lifecycle run worktree.")
        if not lifecycle.owns(relative, state["owned_paths"]):
            audit_hook(repo, run_id, "deny", "path_not_owned", decision)
            return deny("Write path is outside the lifecycle run-owned boundary.")
    audit_hook(repo, run_id, "allow", "editing_state_valid", decision)
    return None
def hook_pre_write(
    payload: dict[str, Any], repo: lifecycle.Repo, session_id: str,
) -> dict[str, Any] | None:
    tool_name = payload.get("tool_name")
    if tool_name == "Bash":
        return bash_hook(payload)
    if tool_name not in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
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
    return owned_path_gate(payload, repo, target, state, run_id, decision)
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
def deferred_stop_first(
    repo: lifecycle.Repo, run_id: str, session_id: str, action: str, head: str | None,
) -> bool:
    identity = {"run_id": run_id, "session": session_key(session_id), "action": action, "head": head}
    name = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    path = adapter_root(repo.common_dir) / "stop-notices" / f"{name}.json"
    fd = secure_file(path.with_suffix(".lock"), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if path.exists():
            return False
        lifecycle.atomic_json(path, {"schema_version": ADAPTER_SCHEMA_VERSION, **identity,
                                     "notice": "deferred action remains unexecuted"})
        return True
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
def hook_stop(repo: lifecycle.Repo, session_id: str) -> dict[str, Any] | None:
    try:
        binding = load_binding(repo, session_id)
    except AdapterError as exc:
        if exc.code == "run_unbound":
            return {"lifecycle_bound": False}
        raise
    args = argparse.Namespace(session_id=session_id, run_id=binding["run_id"])
    try:
        value = tick(args, repo.root)
    except Exception as exc:
        code = exc.code if isinstance(exc, (AdapterError, lifecycle.LifecycleError)) else "tick_failed"
        audit_hook(repo, binding["run_id"], "block", code)
        return {"decision": "block", "reason": f"Lifecycle tick failed closed: {code}",
                "lifecycle_bound": True}
    after, outcome = value.get("after", {}), value.get("outcome")
    action = after.get("action", "blocked")
    if outcome == "done" or action == "done" or outcome == "watching":
        reason = "watcher_detached" if outcome == "watching" else "terminal_done"
        audit_hook(repo, binding["run_id"], "allow", reason, after)
        return {"lifecycle_bound": True}
    if action in PROHIBITED_ACTIONS and not deferred_stop_first(
            repo, binding["run_id"], session_id, action, decision_head(after)):
        audit_hook(repo, binding["run_id"], "allow", "deferred_notice_recorded", after)
        return {"lifecycle_bound": True}
    audit_hook(repo, binding["run_id"], "block",
               value.get("reason_code", "lifecycle_incomplete"), after)
    return {"decision": "block", "reason": stop_reason(value), "lifecycle_bound": True}
def hook_failure(event: str) -> dict[str, Any] | None:
    if event == "PreToolUse":
        return deny("Lifecycle pre-write inspection failed closed.")
    if event == "Stop":
        return {"decision": "block", "reason": "Lifecycle Stop inspection failed closed.",
                "lifecycle_bound": True}
    if event in {"SessionStart", "UserPromptSubmit"}:
        return {"hookSpecificOutput": {"hookEventName": event, "additionalContext":
                "Lifecycle inspection failed closed; repair lifecycle state before mutation."}}
    return None
def dispatch_hook_event(event: str, payload: dict[str, Any], repo: lifecycle.Repo,
                        session_id: str) -> dict[str, Any] | None:
    if event == "PreToolUse":
        return hook_pre_write(payload, repo, session_id)
    if event in {"SessionStart", "UserPromptSubmit"}:
        return hook_context(event, repo, session_id)
    return hook_stop(repo, session_id) if event == "Stop" else None
def malformed_hook(args: argparse.Namespace, cwd: Path) -> dict[str, Any] | None:
    mode, _ = hook_repo({}, cwd)
    return hook_failure(args.event) if mode in {"enabled", "error"} else None
def hook(args: argparse.Namespace, cwd: Path, raw: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return malformed_hook(args, cwd)
    if not isinstance(payload, dict):
        return malformed_hook(args, cwd)
    mode, repo = hook_repo(payload, cwd)
    if mode == "disabled" or repo is None:
        return None
    if mode == "error":
        return hook_failure(args.event)
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
    watch_parser.add_argument("--max-polls", type=int, default=WATCHER_DEFAULT_POLLS)
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
