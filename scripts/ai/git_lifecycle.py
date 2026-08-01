#!/usr/bin/env python3
"""Deterministic, read-only-at-inspection git lifecycle controller."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Iterable, Sequence


SCHEMA_VERSION = 1
AUDIT_SCHEMA_VERSION = 1
STATE_DIR_NAME = "agent-lifecycle"
SUPPORTED_BRANCH_PREFIXES = (
    "feature",
    "feat",
    "bugfix",
    "fix",
    "hotfix",
    "release",
    "chore",
)
TRUNK_BRANCHES = frozenset({"main", "master", "trunk", "develop", "development"})
RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
IDEMPOTENCY_KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
SOURCE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
FULL_OID_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
CONVENTIONAL_SUBJECT_RE = re.compile(
    r"(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(?:\([A-Za-z0-9._/-]+\))?!?: [^\s].{2,}\Z"
)
PLACEHOLDER_BODIES = frozenset(
    {"n/a", "na", "none", "no body", "todo", "tbd", "update", "changes"}
)
FACT_KINDS = frozenset({"pr", "ci", "merge", "sync"})
FACT_STATUS_ALIASES = {
    "pr": {
        "open": "open",
        "ready": "open",
        "draft": "draft",
        "closed": "closed",
        "merged": "merged",
    },
    "ci": {
        "pending": "pending",
        "queued": "pending",
        "running": "pending",
        "in_progress": "pending",
        "passing": "passing",
        "passed": "passing",
        "pass": "passing",
        "success": "passing",
        "successful": "passing",
        "green": "passing",
        "failed": "failed",
        "failure": "failed",
        "failing": "failed",
        "red": "failed",
        "cancelled": "failed",
        "canceled": "failed",
        "timed_out": "failed",
        "unknown": "unknown",
        "skipped": "unknown",
    },
    "merge": {
        "pending": "pending",
        "merged": "merged",
        "success": "merged",
        "succeeded": "merged",
        "failed": "failed",
        "failure": "failed",
    },
    "sync": {
        "pending": "pending",
        "synced": "synced",
        "success": "synced",
        "succeeded": "synced",
        "failed": "failed",
        "failure": "failed",
    },
}


class LifecycleError(RuntimeError):
    """An expected, fail-closed lifecycle error."""


class LockTimeoutError(LifecycleError):
    """The repository lifecycle lock could not be acquired in time."""


@dataclass(frozen=True)
class RepoPaths:
    root: Path
    git_dir: Path
    common_dir: Path


@dataclass
class GitSnapshot:
    root: str
    git_dir: str
    common_dir: str
    branch: str | None
    head_sha: str | None
    upstream_name: str | None
    upstream_sha: str | None
    base_branch: str
    declared_base_sha: str
    current_base_sha: str | None
    intended_branch_sha: str | None
    ahead: int | None
    behind: int | None
    staged_paths: list[str] = field(default_factory=list)
    unstaged_paths: list[str] = field(default_factory=list)
    untracked_paths: list[str] = field(default_factory=list)
    conflict_paths: list[str] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)
    active_operations: list[str] = field(default_factory=list)
    committed_paths: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "git_dir": self.git_dir,
            "common_dir": self.common_dir,
            "branch": self.branch,
            "head_sha": self.head_sha,
            "upstream": {
                "name": self.upstream_name,
                "sha": self.upstream_sha,
                "ahead": self.ahead,
                "behind": self.behind,
            },
            "base": {
                "branch": self.base_branch,
                "declared_sha": self.declared_base_sha,
                "current_sha": self.current_base_sha,
            },
            "intended_branch_sha": self.intended_branch_sha,
            "staged_paths": self.staged_paths,
            "unstaged_paths": self.unstaged_paths,
            "untracked_paths": self.untracked_paths,
            "conflict_paths": self.conflict_paths,
            "changed_paths": self.changed_paths,
            "active_operations": self.active_operations,
            "committed_paths": self.committed_paths,
            "clean": not self.changed_paths,
        }


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def run_git(
    cwd: Path | str,
    *args: str,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=_git_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        check=False,
    )
    if check and proc.returncode != 0:
        stderr = proc.stderr if text else proc.stderr.decode("utf-8", "replace")
        raise LifecycleError(
            f"git {' '.join(args)} failed in {cwd}: {stderr.strip()}"
        )
    return proc


def _absolute_git_path(raw: str, cwd: Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def discover_repo(cwd: Path | str) -> RepoPaths:
    cwd_path = Path(cwd).resolve()
    proc = run_git(
        cwd_path,
        "rev-parse",
        "--path-format=absolute",
        "--show-toplevel",
        "--git-dir",
        "--git-common-dir",
        check=False,
    )
    if proc.returncode == 0:
        lines = proc.stdout.splitlines()
        if len(lines) == 3:
            return RepoPaths(*(Path(line).resolve() for line in lines))

    root_proc = run_git(cwd_path, "rev-parse", "--show-toplevel")
    git_dir_proc = run_git(cwd_path, "rev-parse", "--absolute-git-dir")
    common_proc = run_git(cwd_path, "rev-parse", "--git-common-dir")
    root = Path(root_proc.stdout.strip()).resolve()
    git_dir = Path(git_dir_proc.stdout.strip()).resolve()
    common_dir = _absolute_git_path(common_proc.stdout.strip(), cwd_path)
    return RepoPaths(root=root, git_dir=git_dir, common_dir=common_dir)


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_RE.fullmatch(run_id) or run_id in {".", ".."}:
        raise LifecycleError(
            "run id must be 1-128 safe filename characters and start alphanumeric"
        )
    return run_id


def validate_idempotency_key(key: str) -> str:
    if not IDEMPOTENCY_KEY_RE.fullmatch(key):
        raise LifecycleError(
            "idempotency key must be 1-256 safe non-whitespace characters"
        )
    return key


def validate_full_oid(value: str, *, expected_length: int | None = None) -> str:
    if not FULL_OID_RE.fullmatch(value):
        raise LifecycleError("SHA must be an exact lowercase 40- or 64-character object id")
    if expected_length is not None and len(value) != expected_length:
        raise LifecycleError(
            f"SHA length {len(value)} does not match repository object id length "
            f"{expected_length}"
        )
    return value


def validate_branch(branch: str, *, intended: bool, cwd: Path) -> str:
    if branch != branch.strip() or not branch:
        raise LifecycleError("branch names must be non-empty and have no edge whitespace")
    if branch.startswith("refs/") or branch.startswith("-"):
        raise LifecycleError("branch names must be short local branch names")
    checked = run_git(cwd, "check-ref-format", "--branch", branch, check=False)
    if checked.returncode != 0:
        raise LifecycleError(f"invalid branch name: {branch}")
    if intended:
        prefix, separator, suffix = branch.partition("/")
        if (
            separator != "/"
            or prefix not in SUPPORTED_BRANCH_PREFIXES
            or not suffix
        ):
            supported = ", ".join(f"{item}/" for item in SUPPORTED_BRANCH_PREFIXES)
            raise LifecycleError(
                f"intended branch must use a supported prefix: {supported}"
            )
    return branch


def normalize_owned_paths(raw_paths: Sequence[str], worktree: Path) -> list[str]:
    if not raw_paths:
        raise LifecycleError("at least one owned path is required")

    root = worktree.resolve()
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in raw_paths:
        if not raw or raw != raw.strip() or "\x00" in raw:
            raise LifecycleError("owned paths must be non-empty with no edge whitespace")
        windows_path = PureWindowsPath(raw)
        if (
            Path(raw).is_absolute()
            or PurePosixPath(raw).is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.drive)
        ):
            raise LifecycleError(f"owned path must be repository-relative: {raw}")
        if "\\" in raw:
            raise LifecycleError(f"owned path must use forward slashes: {raw}")

        raw_parts = PurePosixPath(raw).parts
        if ".." in raw_parts:
            raise LifecycleError(f"owned path may not contain '..': {raw}")
        if any(part.lower() == ".git" for part in raw_parts):
            raise LifecycleError(f"owned path may not address .git: {raw}")

        canonical = str(PurePosixPath(raw))
        if canonical in {"", "."}:
            raise LifecycleError("owned path may not be the repository root")
        canonical_parts = PurePosixPath(canonical).parts
        if any(part.lower() == ".git" for part in canonical_parts):
            raise LifecycleError(f"owned path may not address .git: {raw}")

        candidate = (root / canonical).resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise LifecycleError(f"owned path escapes the worktree: {raw}") from exc

        if canonical in seen:
            raise LifecycleError(f"duplicate owned path after normalization: {canonical}")
        seen.add(canonical)
        normalized.append(canonical)

    return sorted(normalized)


def state_locations(common_dir: Path, run_id: str) -> tuple[Path, Path, Path]:
    state_root = common_dir / STATE_DIR_NAME
    return (
        state_root / "runs" / f"{validate_run_id(run_id)}.json",
        state_root / "audit.jsonl",
        state_root / "repository.lock",
    )


class RepositoryLock:
    def __init__(self, path: Path, timeout: float):
        self.path = path
        self.timeout = timeout
        self.fd: int | None = None

    def __enter__(self) -> "RepositoryLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        deadline = time.monotonic() + max(self.timeout, 0.0)
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(self.fd)
                    self.fd = None
                    raise LockTimeoutError(
                        f"timed out acquiring repository lifecycle lock: {self.path}"
                    )
                time.sleep(min(0.025, max(0.0, deadline - time.monotonic())))

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None


def load_state(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except FileNotFoundError as exc:
        raise LifecycleError(f"run does not exist: {path.stem}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"run state is unreadable: {path}: {exc}") from exc
    if not isinstance(state, dict):
        raise LifecycleError("run state root must be an object")
    return state


def validate_state_shape(state: dict[str, Any], expected_run_id: str) -> None:
    if state.get("schema_version") != SCHEMA_VERSION:
        raise LifecycleError(
            f"unsupported run schema version: {state.get('schema_version')!r}"
        )
    if state.get("run_id") != expected_run_id:
        raise LifecycleError("run id does not match its state filename")
    required_types: tuple[tuple[str, type], ...] = (
        ("repository", dict),
        ("base", dict),
        ("intended_branch", str),
        ("owned_paths", list),
        ("work_units", list),
        ("facts", list),
        ("events", list),
        ("idempotency", dict),
        ("revision", int),
    )
    for key, expected_type in required_types:
        if not isinstance(state.get(key), expected_type):
            raise LifecycleError(f"run state field {key!r} has an invalid type")
    if len(state["work_units"]) != 1:
        raise LifecycleError("schema version 1 requires exactly one work unit")


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise


def append_audit(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        written = 0
        while written < len(encoded):
            written += os.write(fd, encoded[written:])
        os.fsync(fd)
    finally:
        os.close(fd)


def _event_id(run_id: str, operation: str, key: str, digest: str) -> str:
    seed = f"{run_id}\0{operation}\0{key}\0{digest}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _idempotent_result(
    state: dict[str, Any],
    *,
    operation: str,
    key: str,
    digest: str,
) -> dict[str, Any] | None:
    prior = state["idempotency"].get(key)
    if prior is None:
        return None
    if prior.get("operation") != operation or prior.get("digest") != digest:
        raise LifecycleError(
            "idempotency key was already used with a different operation or payload"
        )
    return {
        "ok": True,
        "run_id": state["run_id"],
        "operation": operation,
        "event_id": prior.get("event_id"),
        "revision": state["revision"],
        "idempotent": True,
    }


def _apply_event(
    state: dict[str, Any],
    *,
    operation: str,
    key: str,
    payload: dict[str, Any],
    update: Callable[[dict[str, Any], str, str], None],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    digest = canonical_digest(payload)
    duplicate = _idempotent_result(
        state, operation=operation, key=key, digest=digest
    )
    if duplicate is not None:
        return state, {}, duplicate

    changed = copy.deepcopy(state)
    timestamp = utc_now()
    event_id = _event_id(changed["run_id"], operation, key, digest)
    update(changed, timestamp, event_id)
    revision = changed["revision"] + 1
    event = {
        "schema_version": SCHEMA_VERSION,
        "sequence": len(changed["events"]) + 1,
        "event_id": event_id,
        "run_id": changed["run_id"],
        "operation": operation,
        "timestamp": timestamp,
        "idempotency_key": key,
        "payload_digest": digest,
        "payload": payload,
        "revision": revision,
    }
    changed["events"].append(event)
    changed["idempotency"][key] = {
        "operation": operation,
        "digest": digest,
        "event_id": event_id,
    }
    changed["revision"] = revision
    changed["updated_at"] = timestamp
    return changed, event, None


def _persist_event(
    state_path: Path,
    audit_path: Path,
    changed: dict[str, Any],
    event: dict[str, Any],
) -> None:
    atomic_write_json(state_path, changed)
    audit_event = {
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        **event,
    }
    append_audit(audit_path, audit_event)


def _exact_head(worktree: Path) -> str:
    head = run_git(worktree, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    return validate_full_oid(head)


def _verify_commit(worktree: Path, sha: str) -> None:
    resolved = run_git(
        worktree, "rev-parse", "--verify", f"{sha}^{{commit}}", check=False
    )
    if resolved.returncode != 0 or resolved.stdout.strip() != sha:
        raise LifecycleError(f"base SHA is not an exact commit in this repository: {sha}")


def start_run(
    repo_cwd: Path | str,
    *,
    run_id: str | None,
    task: str,
    base_branch: str,
    base_sha: str,
    intended_branch: str,
    owned_paths: Sequence[str],
    worktree: Path | str | None,
    work_unit_id: str,
    work_unit: str | None,
    idempotency_key: str,
    lock_timeout: float,
) -> dict[str, Any]:
    invocation_repo = discover_repo(repo_cwd)
    key = validate_idempotency_key(idempotency_key)
    if run_id is None:
        stable = uuid.uuid5(
            uuid.NAMESPACE_URL, f"{invocation_repo.common_dir}\0{key}"
        )
        run_id = f"run-{stable}"
    run_id = validate_run_id(run_id)

    target = Path(worktree).expanduser() if worktree is not None else invocation_repo.root
    target_repo = discover_repo(target)
    if target_repo.common_dir != invocation_repo.common_dir:
        raise LifecycleError("worktree belongs to a different git common directory")

    normalized_task = task.strip()
    if len(normalized_task) < 3:
        raise LifecycleError("task must contain at least three meaningful characters")
    validate_branch(base_branch, intended=False, cwd=target_repo.root)
    validate_branch(intended_branch, intended=True, cwd=target_repo.root)
    if intended_branch in TRUNK_BRANCHES:
        raise LifecycleError("intended branch may not be a trunk branch")

    current_head = _exact_head(target_repo.root)
    base_sha = validate_full_oid(base_sha, expected_length=len(current_head))
    _verify_commit(target_repo.root, base_sha)
    normalized_paths = normalize_owned_paths(owned_paths, target_repo.root)

    unit_id = validate_run_id(work_unit_id)
    unit_description = (work_unit or normalized_task).strip()
    if len(unit_description) < 3:
        raise LifecycleError("work unit must contain at least three meaningful characters")

    payload = {
        "task": normalized_task,
        "base": {"branch": base_branch, "sha": base_sha},
        "intended_branch": intended_branch,
        "owned_paths": normalized_paths,
        "worktree": str(target_repo.root),
        "work_unit": {"id": unit_id, "description": unit_description},
    }
    state_path, audit_path, lock_path = state_locations(
        invocation_repo.common_dir, run_id
    )
    with RepositoryLock(lock_path, lock_timeout):
        if state_path.exists():
            state = load_state(state_path)
            validate_state_shape(state, run_id)
            digest = canonical_digest(payload)
            duplicate = _idempotent_result(
                state, operation="start", key=key, digest=digest
            )
            if duplicate is not None:
                return duplicate
            raise LifecycleError(f"run already exists: {run_id}")

        timestamp = utc_now()
        digest = canonical_digest(payload)
        event_id = _event_id(run_id, "start", key, digest)
        start_event = {
            "schema_version": SCHEMA_VERSION,
            "sequence": 1,
            "event_id": event_id,
            "run_id": run_id,
            "operation": "start",
            "timestamp": timestamp,
            "idempotency_key": key,
            "payload_digest": digest,
            "payload": payload,
            "revision": 1,
        }
        state = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "task": normalized_task,
            "repository": {
                "worktree": str(target_repo.root),
                "git_common_dir": str(target_repo.common_dir),
            },
            "base": {"branch": base_branch, "sha": base_sha},
            "intended_branch": intended_branch,
            "owned_paths": normalized_paths,
            "work_units": [
                {
                    "id": unit_id,
                    "description": unit_description,
                    "base_head_sha": current_head,
                    "ready": False,
                    "ready_at": None,
                    "ready_head_sha": None,
                    "commit_message": None,
                    "open_tasks": None,
                    "validations": [],
                }
            ],
            "facts": [],
            "terminal": None,
            "events": [start_event],
            "idempotency": {
                key: {
                    "operation": "start",
                    "digest": digest,
                    "event_id": event_id,
                }
            },
            "revision": 1,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        _persist_event(state_path, audit_path, state, start_event)
    return {
        "ok": True,
        "run_id": run_id,
        "operation": "start",
        "event_id": event_id,
        "revision": 1,
        "idempotent": False,
        "state_path": str(state_path),
    }


def normalize_validation_evidence(values: Sequence[str]) -> list[dict[str, Any]]:
    if not values:
        raise LifecycleError("at least one passing validation evidence entry is required")
    evidence: list[dict[str, Any]] = []
    for raw in values:
        raw = raw.strip()
        if not raw:
            raise LifecycleError("validation evidence may not be empty")
        if raw.startswith("{"):
            try:
                item = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise LifecycleError(f"invalid validation JSON: {exc}") from exc
            if not isinstance(item, dict):
                raise LifecycleError("validation JSON must be an object")
        elif "=" in raw:
            name, result = raw.rsplit("=", 1)
            item = {
                "name": name.strip(),
                "passed": result.strip().lower()
                in {"pass", "passed", "passing", "success", "true", "green", "0"},
            }
        elif ":" in raw and raw.rsplit(":", 1)[1].strip().lower() in {
            "pass",
            "passed",
            "passing",
            "success",
            "true",
            "green",
        }:
            name, _ = raw.rsplit(":", 1)
            item = {"name": name.strip(), "passed": True}
        else:
            item = {"name": raw, "passed": True}

        name = item.get("name") or item.get("command") or item.get("check")
        if not isinstance(name, str) or not name.strip():
            raise LifecycleError("validation evidence requires a non-empty name")
        passed = item.get("passed")
        if passed is not True:
            raise LifecycleError(f"validation evidence is not passing: {name}")
        normalized = copy.deepcopy(item)
        normalized["name"] = name.strip()
        normalized["passed"] = True
        evidence.append(normalized)
    return evidence


def validate_commit_message(subject: str, body: str) -> tuple[str, str]:
    normalized_subject = subject.strip()
    normalized_body = body.strip()
    if "\n" in normalized_subject or not CONVENTIONAL_SUBJECT_RE.fullmatch(
        normalized_subject
    ):
        raise LifecycleError("subject must be a single-line conventional commit subject")
    body_words = re.findall(r"[A-Za-z0-9]+", normalized_body)
    if (
        len(normalized_body) < 10
        or len(body_words) < 2
        or normalized_body.lower() in PLACEHOLDER_BODIES
        or normalized_body == normalized_subject
    ):
        raise LifecycleError("commit body must meaningfully explain why the change is needed")
    return normalized_subject, normalized_body


def mutate_existing_run(
    repo_cwd: Path | str,
    *,
    run_id: str,
    operation: str,
    idempotency_key: str,
    payload: dict[str, Any],
    update: Callable[[dict[str, Any], str, str], None],
    lock_timeout: float,
) -> dict[str, Any]:
    repo = discover_repo(repo_cwd)
    run_id = validate_run_id(run_id)
    key = validate_idempotency_key(idempotency_key)
    state_path, audit_path, lock_path = state_locations(repo.common_dir, run_id)
    with RepositoryLock(lock_path, lock_timeout):
        state = load_state(state_path)
        validate_state_shape(state, run_id)
        changed, event, duplicate = _apply_event(
            state,
            operation=operation,
            key=key,
            payload=payload,
            update=update,
        )
        if duplicate is not None:
            return duplicate
        _persist_event(state_path, audit_path, changed, event)
    return {
        "ok": True,
        "run_id": run_id,
        "operation": operation,
        "event_id": event["event_id"],
        "revision": changed["revision"],
        "idempotent": False,
    }


def mark_ready(
    repo_cwd: Path | str,
    *,
    run_id: str,
    work_unit_id: str | None,
    subject: str,
    body: str,
    open_tasks: int,
    validations: Sequence[str],
    idempotency_key: str,
    lock_timeout: float,
) -> dict[str, Any]:
    if open_tasks != 0:
        raise LifecycleError("a work unit is ready only when open tasks equal zero")
    normalized_subject, normalized_body = validate_commit_message(subject, body)
    normalized_validations = normalize_validation_evidence(validations)
    payload = {
        "work_unit_id": work_unit_id,
        "subject": normalized_subject,
        "body": normalized_body,
        "open_tasks": 0,
        "validations": normalized_validations,
    }

    def update(state: dict[str, Any], timestamp: str, event_id: str) -> None:
        if state.get("terminal") is not None:
            raise LifecycleError("terminal runs cannot be marked ready")
        units = state["work_units"]
        selected = (
            next((unit for unit in units if unit.get("id") == work_unit_id), None)
            if work_unit_id is not None
            else units[0]
        )
        if selected is None:
            raise LifecycleError(f"unknown work unit: {work_unit_id}")
        if selected.get("ready") is True:
            raise LifecycleError("work unit is already ready")
        worktree = Path(state["repository"]["worktree"])
        selected["ready"] = True
        selected["ready_at"] = timestamp
        selected["ready_head_sha"] = _exact_head(worktree)
        selected["commit_message"] = {
            "subject": normalized_subject,
            "body": normalized_body,
        }
        selected["open_tasks"] = 0
        selected["validations"] = normalized_validations
        selected["ready_event_id"] = event_id

    return mutate_existing_run(
        repo_cwd,
        run_id=run_id,
        operation="ready",
        idempotency_key=idempotency_key,
        payload=payload,
        update=update,
        lock_timeout=lock_timeout,
    )


def normalize_fact_status(kind: str, status: str) -> str:
    if kind not in FACT_KINDS:
        raise LifecycleError(f"fact kind must be one of: {', '.join(sorted(FACT_KINDS))}")
    normalized = status.strip().lower().replace("-", "_").replace(" ", "_")
    canonical = FACT_STATUS_ALIASES[kind].get(normalized)
    if canonical is None:
        allowed = ", ".join(sorted(FACT_STATUS_ALIASES[kind]))
        raise LifecycleError(f"invalid {kind} status {status!r}; expected one of: {allowed}")
    return canonical


def parse_metadata(raw: str | None) -> dict[str, Any]:
    if raw is None:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LifecycleError(f"invalid metadata JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LifecycleError("metadata JSON must be an object")
    return value


def record_fact(
    repo_cwd: Path | str,
    *,
    run_id: str,
    kind: str,
    status: str,
    source: str,
    sha: str,
    authoritative: bool,
    receipt_sha: str | None,
    metadata: dict[str, Any],
    idempotency_key: str,
    lock_timeout: float,
) -> dict[str, Any]:
    kind = kind.strip().lower()
    canonical_status = normalize_fact_status(kind, status)
    source = source.strip()
    if not SOURCE_RE.fullmatch(source):
        raise LifecycleError("fact source must be a short, explicit source identifier")

    sha = validate_full_oid(sha)
    if receipt_sha is not None:
        receipt_sha = validate_full_oid(receipt_sha)
    elif kind in {"merge", "sync"}:
        receipt_sha = sha

    payload = {
        "kind": kind,
        "status": canonical_status,
        "source": source,
        "sha": sha,
        "authoritative": bool(authoritative),
        "receipt_sha": receipt_sha,
        "metadata": metadata,
    }

    def update(changed: dict[str, Any], timestamp: str, event_id: str) -> None:
        if changed.get("terminal") is not None:
            raise LifecycleError("terminal runs cannot accept new facts")
        worktree = Path(changed["repository"]["worktree"])
        current_head = _exact_head(worktree)
        validate_full_oid(sha, expected_length=len(current_head))
        if sha != current_head:
            raise LifecycleError(
                "fact SHA must exactly match the run worktree's current HEAD"
            )
        changed["facts"].append(
            {
                "fact_id": event_id,
                "kind": kind,
                "status": canonical_status,
                "source": source,
                "head_sha": sha,
                "authoritative": bool(authoritative),
                "receipt_sha": receipt_sha,
                "metadata": metadata,
                "observed_at": timestamp,
            }
        )

    return mutate_existing_run(
        repo_cwd,
        run_id=run_id,
        operation="record",
        idempotency_key=idempotency_key,
        payload=payload,
        update=update,
        lock_timeout=lock_timeout,
    )


def halt_run(
    repo_cwd: Path | str,
    *,
    run_id: str,
    status: str,
    reason: str,
    idempotency_key: str,
    lock_timeout: float,
) -> dict[str, Any]:
    status = status.strip().lower()
    if status not in {"done", "blocked"}:
        raise LifecycleError("terminal status must be done or blocked")
    reason = reason.strip()
    if len(reason) < 3:
        raise LifecycleError("terminal reason must contain at least three characters")
    payload = {"status": status, "reason": reason}

    def update(state: dict[str, Any], timestamp: str, event_id: str) -> None:
        if state.get("terminal") is not None:
            raise LifecycleError("run already has a terminal status")
        state["terminal"] = {
            "status": status,
            "reason": reason,
            "timestamp": timestamp,
            "event_id": event_id,
        }

    return mutate_existing_run(
        repo_cwd,
        run_id=run_id,
        operation="halt",
        idempotency_key=idempotency_key,
        payload=payload,
        update=update,
        lock_timeout=lock_timeout,
    )


def _decode_path(raw: bytes) -> str:
    return raw.decode("utf-8", "surrogateescape")


def parse_porcelain_v2(raw: bytes) -> dict[str, Any]:
    records = raw.split(b"\0")
    headers: dict[str, str] = {}
    staged: set[str] = set()
    unstaged: set[str] = set()
    untracked: set[str] = set()
    conflicts: set[str] = set()
    changed: set[str] = set()
    index = 0

    def add_classified(path: str, xy: str) -> None:
        changed.add(path)
        if len(xy) >= 1 and xy[0] != ".":
            staged.add(path)
        if len(xy) >= 2 and xy[1] != ".":
            unstaged.add(path)

    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        line = _decode_path(record)
        if line.startswith("# "):
            key, _, value = line[2:].partition(" ")
            headers[key] = value
            continue
        if line.startswith("1 "):
            parts = line.split(" ", 8)
            if len(parts) != 9:
                raise LifecycleError(f"unparseable ordinary git status record: {line!r}")
            add_classified(parts[8], parts[1])
            continue
        if line.startswith("2 "):
            parts = line.split(" ", 9)
            if len(parts) != 10 or index >= len(records):
                raise LifecycleError(f"unparseable rename git status record: {line!r}")
            original = _decode_path(records[index])
            index += 1
            add_classified(parts[9], parts[1])
            add_classified(original, parts[1])
            continue
        if line.startswith("u "):
            parts = line.split(" ", 10)
            if len(parts) != 11:
                raise LifecycleError(f"unparseable conflict git status record: {line!r}")
            path = parts[10]
            conflicts.add(path)
            changed.add(path)
            staged.add(path)
            unstaged.add(path)
            continue
        if line.startswith("? "):
            path = line[2:]
            untracked.add(path)
            changed.add(path)
            continue
        if line.startswith("! "):
            continue
        raise LifecycleError(f"unknown git status record: {line!r}")

    return {
        "headers": headers,
        "staged": sorted(staged),
        "unstaged": sorted(unstaged),
        "untracked": sorted(untracked),
        "conflicts": sorted(conflicts),
        "changed": sorted(changed),
    }


def _resolve_ref(worktree: Path, ref: str | None) -> str | None:
    if not ref:
        return None
    proc = run_git(
        worktree, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}",
        check=False,
    )
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value if FULL_OID_RE.fullmatch(value) else None


def _active_operations(git_dir: Path) -> list[str]:
    probes = {
        "merge": (git_dir / "MERGE_HEAD",),
        "rebase": (git_dir / "rebase-merge", git_dir / "rebase-apply"),
        "cherry-pick": (git_dir / "CHERRY_PICK_HEAD",),
        "revert": (git_dir / "REVERT_HEAD",),
        "bisect": (git_dir / "BISECT_LOG", git_dir / "BISECT_START"),
    }
    return sorted(
        operation
        for operation, paths in probes.items()
        if any(path.exists() for path in paths)
    )


def _parse_name_status(raw: bytes) -> list[str]:
    fields = raw.split(b"\0")
    paths: set[str] = set()
    index = 0
    while index < len(fields):
        status_raw = fields[index]
        index += 1
        if not status_raw:
            continue
        status = _decode_path(status_raw)
        if index >= len(fields):
            raise LifecycleError("truncated git diff --name-status output")
        first = _decode_path(fields[index])
        index += 1
        paths.add(first)
        if status.startswith(("R", "C")):
            if index >= len(fields):
                raise LifecycleError("truncated rename/copy path in git diff output")
            paths.add(_decode_path(fields[index]))
            index += 1
    return sorted(paths)


def committed_paths(worktree: Path, base_sha: str, head_sha: str) -> list[str]:
    if base_sha == head_sha:
        return []
    proc = run_git(
        worktree,
        "diff",
        "--name-status",
        "-z",
        "--find-renames",
        f"{base_sha}..{head_sha}",
        text=False,
    )
    return _parse_name_status(proc.stdout)


def collect_snapshot(state: dict[str, Any]) -> GitSnapshot:
    worktree = Path(state["repository"]["worktree"])
    repo = discover_repo(worktree)
    status_proc = run_git(
        repo.root,
        "status",
        "--porcelain=v2",
        "--branch",
        "-z",
        "--untracked-files=all",
        text=False,
    )
    parsed = parse_porcelain_v2(status_proc.stdout)
    headers = parsed["headers"]
    head = headers.get("branch.oid")
    if head in {None, "(initial)"} or not FULL_OID_RE.fullmatch(head):
        head = None
    branch = headers.get("branch.head")
    if branch in {None, "(detached)"}:
        branch = None
    upstream = headers.get("branch.upstream")
    upstream_sha = _resolve_ref(repo.root, upstream)
    ab = headers.get("branch.ab")
    ahead: int | None = None
    behind: int | None = None
    if ab:
        matched = re.fullmatch(r"\+(\d+) -(\d+)", ab)
        if matched:
            ahead, behind = (int(value) for value in matched.groups())

    base_branch = state["base"]["branch"]
    declared_base = state["base"]["sha"]
    unit_base = state["work_units"][0].get("base_head_sha")
    committed: list[str] = []
    if (
        head is not None
        and isinstance(unit_base, str)
        and FULL_OID_RE.fullmatch(unit_base)
    ):
        committed = committed_paths(repo.root, unit_base, head)

    return GitSnapshot(
        root=str(repo.root),
        git_dir=str(repo.git_dir),
        common_dir=str(repo.common_dir),
        branch=branch,
        head_sha=head,
        upstream_name=upstream,
        upstream_sha=upstream_sha,
        base_branch=base_branch,
        declared_base_sha=declared_base,
        current_base_sha=_resolve_ref(repo.root, base_branch),
        intended_branch_sha=_resolve_ref(repo.root, state["intended_branch"]),
        ahead=ahead,
        behind=behind,
        staged_paths=parsed["staged"],
        unstaged_paths=parsed["unstaged"],
        untracked_paths=parsed["untracked"],
        conflict_paths=parsed["conflicts"],
        changed_paths=parsed["changed"],
        active_operations=_active_operations(repo.git_dir),
        committed_paths=committed,
    )


def path_is_owned(path: str, owned_paths: Sequence[str]) -> bool:
    return any(path == owned or path.startswith(f"{owned}/") for owned in owned_paths)


def _is_ancestor(worktree: Path, ancestor: str, descendant: str) -> bool:
    proc = run_git(
        worktree,
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
        check=False,
    )
    return proc.returncode == 0


def _fact_analysis(
    facts: Sequence[Any], head_sha: str | None
) -> tuple[dict[str, str], list[dict[str, Any]], list[str], list[str]]:
    invalid: list[str] = []
    stale: list[dict[str, Any]] = []
    latest_by_source: dict[tuple[str, str], dict[str, Any]] = {}
    for index, raw in enumerate(facts):
        if not isinstance(raw, dict):
            invalid.append(f"fact[{index}] is not an object")
            continue
        kind = raw.get("kind")
        source = raw.get("source")
        status = raw.get("status")
        sha = raw.get("head_sha")
        authoritative = raw.get("authoritative")
        if kind not in FACT_KINDS:
            invalid.append(f"fact[{index}] has invalid kind")
            continue
        if not isinstance(source, str) or not SOURCE_RE.fullmatch(source):
            invalid.append(f"fact[{index}] has invalid source")
            continue
        if status not in set(FACT_STATUS_ALIASES[kind].values()):
            invalid.append(f"fact[{index}] has invalid status")
            continue
        if not isinstance(sha, str) or not FULL_OID_RE.fullmatch(sha):
            invalid.append(f"fact[{index}] does not contain an exact full SHA")
            continue
        if kind in {"merge", "sync"} and status in {"merged", "synced"}:
            receipt_sha = raw.get("receipt_sha")
            if not isinstance(receipt_sha, str) or not FULL_OID_RE.fullmatch(
                receipt_sha
            ):
                invalid.append(f"fact[{index}] lacks an exact receipt SHA")
                continue
        if not isinstance(authoritative, bool):
            invalid.append(f"fact[{index}] has invalid authority")
            continue
        if sha != head_sha:
            stale.append(
                {
                    "kind": kind,
                    "source": source,
                    "status": status,
                    "head_sha": sha,
                }
            )
            continue
        if authoritative:
            latest_by_source[(kind, source)] = raw

    statuses: dict[str, str] = {}
    contradictions: list[str] = []
    for kind in FACT_KINDS:
        observed = {
            fact["status"]
            for (fact_kind, _), fact in latest_by_source.items()
            if fact_kind == kind
        }
        if len(observed) > 1:
            contradictions.append(
                f"authoritative {kind} sources disagree: {', '.join(sorted(observed))}"
            )
        elif observed:
            statuses[kind] = next(iter(observed))
    current_facts = [
        copy.deepcopy(fact)
        for fact in latest_by_source.values()
    ]
    current_facts.sort(key=lambda fact: (fact["kind"], fact["source"]))
    return statuses, current_facts, invalid, contradictions + [
        f"stale fact ignored: {item['kind']}:{item['source']}@{item['head_sha']}"
        for item in stale
    ]


def _result(
    action: str,
    code: str,
    reason: str,
    *,
    run_id: str,
    revision: int | None,
    snapshot: GitSnapshot | None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "run_revision": revision,
        "git": snapshot.as_dict() if snapshot is not None else None,
    }
    if details:
        evidence.update(details)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "action": action,
        "reason_code": code,
        "reason": reason,
        "evidence": evidence,
    }


def decide(state: dict[str, Any], snapshot: GitSnapshot) -> dict[str, Any]:
    run_id = state["run_id"]
    revision = state["revision"]
    owned_paths = state["owned_paths"]
    worktree = Path(snapshot.root)
    foreign_dirty = [
        path for path in snapshot.changed_paths if not path_is_owned(path, owned_paths)
    ]
    owned_dirty = [
        path for path in snapshot.changed_paths if path_is_owned(path, owned_paths)
    ]
    foreign_committed = [
        path for path in snapshot.committed_paths if not path_is_owned(path, owned_paths)
    ]
    details: dict[str, Any] = {
        "owned_paths": owned_paths,
        "owned_dirty_paths": owned_dirty,
        "foreign_dirty_paths": foreign_dirty,
        "foreign_committed_paths": foreign_committed,
    }

    if snapshot.head_sha is None:
        return _result(
            "blocked", "missing_head", "the worktree has no committed HEAD",
            run_id=run_id, revision=revision, snapshot=snapshot, details=details,
        )
    if snapshot.common_dir != state["repository"]["git_common_dir"]:
        return _result(
            "blocked",
            "git_common_dir_mismatch",
            "the run worktree no longer belongs to its recorded shared repository",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if snapshot.root != state["repository"]["worktree"]:
        return _result(
            "blocked",
            "worktree_mismatch",
            "the inspected worktree does not match the recorded worktree",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if snapshot.branch is None:
        return _result(
            "blocked", "detached_head", "the run worktree is in detached HEAD state",
            run_id=run_id, revision=revision, snapshot=snapshot, details=details,
        )
    if snapshot.active_operations:
        return _result(
            "blocked",
            "active_git_operation",
            "a git operation is active: " + ", ".join(snapshot.active_operations),
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if snapshot.conflict_paths:
        return _result(
            "blocked",
            "conflicts",
            "the worktree contains unresolved conflicts",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if foreign_dirty:
        return _result(
            "blocked",
            "foreign_dirty_paths",
            "dirty paths fall outside the run's ownership boundary",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )

    terminal = state.get("terminal")
    if isinstance(terminal, dict) and terminal.get("status") == "blocked":
        details["terminal"] = terminal
        return _result(
            "blocked",
            "terminal_blocked",
            terminal.get("reason", "the run was halted as blocked"),
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if isinstance(terminal, dict) and terminal.get("status") == "done":
        if snapshot.changed_paths:
            return _result(
                "blocked",
                "terminal_done_dirty",
                "a done run has a dirty worktree",
                run_id=run_id,
                revision=revision,
                snapshot=snapshot,
                details=details,
            )
        details["terminal"] = terminal
        return _result(
            "done",
            "terminal_done",
            terminal.get("reason", "the run was halted as done"),
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )

    intended_branch = state["intended_branch"]
    base_branch = state["base"]["branch"]
    declared_base = state["base"]["sha"]
    if snapshot.branch != intended_branch:
        if snapshot.branch != base_branch:
            return _result(
                "blocked",
                "unexpected_branch",
                f"expected {intended_branch} or its base {base_branch}, "
                f"found {snapshot.branch}",
                run_id=run_id,
                revision=revision,
                snapshot=snapshot,
                details=details,
            )
        if snapshot.head_sha != declared_base:
            return _result(
                "blocked",
                "stale_base",
                "the checked-out base branch moved from the run's exact base SHA",
                run_id=run_id,
                revision=revision,
                snapshot=snapshot,
                details=details,
            )
        if snapshot.intended_branch_sha is not None:
            return _result(
                "blocked",
                "intended_branch_elsewhere",
                "the intended branch already exists but is not checked out here",
                run_id=run_id,
                revision=revision,
                snapshot=snapshot,
                details=details,
            )
        return _result(
            "create_stack",
            "intended_branch_missing",
            f"create {intended_branch} from {base_branch}@{declared_base}",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )

    if snapshot.branch in TRUNK_BRANCHES:
        return _result(
            "blocked",
            "trunk_branch",
            "lifecycle commits are forbidden on trunk branches",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if not _is_ancestor(worktree, declared_base, snapshot.head_sha):
        return _result(
            "blocked",
            "base_not_ancestor",
            "current HEAD does not descend from the run's exact base SHA",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if foreign_committed:
        return _result(
            "blocked",
            "foreign_committed_paths",
            "commits since the work unit began contain paths outside ownership",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )

    unit = state["work_units"][0]
    unit_base = unit.get("base_head_sha")
    if not isinstance(unit_base, str) or not FULL_OID_RE.fullmatch(unit_base):
        return _result(
            "blocked",
            "invalid_work_unit_base",
            "the work unit lacks an exact base HEAD SHA",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    ready = unit.get("ready") is True
    if not ready and snapshot.head_sha != unit_base:
        return _result(
            "blocked",
            "commit_without_ready",
            "HEAD advanced before the work unit was semantically marked ready",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if not ready:
        action = "editing" if owned_dirty else "awaiting_work"
        code = "owned_changes_not_ready" if owned_dirty else "no_owned_changes"
        reason = (
            "owned changes exist but the work unit is not semantically ready"
            if owned_dirty
            else "the work unit is awaiting owned changes"
        )
        return _result(
            action, code, reason,
            run_id=run_id, revision=revision, snapshot=snapshot, details=details,
        )

    validations = unit.get("validations")
    commit_message = unit.get("commit_message")
    if (
        unit.get("open_tasks") != 0
        or not isinstance(validations, list)
        or not validations
        or any(
            not isinstance(item, dict) or item.get("passed") is not True
            for item in validations
        )
        or not isinstance(commit_message, dict)
    ):
        return _result(
            "blocked",
            "invalid_ready_evidence",
            "semantic readiness lacks zero open tasks, a commit message, or passing evidence",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    details["ready"] = {
        "work_unit_id": unit.get("id"),
        "commit_message": commit_message,
        "validations": validations,
    }

    if owned_dirty:
        return _result(
            "commit",
            "ready_owned_diff",
            "the ready work unit has a non-empty, exclusively owned diff",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if snapshot.head_sha == unit_base or not snapshot.committed_paths:
        return _result(
            "awaiting_work",
            "ready_without_diff",
            "the ready work unit has no owned diff or owned commit",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )

    statuses, current_facts, invalid_facts, fact_notes = _fact_analysis(
        state["facts"], snapshot.head_sha
    )
    details["current_authoritative_facts"] = current_facts
    details["fact_notes"] = fact_notes
    if invalid_facts:
        details["invalid_facts"] = invalid_facts
        return _result(
            "blocked",
            "invalid_remote_facts",
            "recorded facts are malformed or use abbreviated SHAs",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    disagreements = [note for note in fact_notes if note.startswith("authoritative ")]
    if disagreements:
        return _result(
            "blocked",
            "contradictory_remote_facts",
            "; ".join(disagreements),
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )

    if snapshot.upstream_name is None or snapshot.upstream_sha is None:
        return _result(
            "push",
            "upstream_missing",
            "the committed HEAD has no exact local upstream observation",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if snapshot.behind is not None and snapshot.behind > 0:
        return _result(
            "blocked",
            "upstream_ahead",
            "the local branch is behind or diverged from its upstream",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if snapshot.upstream_sha != snapshot.head_sha:
        if snapshot.ahead is not None and snapshot.ahead > 0 and snapshot.behind == 0:
            return _result(
                "push",
                "head_not_pushed",
                "the exact current HEAD is ahead of its local upstream observation",
                run_id=run_id,
                revision=revision,
                snapshot=snapshot,
                details=details,
            )
        return _result(
            "blocked",
            "upstream_contradiction",
            "upstream SHA differs from HEAD without a safe ahead-only relation",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )

    pr_status = statuses.get("pr")
    if pr_status is None:
        return _result(
            "open_pr",
            "current_pr_fact_missing",
            "no authoritative PR fact is keyed to the exact current HEAD",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if pr_status == "closed":
        return _result(
            "blocked",
            "pr_closed",
            "the authoritative PR fact says the PR is closed",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if pr_status == "draft":
        return _result(
            "wait_ci",
            "pr_draft",
            "the authoritative PR is still a draft",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )

    merge_status = statuses.get("merge")
    if merge_status == "failed":
        return _result(
            "blocked",
            "merge_failed",
            "the authoritative merge receipt reports failure",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if merge_status == "merged":
        if snapshot.changed_paths:
            return _result(
                "blocked",
                "post_merge_dirty",
                "the worktree became dirty after the exact merge receipt",
                run_id=run_id,
                revision=revision,
                snapshot=snapshot,
                details=details,
            )
        sync_status = statuses.get("sync")
        if sync_status == "failed":
            return _result(
                "blocked",
                "sync_failed",
                "the authoritative sync receipt reports failure",
                run_id=run_id,
                revision=revision,
                snapshot=snapshot,
                details=details,
            )
        if sync_status != "synced":
            return _result(
                "sync",
                "sync_receipt_missing",
                "the exact merge receipt exists but no successful exact sync receipt does",
                run_id=run_id,
                revision=revision,
                snapshot=snapshot,
                details=details,
            )
        details["required_before_cleanup"] = [
            {
                "name": "child_stack_safe",
                "provided": False,
                "enforced_by": "execution_adapter",
            },
            {
                "name": "no_active_sessions",
                "provided": False,
                "enforced_by": "execution_adapter",
            },
        ]
        return _result(
            "cleanup",
            "merge_sync_clean",
            "exact merge and sync receipts exist and the worktree is clean",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if merge_status == "pending" or pr_status == "merged":
        return _result(
            "wait_ci",
            "merge_receipt_pending",
            "the PR is merged or merging but an exact authoritative merge receipt is pending",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )

    ci_status = statuses.get("ci")
    if ci_status is None or ci_status in {"pending", "unknown"}:
        return _result(
            "wait_ci",
            "current_ci_fact_not_passing",
            "CI evidence is missing, pending, unknown, stale, or non-authoritative",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if ci_status == "failed":
        return _result(
            "blocked",
            "ci_failed",
            "authoritative CI failed for the exact current HEAD",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    if ci_status != "passing":
        return _result(
            "blocked",
            "unknown_ci_status",
            "CI status is not a recognized passing state",
            run_id=run_id,
            revision=revision,
            snapshot=snapshot,
            details=details,
        )
    return _result(
        "merge_eligible",
        "exact_authoritative_green",
        "the exact current HEAD has authoritative open-PR and passing-CI facts",
        run_id=run_id,
        revision=revision,
        snapshot=snapshot,
        details=details,
    )


def blocked_inspection(
    run_id: str, code: str, reason: str, *, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return _result(
        "blocked",
        code,
        reason,
        run_id=run_id,
        revision=None,
        snapshot=None,
        details=details,
    )


def inspect_run(repo_cwd: Path | str, *, run_id: str) -> dict[str, Any]:
    run_id = validate_run_id(run_id)
    try:
        invocation_repo = discover_repo(repo_cwd)
        state_path, _, _ = state_locations(invocation_repo.common_dir, run_id)
        state = load_state(state_path)
        validate_state_shape(state, run_id)
        snapshot = collect_snapshot(state)
        return decide(state, snapshot)
    except LifecycleError as exc:
        return blocked_inspection(run_id, "inspection_invariant", str(exc))


def _lock_timeout(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("lock timeout must be a number") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("lock timeout may not be negative")
    return parsed


def _add_common_mutation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument(
        "--lock-timeout",
        type=_lock_timeout,
        default=_lock_timeout(os.environ.get("GIT_LIFECYCLE_LOCK_TIMEOUT", "10")),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute one deterministic next git lifecycle action"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="create a versioned lifecycle run")
    start.add_argument("--run-id")
    start.add_argument("--task", required=True)
    start.add_argument("--base-branch", required=True)
    start.add_argument("--base-sha", required=True)
    start.add_argument(
        "--intended-branch", "--branch", dest="intended_branch", required=True
    )
    start.add_argument(
        "--owned-path", "--owned", dest="owned_paths", action="append", required=True
    )
    start.add_argument("--worktree")
    start.add_argument("--work-unit-id", default="work-1")
    start.add_argument("--work-unit")
    start.add_argument("--idempotency-key", required=True)
    start.add_argument(
        "--lock-timeout",
        type=_lock_timeout,
        default=_lock_timeout(os.environ.get("GIT_LIFECYCLE_LOCK_TIMEOUT", "10")),
    )

    ready = subparsers.add_parser("ready", help="mark the work unit semantically ready")
    _add_common_mutation_args(ready)
    ready.add_argument("--work-unit-id")
    ready.add_argument("--subject", required=True)
    ready.add_argument("--body", required=True)
    ready.add_argument(
        "--open-tasks", "--open-task-count", dest="open_tasks", type=int, required=True
    )
    ready.add_argument(
        "--validation",
        "--evidence",
        dest="validations",
        action="append",
        required=True,
    )

    record = subparsers.add_parser("record", help="record a sourced lifecycle fact")
    _add_common_mutation_args(record)
    record.add_argument("--kind", "--fact", dest="kind", required=True)
    record.add_argument("--status", required=True)
    record.add_argument("--source", required=True)
    record.add_argument("--sha", "--head-sha", dest="sha", required=True)
    record.add_argument("--authoritative", action="store_true")
    record.add_argument("--receipt-sha")
    record.add_argument("--metadata")

    inspect = subparsers.add_parser("inspect", help="emit one read-only next action")
    inspect.add_argument("--run-id", required=True)

    halt = subparsers.add_parser("halt", help="append a terminal run status")
    _add_common_mutation_args(halt)
    halt.add_argument("--status", choices=("done", "blocked"), required=True)
    halt.add_argument("--reason", required=True)
    return parser


def dispatch(args: argparse.Namespace, cwd: Path | str) -> dict[str, Any]:
    if args.command == "start":
        return start_run(
            cwd,
            run_id=args.run_id,
            task=args.task,
            base_branch=args.base_branch,
            base_sha=args.base_sha,
            intended_branch=args.intended_branch,
            owned_paths=args.owned_paths,
            worktree=args.worktree,
            work_unit_id=args.work_unit_id,
            work_unit=args.work_unit,
            idempotency_key=args.idempotency_key,
            lock_timeout=args.lock_timeout,
        )
    if args.command == "ready":
        return mark_ready(
            cwd,
            run_id=args.run_id,
            work_unit_id=args.work_unit_id,
            subject=args.subject,
            body=args.body,
            open_tasks=args.open_tasks,
            validations=args.validations,
            idempotency_key=args.idempotency_key,
            lock_timeout=args.lock_timeout,
        )
    if args.command == "record":
        return record_fact(
            cwd,
            run_id=args.run_id,
            kind=args.kind,
            status=args.status,
            source=args.source,
            sha=args.sha,
            authoritative=args.authoritative,
            receipt_sha=args.receipt_sha,
            metadata=parse_metadata(args.metadata),
            idempotency_key=args.idempotency_key,
            lock_timeout=args.lock_timeout,
        )
    if args.command == "inspect":
        return inspect_run(cwd, run_id=args.run_id)
    if args.command == "halt":
        return halt_run(
            cwd,
            run_id=args.run_id,
            status=args.status,
            reason=args.reason,
            idempotency_key=args.idempotency_key,
            lock_timeout=args.lock_timeout,
        )
    raise LifecycleError(f"unsupported command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = dispatch(args, Path.cwd())
    except LifecycleError as exc:
        print(
            json.dumps(
                {"ok": False, "error": str(exc), "error_type": type(exc).__name__},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
