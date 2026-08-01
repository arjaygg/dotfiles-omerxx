#!/usr/bin/env python3
"""Deterministic git lifecycle state and decision controller."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Sequence


SCHEMA_VERSION = 2
AUDIT_SCHEMA_VERSION = 1
STATE_DIR = "agent-lifecycle"
BRANCH_PREFIXES = ("feature", "feat", "bugfix", "fix", "hotfix", "release", "chore")
TRUNK_BRANCHES = frozenset({"main", "master", "trunk", "develop", "development"})
FACT_KINDS = frozenset({"pr", "ci", "merge", "sync"})
SUCCESS_RECEIPT = {"merge": "merged", "sync": "synced"}
RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
SOURCE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
OID_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
SUBJECT_RE = re.compile(
    r"(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(?:\([A-Za-z0-9._/-]+\))?!?: [^\s].{2,}\Z"
)
PLACEHOLDER_BODIES = frozenset({"n/a", "none", "todo", "tbd", "no body", "changes"})
STATUS_ALIASES = {
    "pr": {"open": "open", "ready": "open", "draft": "draft", "closed": "closed", "merged": "merged"},
    "ci": {
        "pending": "pending", "queued": "pending", "running": "pending",
        "in_progress": "pending", "passing": "passing", "passed": "passing",
        "success": "passing", "green": "passing", "failed": "failed",
        "failure": "failed", "cancelled": "failed", "canceled": "failed",
        "timed_out": "failed", "unknown": "unknown", "skipped": "unknown",
    },
    "merge": {"pending": "pending", "merged": "merged", "success": "merged",
              "succeeded": "merged", "failed": "failed", "failure": "failed"},
    "sync": {"pending": "pending", "synced": "synced", "success": "synced",
             "succeeded": "synced", "failed": "failed", "failure": "failed"},
}


class LifecycleError(RuntimeError):
    def __init__(self, message: str, code: str = "lifecycle_error"):
        super().__init__(message)
        self.code = code


class LockTimeoutError(LifecycleError):
    def __init__(self, message: str):
        super().__init__(message, "lock_timeout")


@dataclass(frozen=True)
class Repo:
    root: Path
    git_dir: Path
    common_dir: Path


@dataclass(frozen=True)
class Worktree:
    path: Path
    branch: str | None
    head: str | None
    prunable: bool = False


@dataclass
class GitView:
    repo: Repo
    mode: str
    branch: str | None
    head: str | None
    upstream: str | None
    upstream_sha: str | None
    base_sha: str | None
    intended_sha: str | None
    ahead: int | None
    behind: int | None
    staged: list[str]
    unstaged: list[str]
    untracked: list[str]
    conflicts: list[str]
    changed: list[str]
    operations: list[str]

    def evidence(self) -> dict[str, Any]:
        return {
            "root": str(self.repo.root), "git_dir": str(self.repo.git_dir),
            "common_dir": str(self.repo.common_dir), "mode": self.mode,
            "branch": self.branch, "head_sha": self.head,
            "upstream": {"name": self.upstream, "sha": self.upstream_sha,
                         "ahead": self.ahead, "behind": self.behind},
            "base_sha": self.base_sha, "intended_branch_sha": self.intended_sha,
            "staged_paths": self.staged, "unstaged_paths": self.unstaged,
            "untracked_paths": self.untracked, "conflict_paths": self.conflicts,
            "changed_paths": self.changed, "active_operations": self.operations,
            "clean": not self.changed,
        }


@dataclass
class DecisionContext:
    state: dict[str, Any]
    view: GitView
    unit: dict[str, Any]
    owned_dirty: list[str]
    foreign_dirty: list[str]
    details: dict[str, Any] = field(default_factory=dict)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode()).hexdigest()


def git(
    cwd: Path | str,
    *args: str,
    check: bool = True,
    text: bool = True,
    input_data: bytes | str | None = None,
) -> subprocess.CompletedProcess[Any]:
    env = os.environ.copy()
    env.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"})
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), env=env, input=input_data,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text, check=False,
    )
    if check and proc.returncode:
        error = proc.stderr if text else proc.stderr.decode("utf-8", "replace")
        raise LifecycleError(
            f"git {' '.join(args)} failed: {error.strip()}", "git_error"
        )
    return proc


def discover_repo(cwd: Path | str) -> Repo:
    cwd = Path(cwd).expanduser().resolve()
    proc = git(
        cwd, "rev-parse", "--path-format=absolute", "--show-toplevel",
        "--git-dir", "--git-common-dir", check=False,
    )
    lines = proc.stdout.splitlines() if proc.returncode == 0 else []
    if len(lines) == 3:
        return Repo(*(Path(item).resolve() for item in lines))
    root = Path(git(cwd, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    git_dir = Path(git(cwd, "rev-parse", "--absolute-git-dir").stdout.strip()).resolve()
    raw_common = Path(git(cwd, "rev-parse", "--git-common-dir").stdout.strip())
    common = raw_common.resolve() if raw_common.is_absolute() else (cwd / raw_common).resolve()
    return Repo(root, git_dir, common)


def exact_head(repo: Repo) -> str:
    value = git(repo.root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    return validate_oid(value)


def resolve_ref(repo: Repo, ref: str | None) -> str | None:
    if not ref:
        return None
    proc = git(repo.root, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}", check=False)
    value = proc.stdout.strip()
    return value if proc.returncode == 0 and OID_RE.fullmatch(value) else None


def is_ancestor(repo: Repo, ancestor: str, descendant: str) -> bool:
    return git(repo.root, "merge-base", "--is-ancestor", ancestor, descendant, check=False).returncode == 0


def validate_oid(value: str, length: int | None = None) -> str:
    if not isinstance(value, str) or not OID_RE.fullmatch(value):
        raise LifecycleError("SHA must be an exact lowercase 40- or 64-character object id", "invalid_sha")
    if length is not None and len(value) != length:
        raise LifecycleError("SHA length does not match this repository", "invalid_sha")
    return value


def validate_name(value: str, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise LifecycleError(f"invalid {label}", f"invalid_{label.replace(' ', '_')}")
    return value


def validate_branch(repo: Repo, branch: str, intended: bool = False) -> str:
    if not isinstance(branch, str) or branch != branch.strip() or branch.startswith(("refs/", "-")):
        raise LifecycleError("branch must be a short local branch name", "invalid_branch")
    if git(repo.root, "check-ref-format", "--branch", branch, check=False).returncode:
        raise LifecycleError(f"invalid branch name: {branch}", "invalid_branch")
    if intended:
        prefix, slash, suffix = branch.partition("/")
        if slash != "/" or prefix not in BRANCH_PREFIXES or not suffix:
            expected = ", ".join(f"{item}/" for item in BRANCH_PREFIXES)
            raise LifecycleError(f"intended branch must use: {expected}", "invalid_branch")
    return branch


def normalize_paths(values: Sequence[str], root: Path) -> list[str]:
    if not values:
        raise LifecycleError("at least one owned path is required", "invalid_owned_path")
    result: list[str] = []
    seen: set[str] = set()
    root = root.resolve()
    for raw in values:
        windows = PureWindowsPath(raw)
        if not raw or raw != raw.strip() or "\x00" in raw:
            raise LifecycleError("owned paths may not be empty or padded", "invalid_owned_path")
        if Path(raw).is_absolute() or PurePosixPath(raw).is_absolute() or windows.is_absolute() or windows.drive:
            raise LifecycleError(f"owned path must be repository-relative: {raw}", "invalid_owned_path")
        if "\\" in raw or ".." in PurePosixPath(raw).parts:
            raise LifecycleError(f"owned path may not escape the repository: {raw}", "invalid_owned_path")
        path = str(PurePosixPath(raw))
        if path in {"", "."} or any(part.lower() == ".git" for part in PurePosixPath(path).parts):
            raise LifecycleError(f"owned path may not address the root or .git: {raw}", "invalid_owned_path")
        try:
            (root / path).resolve(strict=False).relative_to(root)
        except ValueError as exc:
            raise LifecycleError(f"owned path escapes the worktree: {raw}", "invalid_owned_path") from exc
        if path in seen:
            raise LifecycleError(f"duplicate owned path: {path}", "invalid_owned_path")
        seen.add(path)
        result.append(path)
    return sorted(result)


def owns(path: str, owned: Sequence[str]) -> bool:
    return any(path == item or path.startswith(f"{item}/") for item in owned)


def locations(common: Path, run_id: str) -> tuple[Path, Path, Path]:
    validate_name(run_id, RUN_ID_RE, "run id")
    root = common / STATE_DIR
    return root / "runs" / f"{run_id}.json", root / "audit.jsonl", root / "repository.lock"


class RepoLock:
    def __init__(self, path: Path, timeout: float):
        self.path, self.timeout, self.fd = path, max(timeout, 0), None

    def __enter__(self) -> "RepoLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(self.fd)
                    self.fd = None
                    raise LockTimeoutError(f"timed out acquiring lifecycle lock: {self.path}")
                time.sleep(min(0.025, max(0, deadline - time.monotonic())))

    def __exit__(self, *_: Any) -> None:
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)


def load_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise LifecycleError(f"run does not exist: {path.stem}", "run_not_found") from exc
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise LifecycleError(f"run state is unreadable: {exc}", "invalid_state") from exc
    if not isinstance(value, dict):
        raise LifecycleError("run state root must be an object", "invalid_state")
    return value


def require(mapping: dict[str, Any], key: str, kind: type, where: str) -> Any:
    value = mapping.get(key)
    if not isinstance(value, kind):
        raise LifecycleError(f"{where}.{key} has an invalid type", "invalid_state")
    return value


def validate_state(state: dict[str, Any], run_id: str) -> None:
    if state.get("schema_version") != SCHEMA_VERSION or state.get("run_id") != run_id:
        raise LifecycleError("run schema or filename identity is invalid", "invalid_state")
    repository = require(state, "repository", dict, "state")
    require(repository, "start_worktree", str, "repository")
    require(repository, "git_common_dir", str, "repository")
    base = require(state, "base", dict, "state")
    require(base, "branch", str, "base")
    validate_oid(require(base, "sha", str, "base"))
    require(state, "intended_branch", str, "state")
    owned = require(state, "owned_paths", list, "state")
    if not owned or any(not isinstance(item, str) for item in owned):
        raise LifecycleError("state.owned_paths is invalid", "invalid_state")
    units = require(state, "work_units", list, "state")
    if not units or any(not isinstance(item, dict) for item in units):
        raise LifecycleError("state.work_units is invalid", "invalid_state")
    ids: set[str] = set()
    for unit in units:
        unit_id = require(unit, "id", str, "work_unit")
        validate_oid(require(unit, "base_head_sha", str, "work_unit"))
        if unit_id in ids or unit.get("status") not in {"editing", "ready", "consumed"}:
            raise LifecycleError("work unit identity or status is invalid", "invalid_state")
        ids.add(unit_id)
        if unit["status"] == "ready" and not isinstance(unit.get("ready"), dict):
            raise LifecycleError("ready work unit lacks readiness evidence", "invalid_state")
        if unit["status"] == "consumed" and not isinstance(unit.get("consumed"), dict):
            raise LifecycleError("consumed work unit lacks a receipt", "invalid_state")
    if state.get("current_unit_id") not in ids:
        raise LifecycleError("current work unit is missing", "invalid_state")
    require(state, "facts", list, "state")
    require(state, "events", list, "state")
    require(state, "idempotency", dict, "state")
    require(state, "revision", int, "state")
    terminal = state.get("terminal")
    if terminal is not None and (
        not isinstance(terminal, dict) or terminal.get("status") not in {"done", "blocked"}
    ):
        raise LifecycleError("terminal state is invalid", "invalid_state")


def current_unit(state: dict[str, Any]) -> dict[str, Any]:
    unit_id = state["current_unit_id"]
    for unit in state["work_units"]:
        if unit["id"] == unit_id:
            return unit
    raise LifecycleError("current work unit is missing", "invalid_state")


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def audit_event(event: dict[str, Any]) -> dict[str, Any]:
    return {"audit_schema_version": AUDIT_SCHEMA_VERSION, **event}


def read_audit(path: Path) -> tuple[list[dict[str, Any]], bool, int]:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return [], False, 0
    newline = data.rfind(b"\n")
    complete_end = newline + 1 if newline >= 0 else 0
    complete, tail = data[:complete_end], data[complete_end:]
    events: list[dict[str, Any]] = []
    for number, line in enumerate(complete.splitlines(), 1):
        if not line:
            raise LifecycleError(f"audit line {number} is empty", "audit_invalid")
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise LifecycleError(f"audit line {number} is invalid JSON", "audit_invalid") from exc
        if not isinstance(value, dict) or not isinstance(value.get("event_id"), str):
            raise LifecycleError(f"audit line {number} is malformed", "audit_invalid")
        events.append(value)
    return events, bool(tail), complete_end


def append_audit(path: Path, events: Sequence[dict[str, Any]]) -> None:
    if not events:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    data = b"".join(
        (json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
        for event in events
    )
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        offset = 0
        while offset < len(data):
            written = os.write(fd, data[offset:])
            if written <= 0:
                raise OSError("audit append made no progress")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)


def reconcile_audit(state: dict[str, Any], path: Path, repair: bool) -> None:
    expected = [audit_event(item) for item in state["events"]]
    all_events, incomplete, complete_end = read_audit(path)
    identifiers = [item["event_id"] for item in all_events]
    if len(identifiers) != len(set(identifiers)):
        raise LifecycleError("audit contains duplicate event IDs", "audit_invalid")
    actual = [item for item in all_events if item.get("run_id") == state["run_id"]]
    if len(actual) > len(expected):
        raise LifecycleError("audit contains events absent from state", "audit_invalid")
    for index, observed in enumerate(actual):
        if observed != expected[index]:
            raise LifecycleError(f"audit diverges at event {index + 1}", "audit_invalid")
    if not repair and (incomplete or len(actual) != len(expected)):
        raise LifecycleError("audit is incomplete relative to state", "audit_inconsistent")
    if not repair:
        return
    if incomplete:
        with path.open("r+b") as handle:
            handle.truncate(complete_end)
            handle.flush()
            os.fsync(handle.fileno())
    append_audit(path, expected[len(actual):])


def reconcile_runs(
    runs_dir: Path, audit_path: Path, repair: bool
) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for path in sorted(runs_dir.glob("*.json")):
        state = load_state(path)
        validate_state(state, path.stem)
        reconcile_audit(state, audit_path, repair)
        states[path.stem] = state
    return states


def event_id(run_id: str, operation: str, key: str, payload_digest: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{run_id}\0{operation}\0{key}\0{payload_digest}"))


def idempotent(
    state: dict[str, Any], operation: str, key: str, payload_digest: str
) -> dict[str, Any] | None:
    prior = state["idempotency"].get(key)
    if prior is None:
        return None
    if prior.get("operation") != operation or prior.get("digest") != payload_digest:
        raise LifecycleError("idempotency key was reused with a different payload", "idempotency_conflict")
    return {
        "ok": True, "run_id": state["run_id"], "operation": operation,
        "event_id": prior["event_id"], "revision": state["revision"], "idempotent": True,
    }


def apply_event(
    state: dict[str, Any],
    operation: str,
    key: str,
    payload: dict[str, Any],
    update: Callable[[dict[str, Any], str, str], None],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    payload_digest = digest(payload)
    duplicate = idempotent(state, operation, key, payload_digest)
    if duplicate:
        return state, {}, duplicate
    changed = copy.deepcopy(state)
    timestamp = now()
    identifier = event_id(state["run_id"], operation, key, payload_digest)
    update(changed, timestamp, identifier)
    event = {
        "schema_version": SCHEMA_VERSION, "sequence": len(changed["events"]) + 1,
        "event_id": identifier, "run_id": changed["run_id"], "operation": operation,
        "timestamp": timestamp, "idempotency_key": key,
        "payload_digest": payload_digest, "payload": payload,
        "revision": changed["revision"] + 1,
    }
    changed["events"].append(event)
    changed["idempotency"][key] = {
        "operation": operation, "digest": payload_digest, "event_id": identifier,
    }
    changed["revision"] += 1
    changed["updated_at"] = timestamp
    return changed, event, None


def persist(state_path: Path, audit_path: Path, state: dict[str, Any], event: dict[str, Any]) -> None:
    atomic_json(state_path, state)
    append_audit(audit_path, [audit_event(event)])


def mutate(
    cwd: Path | str,
    run_id: str,
    operation: str,
    key: str,
    payload: dict[str, Any],
    update: Callable[[dict[str, Any], str, str, Repo], None],
    timeout: float,
) -> dict[str, Any]:
    repo = discover_repo(cwd)
    validate_name(run_id, RUN_ID_RE, "run id")
    validate_name(key, KEY_RE, "idempotency key")
    state_path, audit_path, lock_path = locations(repo.common_dir, run_id)
    with RepoLock(lock_path, timeout):
        states = reconcile_runs(state_path.parent, audit_path, repair=True)
        state = states.get(run_id)
        if state is None:
            raise LifecycleError(f"run does not exist: {run_id}", "run_not_found")

        def wrapped(changed: dict[str, Any], timestamp: str, identifier: str) -> None:
            update(changed, timestamp, identifier, repo)

        changed, event, duplicate = apply_event(state, operation, key, payload, wrapped)
        if duplicate:
            return duplicate
        persist(state_path, audit_path, changed, event)
    return {
        "ok": True, "run_id": run_id, "operation": operation,
        "event_id": event["event_id"], "revision": changed["revision"], "idempotent": False,
    }


def parse_worktrees(raw: bytes) -> list[Worktree]:
    result: list[Worktree] = []
    current: dict[str, Any] = {}
    for field in raw.split(b"\0"):
        if not field:
            if current:
                result.append(
                    Worktree(
                        Path(current["worktree"]).resolve(),
                        current.get("branch"), current.get("HEAD"), current.get("prunable", False),
                    )
                )
                current = {}
            continue
        key, _, value = field.partition(b" ")
        name, text = key.decode(), value.decode("utf-8", "surrogateescape")
        if name == "worktree" and current:
            result.append(
                Worktree(
                    Path(current["worktree"]).resolve(),
                    current.get("branch"), current.get("HEAD"), current.get("prunable", False),
                )
            )
            current = {}
        if name == "branch":
            current[name] = text.removeprefix("refs/heads/")
        elif name == "prunable":
            current[name] = True
        elif name in {"worktree", "HEAD"}:
            current[name] = text
    if current:
        result.append(
            Worktree(
                Path(current["worktree"]).resolve(),
                current.get("branch"), current.get("HEAD"), current.get("prunable", False),
            )
        )
    return result


def list_worktrees(repo: Repo) -> list[Worktree]:
    raw = git(repo.root, "worktree", "list", "--porcelain", "-z", text=False).stdout
    return parse_worktrees(raw)


def target_repo(state: dict[str, Any], invocation: Repo) -> tuple[Repo, str]:
    intended = state["intended_branch"]
    candidates = [item for item in list_worktrees(invocation) if item.branch == intended]
    if len(candidates) > 1:
        raise LifecycleError("intended branch has multiple registered worktrees", "ambiguous_worktree")
    if candidates:
        candidate = candidates[0]
        if candidate.prunable or not candidate.path.is_dir():
            raise LifecycleError("intended branch worktree is missing or prunable", "missing_worktree")
        repo = discover_repo(candidate.path)
        if str(repo.common_dir) != state["repository"]["git_common_dir"]:
            raise LifecycleError("intended worktree belongs to another repository", "worktree_common_mismatch")
        return repo, "intended"
    start = Path(state["repository"]["start_worktree"])
    if not start.is_dir():
        raise LifecycleError("starting worktree is missing or pruned", "missing_worktree")
    repo = discover_repo(start)
    if str(repo.common_dir) != state["repository"]["git_common_dir"]:
        raise LifecycleError("starting worktree belongs to another repository", "worktree_common_mismatch")
    return repo, "base"


def parse_status(raw: bytes) -> dict[str, Any]:
    records = raw.split(b"\0")
    headers: dict[str, str] = {}
    groups = {name: set() for name in ("staged", "unstaged", "untracked", "conflicts", "changed")}
    index = 0

    def classify(path: str, xy: str) -> None:
        groups["changed"].add(path)
        if xy[0] != ".":
            groups["staged"].add(path)
        if xy[1] != ".":
            groups["unstaged"].add(path)

    while index < len(records):
        line = records[index].decode("utf-8", "surrogateescape")
        index += 1
        if not line:
            continue
        if line.startswith("# "):
            key, _, value = line[2:].partition(" ")
            headers[key] = value
        elif line.startswith("1 "):
            parts = line.split(" ", 8)
            if len(parts) != 9:
                raise LifecycleError("invalid ordinary status record", "git_parse_error")
            classify(parts[8], parts[1])
        elif line.startswith("2 "):
            parts = line.split(" ", 9)
            if len(parts) != 10 or index >= len(records):
                raise LifecycleError("invalid rename status record", "git_parse_error")
            old = records[index].decode("utf-8", "surrogateescape")
            index += 1
            classify(parts[9], parts[1])
            classify(old, parts[1])
        elif line.startswith("u "):
            parts = line.split(" ", 10)
            if len(parts) != 11:
                raise LifecycleError("invalid conflict status record", "git_parse_error")
            path = parts[10]
            for name in ("staged", "unstaged", "conflicts", "changed"):
                groups[name].add(path)
        elif line.startswith("? "):
            groups["untracked"].add(line[2:])
            groups["changed"].add(line[2:])
        elif not line.startswith("! "):
            raise LifecycleError("unknown git status record", "git_parse_error")
    return {"headers": headers, **{name: sorted(value) for name, value in groups.items()}}


def active_operations(git_dir: Path) -> list[str]:
    probes = {
        "merge": ("MERGE_HEAD",), "rebase": ("rebase-merge", "rebase-apply"),
        "cherry-pick": ("CHERRY_PICK_HEAD",), "revert": ("REVERT_HEAD",),
        "bisect": ("BISECT_LOG", "BISECT_START"),
    }
    return sorted(name for name, paths in probes.items() if any((git_dir / path).exists() for path in paths))


def inspect_git(repo: Repo, mode: str, state: dict[str, Any]) -> GitView:
    parsed = parse_status(
        git(repo.root, "status", "--porcelain=v2", "--branch", "-z", "--untracked-files=all", text=False).stdout
    )
    headers = parsed["headers"]
    head = headers.get("branch.oid")
    head = head if isinstance(head, str) and OID_RE.fullmatch(head) else None
    branch = headers.get("branch.head")
    branch = None if branch in {None, "(detached)"} else branch
    upstream = headers.get("branch.upstream")
    ahead = behind = None
    match = re.fullmatch(r"\+(\d+) -(\d+)", headers.get("branch.ab", ""))
    if match:
        ahead, behind = map(int, match.groups())
    return GitView(
        repo, mode, branch, head, upstream, resolve_ref(repo, upstream),
        resolve_ref(repo, state["base"]["branch"]), resolve_ref(repo, state["intended_branch"]),
        ahead, behind, parsed["staged"], parsed["unstaged"], parsed["untracked"],
        parsed["conflicts"], parsed["changed"], active_operations(repo.git_dir),
    )


def file_entry(repo: Repo, path: str) -> dict[str, str]:
    absolute = repo.root / path
    try:
        metadata = absolute.lstat()
    except FileNotFoundError:
        return {"path": path, "state": "deleted"}
    if stat.S_ISLNK(metadata.st_mode):
        content, mode = os.readlink(absolute).encode(), "120000"
    elif stat.S_ISREG(metadata.st_mode):
        content = absolute.read_bytes()
        mode = "100755" if metadata.st_mode & 0o111 else "100644"
    else:
        raise LifecycleError(f"unsupported changed path type: {path}", "unsupported_path")
    oid = git(repo.root, "hash-object", f"--path={path}", "--stdin", text=False, input_data=content).stdout.decode().strip()
    return {"path": path, "state": "present", "mode": mode, "oid": validate_oid(oid)}


def worktree_fingerprint(repo: Repo, paths: Sequence[str]) -> str:
    return digest([file_entry(repo, path) for path in sorted(paths)])


def commit_fingerprint(repo: Repo, head: str, paths: Sequence[str]) -> str:
    pathspecs = [f":(literal){path}" for path in paths]
    raw = git(repo.root, "ls-tree", "-z", head, "--", *pathspecs, text=False).stdout
    entries: dict[str, dict[str, str]] = {}
    for item in raw.split(b"\0"):
        if not item:
            continue
        metadata, separator, raw_path = item.partition(b"\t")
        if not separator:
            raise LifecycleError("invalid ls-tree output", "git_parse_error")
        mode, object_type, oid = metadata.decode().split(" ")
        path = raw_path.decode("utf-8", "surrogateescape")
        entries[path] = {"path": path, "state": "present", "mode": mode, "oid": oid, "type": object_type}
    normalized = []
    for path in sorted(paths):
        entry = entries.get(path, {"path": path, "state": "deleted"})
        entry.pop("type", None)
        normalized.append(entry)
    return digest(normalized)


def parse_name_status(raw: bytes) -> list[str]:
    fields, paths, index = raw.split(b"\0"), set(), 0
    while index < len(fields):
        status_value = fields[index].decode("utf-8", "surrogateescape")
        index += 1
        if not status_value:
            continue
        if index >= len(fields):
            raise LifecycleError("truncated name-status output", "git_parse_error")
        paths.add(fields[index].decode("utf-8", "surrogateescape"))
        index += 1
        if status_value.startswith(("R", "C")):
            if index >= len(fields):
                raise LifecycleError("truncated rename output", "git_parse_error")
            paths.add(fields[index].decode("utf-8", "surrogateescape"))
            index += 1
    return sorted(paths)


def commit_history(repo: Repo, start: str, head: str) -> tuple[list[str], list[str]]:
    if start == head:
        return [], []
    commits = git(repo.root, "rev-list", "--reverse", f"{start}..{head}").stdout.splitlines()
    paths: set[str] = set()
    for commit in commits:
        raw = git(
            repo.root, "diff-tree", "--root", "--no-commit-id", "--name-status",
            "-r", "-z", "--find-renames", commit, text=False,
        ).stdout
        paths.update(parse_name_status(raw))
    return commits, sorted(paths)


def validate_message(subject: str, body: str) -> tuple[str, str]:
    subject, body = subject.strip(), body.strip()
    if "\n" in subject or not SUBJECT_RE.fullmatch(subject):
        raise LifecycleError("subject must be a conventional commit subject", "invalid_commit_message")
    if len(body) < 10 or len(re.findall(r"[A-Za-z0-9]+", body)) < 2 or body.lower() in PLACEHOLDER_BODIES:
        raise LifecycleError("body must meaningfully explain why", "invalid_commit_message")
    return subject, body


def validation_evidence(values: Sequence[str]) -> list[dict[str, Any]]:
    if not values:
        raise LifecycleError("passing validation evidence is required", "invalid_validation")
    result, names = [], set()
    for raw in values:
        if raw != raw.strip():
            raise LifecycleError("validation evidence may not be padded", "invalid_validation")
        if raw.startswith("{"):
            try:
                item = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise LifecycleError("validation JSON is invalid", "invalid_validation") from exc
            if not isinstance(item, dict) or item.get("passed") is not True:
                raise LifecycleError("validation JSON must declare passed:true", "invalid_validation")
            name = item.get("name")
        else:
            match = re.fullmatch(r"([^=]+)=pass", raw)
            if not match:
                raise LifecycleError("validation must be JSON passed:true or name=pass", "invalid_validation")
            name, item = match.group(1), {"name": match.group(1), "passed": True}
        if not isinstance(name, str) or not name.strip() or name != name.strip():
            raise LifecycleError("validation name must be non-empty and unpadded", "invalid_validation")
        normalized = name.casefold()
        if normalized in names:
            raise LifecycleError(f"duplicate validation name: {name}", "invalid_validation")
        names.add(normalized)
        item = copy.deepcopy(item)
        item.update({"name": name, "passed": True})
        result.append(item)
    return result


def normalize_status(kind: str, status_value: str) -> str:
    kind = kind.strip().lower()
    if kind not in FACT_KINDS:
        raise LifecycleError("invalid fact kind", "invalid_fact")
    key = status_value.strip().lower().replace("-", "_").replace(" ", "_")
    status_result = STATUS_ALIASES[kind].get(key)
    if not status_result:
        raise LifecycleError(f"invalid {kind} status", "invalid_fact")
    return status_result


def context(state: dict[str, Any], view: GitView) -> DecisionContext:
    owned = state["owned_paths"]
    owned_dirty = [path for path in view.changed if owns(path, owned)]
    foreign_dirty = [path for path in view.changed if not owns(path, owned)]
    return DecisionContext(
        state, view, current_unit(state), owned_dirty, foreign_dirty,
        {"owned_paths": owned, "owned_dirty_paths": owned_dirty, "foreign_dirty_paths": foreign_dirty},
    )


def result(ctx: DecisionContext, action: str, code: str, reason: str, **extra: Any) -> dict[str, Any]:
    git_evidence = ctx.view.evidence()
    git_evidence["base"] = {
        "branch": ctx.state["base"]["branch"],
        "declared_sha": ctx.state["base"]["sha"],
        "current_sha": ctx.view.base_sha,
    }
    evidence = {"run_revision": ctx.state["revision"], "git": git_evidence, **ctx.details, **extra}
    return {
        "schema_version": SCHEMA_VERSION, "run_id": ctx.state["run_id"],
        "action": action, "reason_code": code, "reason": reason, "evidence": evidence,
    }


def phase_invariants(ctx: DecisionContext) -> dict[str, Any] | None:
    view, state = ctx.view, ctx.state
    checks = [
        (view.head is None, "missing_head", "worktree has no committed HEAD"),
        (view.branch is None, "detached_head", "worktree is detached"),
        (bool(view.operations), "active_git_operation", "a git operation is active"),
        (bool(view.conflicts), "conflicts", "worktree contains unresolved conflicts"),
        (bool(ctx.foreign_dirty), "foreign_dirty_paths", "dirty paths fall outside ownership"),
    ]
    for failed, code, message in checks:
        if failed:
            return result(ctx, "blocked", code, message)
    if view.mode == "intended" and view.branch != state["intended_branch"]:
        return result(ctx, "blocked", "unexpected_branch", "registered worktree has the wrong branch")
    if view.mode == "intended" and view.branch in TRUNK_BRANCHES:
        return result(ctx, "blocked", "trunk_branch", "lifecycle commits are forbidden on trunk")
    return None


def phase_stack(ctx: DecisionContext) -> dict[str, Any] | None:
    if ctx.view.mode != "base":
        return None
    state, view = ctx.state, ctx.view
    if view.branch != state["base"]["branch"]:
        return result(ctx, "blocked", "unexpected_branch", "starting worktree is not on the base branch")
    if view.head != state["base"]["sha"]:
        return result(ctx, "blocked", "stale_base", "base worktree moved from the exact declared SHA")
    if view.intended_sha is not None:
        return result(
            ctx, "blocked", "intended_worktree_unregistered",
            "intended branch exists without one registered same-repository worktree",
        )
    return result(ctx, "create_stack", "intended_worktree_missing", "create the intended linked worktree")


def local_ancestry(ctx: DecisionContext) -> dict[str, Any] | None:
    view, state = ctx.view, ctx.state
    if not is_ancestor(view.repo, state["base"]["sha"], view.head):
        return result(ctx, "blocked", "base_not_ancestor", "HEAD does not descend from the exact base")
    if not is_ancestor(view.repo, ctx.unit["base_head_sha"], view.head):
        return result(ctx, "blocked", "unit_base_not_ancestor", "HEAD does not descend from the current unit base")
    return None


def consumption(ctx: DecisionContext) -> dict[str, Any]:
    unit, view = ctx.unit, ctx.view
    ready = unit["ready"]
    commits, history_paths = commit_history(view.repo, unit["base_head_sha"], view.head)
    ctx.details["current_unit_history"] = {"commits": commits, "paths": history_paths}
    foreign = [path for path in history_paths if not owns(path, ctx.state["owned_paths"])]
    if foreign:
        raise LifecycleError(
            "commit history touched paths outside ownership: " + ", ".join(foreign),
            "foreign_committed_paths",
        )
    if view.changed:
        raise LifecycleError("new edits require an explicit next work unit", "readiness_consumed_dirty")
    if len(commits) != 1:
        raise LifecycleError("one readiness may authorize exactly one regular commit", "non_regular_commit")
    parents = git(view.repo.root, "rev-list", "--parents", "-n", "1", view.head).stdout.split()
    if len(parents) != 2 or parents[1] != ready["head_sha"]:
        raise LifecycleError("ready HEAD is not the sole parent of the commit", "non_regular_commit")
    if history_paths != ready["paths"]:
        raise LifecycleError("committed paths differ from the ready diff", "commit_diff_mismatch")
    if commit_fingerprint(view.repo, view.head, ready["paths"]) != ready["diff_fingerprint"]:
        raise LifecycleError("committed content differs from the ready diff", "commit_diff_mismatch")
    return {"head_sha": view.head, "commits": commits, "paths": history_paths}


def phase_local(ctx: DecisionContext) -> dict[str, Any] | None:
    ancestry = local_ancestry(ctx)
    if ancestry:
        return ancestry
    unit, view = ctx.unit, ctx.view
    if unit["status"] == "editing":
        if view.head != unit["base_head_sha"]:
            _, paths = commit_history(view.repo, unit["base_head_sha"], view.head)
            foreign = [path for path in paths if not owns(path, ctx.state["owned_paths"])]
            code = "foreign_committed_paths" if foreign else "commit_without_ready"
            return result(ctx, "blocked", code, "HEAD advanced before exact readiness", committed_paths=paths)
        action = "editing" if ctx.owned_dirty else "awaiting_work"
        code = "owned_changes_not_ready" if ctx.owned_dirty else "no_owned_changes"
        return result(ctx, action, code, "current work unit is not semantically ready")
    if unit["status"] != "ready":
        return result(ctx, "blocked", "invalid_current_unit", "current work unit was already consumed")
    ready = unit["ready"]
    if view.head == ready["head_sha"]:
        if ctx.owned_dirty != ready["paths"]:
            return result(ctx, "blocked", "ready_diff_changed", "ready path set changed before commit")
        if worktree_fingerprint(view.repo, ctx.owned_dirty) != ready["diff_fingerprint"]:
            return result(ctx, "blocked", "ready_diff_changed", "ready content changed before commit")
        return result(ctx, "commit", "ready_owned_diff", "exact ready HEAD and owned diff are unchanged")
    try:
        consumed = consumption(ctx)
    except LifecycleError as exc:
        return result(ctx, "blocked", exc.code, str(exc))
    ctx.details["consumed_unit"] = consumed
    return None


def validated_fact(
    fact: Any, index: int, head: str
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(fact, dict):
        raise LifecycleError(f"fact {index} is not an object", "invalid_remote_facts")
    kind, source = fact.get("kind"), fact.get("source")
    status_value, sha = fact.get("status"), fact.get("head_sha")
    if kind not in FACT_KINDS or not isinstance(source, str) or not SOURCE_RE.fullmatch(source):
        raise LifecycleError(f"fact {index} has invalid identity", "invalid_remote_facts")
    if status_value not in set(STATUS_ALIASES[kind].values()) or not isinstance(fact.get("authoritative"), bool):
        raise LifecycleError(f"fact {index} has invalid status or authority", "invalid_remote_facts")
    if not isinstance(sha, str) or not OID_RE.fullmatch(sha):
        raise LifecycleError(f"fact {index} lacks an exact SHA", "invalid_remote_facts")
    receipt = fact.get("receipt_sha")
    if status_value == SUCCESS_RECEIPT.get(kind) and (
        not isinstance(receipt, str) or not OID_RE.fullmatch(receipt)
    ):
        raise LifecycleError(f"fact {index} lacks an exact receipt SHA", "invalid_remote_facts")
    if sha != head:
        return None, f"{kind}:{source}@{sha}"
    return (fact, None) if fact["authoritative"] else (None, None)


def fact_summary(ctx: DecisionContext) -> tuple[dict[str, str], list[dict[str, Any]], list[str]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    stale: list[str] = []
    for index, raw in enumerate(ctx.state["facts"]):
        fact, stale_id = validated_fact(raw, index, ctx.view.head)
        if stale_id:
            stale.append(stale_id)
        if fact:
            latest[(fact["kind"], fact["source"])] = fact
    statuses: dict[str, str] = {}
    for kind in FACT_KINDS:
        observed = {fact["status"] for (fact_kind, _), fact in latest.items() if fact_kind == kind}
        if len(observed) > 1:
            raise LifecycleError(f"authoritative {kind} sources disagree", "contradictory_remote_facts")
        if observed:
            statuses[kind] = next(iter(observed))
    facts = sorted(latest.values(), key=lambda item: (item["kind"], item["source"]))
    return statuses, facts, stale


def upstream_phase(ctx: DecisionContext) -> dict[str, Any] | None:
    view = ctx.view
    if view.upstream is None or view.upstream_sha is None:
        return result(ctx, "push", "upstream_missing", "current committed HEAD has no exact upstream")
    if view.behind and view.behind > 0:
        return result(ctx, "blocked", "upstream_ahead", "local branch is behind or diverged")
    if view.upstream_sha == view.head:
        return None
    if view.ahead and view.ahead > 0 and view.behind == 0:
        return result(ctx, "push", "head_not_pushed", "exact current HEAD is ahead of upstream")
    return result(ctx, "blocked", "upstream_contradiction", "upstream differs without ahead-only proof")


def pr_phase(ctx: DecisionContext, statuses: dict[str, str]) -> dict[str, Any] | None:
    pr = statuses.get("pr")
    if pr is None:
        return result(ctx, "open_pr", "current_pr_fact_missing", "no exact authoritative PR fact exists")
    if pr == "closed":
        return result(ctx, "blocked", "pr_closed", "authoritative PR is closed")
    if pr == "draft":
        return result(ctx, "wait_ci", "pr_draft", "authoritative PR remains draft")
    return None


def merge_ci_phase(ctx: DecisionContext, statuses: dict[str, str]) -> dict[str, Any] | None:
    merge, pr = statuses.get("merge"), statuses.get("pr")
    if merge == "failed":
        return result(ctx, "blocked", "merge_failed", "authoritative merge failed")
    if merge == "merged":
        return None
    if merge == "pending" or pr == "merged":
        return result(ctx, "wait_ci", "merge_receipt_pending", "exact merge receipt is pending")
    ci = statuses.get("ci")
    if ci in {None, "pending", "unknown"}:
        return result(ctx, "wait_ci", "current_ci_fact_not_passing", "exact authoritative CI is not passing")
    if ci == "failed":
        return result(ctx, "blocked", "ci_failed", "authoritative CI failed for current HEAD")
    return result(ctx, "merge_eligible", "exact_authoritative_green", "PR and CI facts match exact current HEAD")


def phase_remote(ctx: DecisionContext) -> dict[str, Any] | None:
    upstream = upstream_phase(ctx)
    if upstream:
        return upstream
    try:
        statuses, facts, stale = fact_summary(ctx)
    except LifecycleError as exc:
        return result(ctx, "blocked", exc.code, str(exc))
    ctx.details.update({"current_authoritative_facts": facts, "stale_facts": stale, "fact_statuses": statuses})
    return pr_phase(ctx, statuses) or merge_ci_phase(ctx, statuses)


def phase_post_merge(ctx: DecisionContext) -> dict[str, Any]:
    statuses = ctx.details["fact_statuses"]
    sync = statuses.get("sync")
    if sync == "failed":
        return result(ctx, "blocked", "sync_failed", "authoritative sync failed")
    if sync != "synced":
        return result(ctx, "sync", "sync_receipt_missing", "exact merge exists without exact sync receipt")
    requirements = [
        {"name": "child_stack_safe", "provided": False, "enforced_by": "execution_adapter"},
        {"name": "no_active_sessions", "provided": False, "enforced_by": "execution_adapter"},
    ]
    return result(
        ctx, "cleanup", "merge_sync_clean",
        "exact merge and sync receipts exist and worktree is clean",
        required_before_cleanup=requirements,
    )


def decide(ctx: DecisionContext) -> dict[str, Any]:
    for phase in (phase_invariants, phase_stack, phase_local, phase_remote):
        decision = phase(ctx)
        if decision is not None:
            return decision
    return phase_post_merge(ctx)


def terminal_result(state: dict[str, Any]) -> dict[str, Any]:
    terminal = state["terminal"]
    return {
        "schema_version": SCHEMA_VERSION, "run_id": state["run_id"],
        "action": terminal["status"], "reason_code": f"terminal_{terminal['status']}",
        "reason": terminal["reason"],
        "evidence": {"run_revision": state["revision"], "git": None, "terminal": terminal},
    }


def blocked_result(run_id: str, code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION, "run_id": run_id, "action": "blocked",
        "reason_code": code, "reason": message,
        "evidence": {"run_revision": None, "git": None},
    }


def inspect_run(cwd: Path | str, run_id: str) -> dict[str, Any]:
    try:
        validate_name(run_id, RUN_ID_RE, "run id")
        invocation = discover_repo(cwd)
        state_path, audit_path, _ = locations(invocation.common_dir, run_id)
        state = reconcile_runs(state_path.parent, audit_path, repair=False).get(run_id)
        if state is None:
            raise LifecycleError(f"run does not exist: {run_id}", "run_not_found")
        if str(invocation.common_dir) != state["repository"]["git_common_dir"]:
            raise LifecycleError("invocation repository does not own this run", "worktree_common_mismatch")
        if state["terminal"] is not None:
            return terminal_result(state)
        repo, mode = target_repo(state, invocation)
        return decide(context(state, inspect_git(repo, mode, state)))
    except LifecycleError as exc:
        return blocked_result(run_id, exc.code, str(exc))
    except Exception as exc:
        return blocked_result(run_id, "inspection_error", normalized_error(exc))


def initial_unit(unit_id: str, description: str, head: str) -> dict[str, Any]:
    return {
        "id": unit_id, "description": description, "base_head_sha": head,
        "status": "editing", "ready": None, "consumed": None,
    }


def duplicate_run(states: Sequence[dict[str, Any]], state: dict[str, Any]) -> str | None:
    for other in states:
        same_target = (
            other["run_id"] != state["run_id"]
            and other["repository"]["git_common_dir"] == state["repository"]["git_common_dir"]
            and other["intended_branch"] == state["intended_branch"]
        )
        if same_target and other["terminal"] is None:
            return other["run_id"]
    return None


def starting_unit_head(repo: Repo, intended_branch: str) -> str:
    candidates = [item for item in list_worktrees(repo) if item.branch == intended_branch]
    if len(candidates) > 1:
        raise LifecycleError("intended branch has multiple registered worktrees", "ambiguous_worktree")
    if not candidates:
        return exact_head(repo)
    candidate = candidates[0]
    if candidate.prunable or not candidate.path.is_dir():
        raise LifecycleError("intended branch worktree is missing or prunable", "missing_worktree")
    intended_repo = discover_repo(candidate.path)
    if intended_repo.common_dir != repo.common_dir:
        raise LifecycleError("intended worktree belongs to another repository", "worktree_common_mismatch")
    return exact_head(intended_repo)


def start_run(
    cwd: Path | str, *, run_id: str | None, task: str, base_branch: str,
    base_sha: str, intended_branch: str, owned_paths: Sequence[str],
    worktree: Path | str | None, unit_id: str, unit_description: str | None,
    key: str, timeout: float,
) -> dict[str, Any]:
    invocation = discover_repo(cwd)
    validate_name(key, KEY_RE, "idempotency key")
    if run_id is None:
        run_id = f"run-{uuid.uuid5(uuid.NAMESPACE_URL, f'{invocation.common_dir}\\0{key}')}"
    validate_name(run_id, RUN_ID_RE, "run id")
    target_path = Path(worktree).expanduser() if worktree else invocation.root
    if not target_path.is_absolute():
        target_path = invocation.root / target_path
    start_repo = discover_repo(target_path)
    if start_repo.common_dir != invocation.common_dir:
        raise LifecycleError("starting worktree belongs to another repository", "worktree_common_mismatch")
    task = task.strip()
    description = (unit_description or task).strip()
    if len(task) < 3 or len(description) < 3:
        raise LifecycleError("task and work unit require meaningful descriptions", "invalid_task")
    validate_name(unit_id, RUN_ID_RE, "work unit id")
    validate_branch(start_repo, base_branch)
    validate_branch(start_repo, intended_branch, intended=True)
    unit_head = starting_unit_head(start_repo, intended_branch)
    validate_oid(base_sha, len(unit_head))
    if resolve_ref(start_repo, base_sha) != base_sha or not is_ancestor(start_repo, base_sha, unit_head):
        raise LifecycleError("base SHA is not an exact ancestor commit", "invalid_base")
    owned = normalize_paths(owned_paths, start_repo.root)
    payload = {
        "task": task, "base": {"branch": base_branch, "sha": base_sha},
        "intended_branch": intended_branch, "owned_paths": owned,
        "start_worktree": str(start_repo.root),
        "work_unit": {"id": unit_id, "description": description},
    }
    state_path, audit_path, lock_path = locations(invocation.common_dir, run_id)
    with RepoLock(lock_path, timeout):
        states = reconcile_runs(state_path.parent, audit_path, repair=True)
        if state_path.exists():
            state = states[run_id]
            duplicate = idempotent(state, "start", key, digest(payload))
            if duplicate:
                return duplicate
            raise LifecycleError(f"run already exists: {run_id}", "run_exists")
        timestamp = now()
        identifier = event_id(run_id, "start", key, digest(payload))
        event = {
            "schema_version": SCHEMA_VERSION, "sequence": 1, "event_id": identifier,
            "run_id": run_id, "operation": "start", "timestamp": timestamp,
            "idempotency_key": key, "payload_digest": digest(payload), "payload": payload, "revision": 1,
        }
        state = {
            "schema_version": SCHEMA_VERSION, "run_id": run_id, "task": task,
            "repository": {"start_worktree": str(start_repo.root), "git_common_dir": str(start_repo.common_dir)},
            "base": {"branch": base_branch, "sha": base_sha}, "intended_branch": intended_branch,
            "owned_paths": owned, "work_units": [initial_unit(unit_id, description, unit_head)],
            "current_unit_id": unit_id, "facts": [], "terminal": None,
            "events": [event], "idempotency": {
                key: {"operation": "start", "digest": digest(payload), "event_id": identifier}
            },
            "revision": 1, "created_at": timestamp, "updated_at": timestamp,
        }
        existing = duplicate_run(list(states.values()), state)
        if existing:
            raise LifecycleError(f"nonterminal run already targets this worktree and branch: {existing}", "duplicate_run")
        persist(state_path, audit_path, state, event)
    return {
        "ok": True, "run_id": run_id, "operation": "start", "event_id": identifier,
        "revision": 1, "idempotent": False, "state_path": str(state_path),
    }


def ready_run(
    cwd: Path | str, *, run_id: str, subject: str, body: str,
    open_tasks: int, validations: Sequence[str], key: str, timeout: float,
) -> dict[str, Any]:
    if open_tasks != 0:
        raise LifecycleError("open tasks must equal zero", "open_tasks")
    subject, body = validate_message(subject, body)
    evidence = validation_evidence(validations)
    payload = {"subject": subject, "body": body, "open_tasks": 0, "validations": evidence}

    def update(state: dict[str, Any], timestamp: str, identifier: str, invocation: Repo) -> None:
        if state["terminal"] is not None:
            raise LifecycleError("terminal run cannot become ready", "terminal_run")
        repo, mode = target_repo(state, invocation)
        if mode != "intended":
            raise LifecycleError("intended linked worktree is not registered", "missing_worktree")
        ctx = context(state, inspect_git(repo, mode, state))
        blocked = phase_invariants(ctx) or local_ancestry(ctx)
        if blocked:
            raise LifecycleError(blocked["reason"], blocked["reason_code"])
        unit = ctx.unit
        ready = unit.get("ready")
        expected_head = ready["head_sha"] if unit["status"] == "ready" else unit["base_head_sha"]
        if unit["status"] == "consumed" or ctx.view.head != expected_head:
            raise LifecycleError("readiness cannot be reused after a commit", "readiness_consumed")
        if not ctx.owned_dirty:
            raise LifecycleError("ready work unit requires a non-empty owned diff", "empty_owned_diff")
        fingerprint = worktree_fingerprint(repo, ctx.owned_dirty)
        unit.update({
            "status": "ready",
            "ready": {
                "head_sha": ctx.view.head, "paths": ctx.owned_dirty,
                "diff_fingerprint": fingerprint, "subject": subject, "body": body,
                "open_tasks": 0, "validations": evidence,
                "timestamp": timestamp, "event_id": identifier,
            },
        })

    return mutate(cwd, run_id, "ready", key, payload, update, timeout)


def next_unit_run(
    cwd: Path | str, *, run_id: str, unit_id: str,
    description: str, key: str, timeout: float,
) -> dict[str, Any]:
    validate_name(unit_id, RUN_ID_RE, "work unit id")
    description = description.strip()
    if len(description) < 3:
        raise LifecycleError("work unit description is too short", "invalid_task")
    payload = {"work_unit": {"id": unit_id, "description": description}}

    def update(state: dict[str, Any], timestamp: str, identifier: str, invocation: Repo) -> None:
        if state["terminal"] is not None:
            raise LifecycleError("terminal run cannot add work", "terminal_run")
        if any(unit["id"] == unit_id for unit in state["work_units"]):
            raise LifecycleError(f"duplicate work unit id: {unit_id}", "duplicate_work_unit")
        repo, mode = target_repo(state, invocation)
        if mode != "intended":
            raise LifecycleError("intended linked worktree is not registered", "missing_worktree")
        ctx = context(state, inspect_git(repo, mode, state))
        blocked = phase_invariants(ctx) or local_ancestry(ctx)
        if blocked:
            raise LifecycleError(blocked["reason"], blocked["reason_code"])
        if ctx.unit["status"] != "ready" or ctx.view.head == ctx.unit["ready"]["head_sha"]:
            raise LifecycleError("current work unit has no consumed ready commit", "unit_not_committed")
        receipt = consumption(ctx)
        ctx.unit.update({
            "status": "consumed",
            "consumed": {**receipt, "timestamp": timestamp, "event_id": identifier},
        })
        state["work_units"].append(initial_unit(unit_id, description, ctx.view.head))
        state["current_unit_id"] = unit_id

    return mutate(cwd, run_id, "next-unit", key, payload, update, timeout)


def record_run(
    cwd: Path | str, *, run_id: str, kind: str, status_value: str,
    source: str, sha: str, authoritative: bool, receipt_sha: str | None,
    metadata: dict[str, Any], key: str, timeout: float,
) -> dict[str, Any]:
    kind = kind.strip().lower()
    status_value = normalize_status(kind, status_value)
    validate_name(source.strip(), SOURCE_RE, "fact source")
    source = source.strip()
    validate_oid(sha)
    if status_value == SUCCESS_RECEIPT.get(kind) and receipt_sha is None:
        raise LifecycleError(f"successful {kind} fact requires --receipt-sha", "missing_receipt")
    if receipt_sha is not None:
        validate_oid(receipt_sha)
    payload = {
        "kind": kind, "status": status_value, "source": source, "sha": sha,
        "authoritative": bool(authoritative), "receipt_sha": receipt_sha, "metadata": metadata,
    }

    def update(state: dict[str, Any], timestamp: str, identifier: str, invocation: Repo) -> None:
        if state["terminal"] is not None:
            raise LifecycleError("terminal run cannot accept facts", "terminal_run")
        repo, mode = target_repo(state, invocation)
        if mode != "intended":
            raise LifecycleError("intended linked worktree is not registered", "missing_worktree")
        head = exact_head(repo)
        validate_oid(sha, len(head))
        if sha != head:
            raise LifecycleError("fact SHA must exactly match current HEAD", "stale_fact")
        state["facts"].append({
            "fact_id": identifier, "kind": kind, "status": status_value,
            "source": source, "head_sha": sha, "authoritative": bool(authoritative),
            "receipt_sha": receipt_sha, "metadata": metadata, "observed_at": timestamp,
        })

    return mutate(cwd, run_id, "record", key, payload, update, timeout)


def halt_run(
    cwd: Path | str, *, run_id: str, status_value: str,
    reason: str, key: str, timeout: float,
) -> dict[str, Any]:
    if status_value not in {"done", "blocked"} or len(reason.strip()) < 3:
        raise LifecycleError("halt requires done/blocked and a meaningful reason", "invalid_terminal")
    reason = reason.strip()
    payload = {"status": status_value, "reason": reason}

    def update(state: dict[str, Any], timestamp: str, identifier: str, _: Repo) -> None:
        if state["terminal"] is not None:
            raise LifecycleError("run already has a terminal status", "terminal_run")
        state["terminal"] = {
            "status": status_value, "reason": reason, "timestamp": timestamp, "event_id": identifier,
        }

    return mutate(cwd, run_id, "halt", key, payload, update, timeout)


def metadata(value: str | None) -> dict[str, Any]:
    if value is None:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise LifecycleError("metadata must be valid JSON", "invalid_metadata") from exc
    if not isinstance(parsed, dict):
        raise LifecycleError("metadata must be a JSON object", "invalid_metadata")
    return parsed


def timeout(value: str) -> float:
    try:
        result_value = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be numeric") from exc
    if result_value < 0:
        raise argparse.ArgumentTypeError("timeout may not be negative")
    return result_value


def mutation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument(
        "--lock-timeout", type=timeout,
        default=timeout(os.environ.get("GIT_LIFECYCLE_LOCK_TIMEOUT", "10")),
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Compute one deterministic next git lifecycle action")
    commands = root.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("--run-id")
    start.add_argument("--task", required=True)
    start.add_argument("--base-branch", required=True)
    start.add_argument("--base-sha", required=True)
    start.add_argument("--intended-branch", "--branch", dest="intended_branch", required=True)
    start.add_argument("--owned-path", "--owned", dest="owned_paths", action="append", required=True)
    start.add_argument("--worktree")
    start.add_argument("--work-unit-id", default="work-1")
    start.add_argument("--work-unit")
    start.add_argument("--idempotency-key", required=True)
    start.add_argument("--lock-timeout", type=timeout, default=timeout(os.environ.get("GIT_LIFECYCLE_LOCK_TIMEOUT", "10")))

    ready = commands.add_parser("ready")
    mutation_args(ready)
    ready.add_argument("--subject", required=True)
    ready.add_argument("--body", required=True)
    ready.add_argument("--open-tasks", "--open-task-count", dest="open_tasks", type=int, required=True)
    ready.add_argument("--validation", "--evidence", dest="validations", action="append", required=True)

    next_unit = commands.add_parser("next-unit")
    mutation_args(next_unit)
    next_unit.add_argument("--work-unit-id", required=True)
    next_unit.add_argument("--work-unit", "--description", dest="description", required=True)

    record = commands.add_parser("record")
    mutation_args(record)
    record.add_argument("--kind", "--fact", dest="kind", required=True)
    record.add_argument("--status", required=True)
    record.add_argument("--source", required=True)
    record.add_argument("--sha", "--head-sha", dest="sha", required=True)
    record.add_argument("--authoritative", action="store_true")
    record.add_argument("--receipt-sha")
    record.add_argument("--metadata")

    inspect = commands.add_parser("inspect")
    inspect.add_argument("--run-id", required=True)

    halt = commands.add_parser("halt")
    mutation_args(halt)
    halt.add_argument("--status", choices=("done", "blocked"), required=True)
    halt.add_argument("--reason", required=True)
    return root


def dispatch(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    common = {"key": args.idempotency_key, "timeout": args.lock_timeout} if args.command not in {"inspect"} else {}
    if args.command == "start":
        return start_run(
            cwd, run_id=args.run_id, task=args.task, base_branch=args.base_branch,
            base_sha=args.base_sha, intended_branch=args.intended_branch,
            owned_paths=args.owned_paths, worktree=args.worktree,
            unit_id=args.work_unit_id, unit_description=args.work_unit, **common,
        )
    if args.command == "ready":
        return ready_run(
            cwd, run_id=args.run_id, subject=args.subject, body=args.body,
            open_tasks=args.open_tasks, validations=args.validations, **common,
        )
    if args.command == "next-unit":
        return next_unit_run(
            cwd, run_id=args.run_id, unit_id=args.work_unit_id,
            description=args.description, **common,
        )
    if args.command == "record":
        return record_run(
            cwd, run_id=args.run_id, kind=args.kind, status_value=args.status,
            source=args.source, sha=args.sha, authoritative=args.authoritative,
            receipt_sha=args.receipt_sha, metadata=metadata(args.metadata), **common,
        )
    if args.command == "inspect":
        return inspect_run(cwd, args.run_id)
    return halt_run(
        cwd, run_id=args.run_id, status_value=args.status, reason=args.reason, **common,
    )


def normalized_error(exc: BaseException) -> str:
    if isinstance(exc, OSError):
        return f"os error {exc.errno}: {exc.strerror or type(exc).__name__}"
    text = str(exc).strip()
    return text if text else type(exc).__name__


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        value = dispatch(args, Path.cwd())
    except LifecycleError as exc:
        print(json.dumps({"ok": False, "error_code": exc.code, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    except Exception as exc:
        print(
            json.dumps({"ok": False, "error_code": "operation_error", "error": normalized_error(exc)}, sort_keys=True),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(value, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
