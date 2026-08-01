#!/usr/bin/env python3
"""Claude Code adapter for the shared deterministic git lifecycle controller."""
from __future__ import annotations
import argparse, fcntl, hashlib, json, os, re, shlex, shutil, signal, stat, subprocess, sys, tempfile, threading, time
import contextlib
import datetime as dt
import urllib.parse
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Sequence
sys.path.insert(0, str(Path(__file__).resolve().parent))
import git_lifecycle as lifecycle  # noqa: E402

ADAPTER_SCHEMA_VERSION = 1
HOOK_ENVELOPE_VERSION = 1
ROOT = Path(__file__).resolve().parents[2]
STACK = ROOT / ".claude" / "scripts" / "stack"
COMMIT = ROOT / "scripts" / "ai" / "commit.sh"
VALIDATE = ROOT / "scripts" / "ai" / "validate-changeset.sh"
AUTONOMY = ROOT / "scripts" / "ai" / "autonomy-tier.sh"
HOOK_CONFIG = ROOT / ".claude" / "hooks" / "hook-config.yaml"
HARD_BLOCK = "[HARD-BLOCK — DO NOT RETRY]"
ACTION_STAGES = {"create_stack": "auto_stack", "commit": "auto_commit",
                 "push": "auto_push", "open_pr": "auto_pr"}
ACTION_SUCCESSORS = {
    "create_stack": frozenset({"editing", "awaiting_work"}),
    "commit": frozenset({"push"}),
    "push": frozenset({"open_pr"}),
    "open_pr": frozenset({"wait_ci"}),
}
EDITING_ACTIONS = frozenset({"editing", "awaiting_work"})
PROHIBITED_ACTIONS = frozenset({"merge_eligible", "sync", "cleanup"})
SUCCESS_CHECK_STATES = frozenset({"pass", "passed", "success", "successful", "completed"})
FAILED_CHECK_STATES = frozenset({"fail", "failed", "failure", "cancel", "cancelled",
                                 "canceled", "timed_out", "error"})
PENDING_CHECK_STATES = frozenset({"pending", "queued", "waiting", "requested",
                                  "in_progress", "in-progress", "running"})
OID_RE = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
SAFE_AUDIT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
SESSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}\Z")
ACTOR_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\Z")
WATCHER_DEFAULT_POLLS = 80
WATCHER_READY_TIMEOUT = 3.0
WATCHER_STALE_SECONDS = 300.0
COMMAND_TIMEOUT = 30.0
MAX_COMMAND_TIMEOUT = 300.0
PROCESS_TERM_GRACE = 1.0
CONTROL_PLANE_PATHS = (
    ".claude-atomic.yaml",
    ".claude/hooks",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/scripts/stack",
    ".claude/scripts/pr-stack",
    "ai/config/claude",
    "scripts/ai/autonomy-tier.sh",
    "scripts/ai/commit.sh",
    "scripts/ai/git_lifecycle.py",
    "scripts/ai/lifecycle_adapter.py",
    "scripts/ai/validate-changeset.sh",
)
READ_ONLY_GIT = frozenset({
    "diff", "diff-tree", "log", "ls-files", "ls-tree", "merge-base",
    "rev-list", "rev-parse", "show", "status",
})
READ_ONLY_GH_PR = frozenset({"checks", "list", "status", "view"})

class AdapterError(RuntimeError):
    def __init__(self, message: str, code: str = "adapter_error"):
        super().__init__(message)
        self.code = code


class ProcessSignal(BaseException):
    def __init__(self, signum: int):
        super().__init__(signum)
        self.signum = signum
def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
def stable_key(prefix: str, payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return f"adapter:{prefix}:{hashlib.sha256(encoded).hexdigest()}"
def process_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "GIT_ASKPASS": "/usr/bin/false",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_SSH_COMMAND": "ssh -oBatchMode=yes",
        "GIT_TERMINAL_PROMPT": "0",
        "GH_PROMPT_DISABLED": "1",
        "PAGER": "cat",
    })
    if extra:
        env.update(extra)
    return env

def process_group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def terminate_lingering_processes(pgid: int) -> None:
    if not process_group_alive(pgid):
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + PROCESS_TERM_GRACE
    while process_group_alive(pgid) and time.monotonic() < deadline:
        time.sleep(0.02)
    if process_group_alive(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def terminate_process_group(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is not None:
        proc.wait()
        terminate_lingering_processes(proc.pid)
        return
    deadline = time.monotonic() + PROCESS_TERM_GRACE
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except OSError:
        try:
            proc.terminate()
        except OSError:
            pass
    try:
        proc.wait(timeout=PROCESS_TERM_GRACE)
    except subprocess.TimeoutExpired:
        pass
    while process_group_alive(proc.pid) and time.monotonic() < deadline:
        time.sleep(0.02)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        try:
            proc.kill()
        except OSError:
            pass
    proc.wait()

def bounded_process(
    args: Sequence[str | Path], cwd: Path, *, check: bool = True,
    timeout: float = COMMAND_TIMEOUT, text: bool = True,
    input_data: bytes | str | None = None, env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[Any]:
    bounded_timeout = min(max(float(timeout), 0.1), MAX_COMMAND_TIMEOUT)
    values = [str(item) for item in args]
    try:
        proc = subprocess.Popen(
            values, cwd=str(cwd), env=process_environment(env),
            stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text,
            start_new_session=True, close_fds=True,
        )
    except OSError as exc:
        raise AdapterError("external process could not be started", "action_command_start_failed") from exc

    previous_handlers: dict[int, Any] = {}
    if threading.current_thread() is threading.main_thread():
        def interrupt(signum: int, _frame: Any) -> None:
            raise ProcessSignal(signum)
        for signum in (signal.SIGHUP, signal.SIGTERM):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, interrupt)
    try:
        try:
            stdout, stderr = proc.communicate(input=input_data, timeout=bounded_timeout)
        except subprocess.TimeoutExpired as exc:
            terminate_process_group(proc)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            raise AdapterError("external process timed out", "action_command_timeout") from exc
        except BaseException:
            terminate_process_group(proc)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except OSError:
                        pass
            raise
    except ProcessSignal as exc:
        raise SystemExit(128 + exc.signum) from None
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    terminate_lingering_processes(proc.pid)
    result = subprocess.CompletedProcess(values, proc.returncode, stdout, stderr)
    if check and result.returncode:
        raise AdapterError(
            f"canonical action failed with exit status {result.returncode}",
            "action_command_failed",
        )
    return result

def run_command(
    args: Sequence[str | Path], cwd: Path, *, check: bool = True,
    timeout: float = COMMAND_TIMEOUT, env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return bounded_process(args, cwd, check=check, timeout=timeout, env=env)

def bounded_git(
    cwd: Path | str, *args: str, check: bool = True, text: bool = True,
    input_data: bytes | str | None = None, env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[Any]:
    try:
        return bounded_process(
            ["git", *args], Path(cwd), check=check, text=text,
            input_data=input_data, env=env,
        )
    except AdapterError as exc:
        if exc.code == "action_command_failed":
            raise lifecycle.LifecycleError(f"git {' '.join(args)} failed", "git_error") from exc
        raise

lifecycle.git = bounded_git
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
    if not isinstance(value, str) or not SESSION_RE.fullmatch(value):
        raise AdapterError("invalid Claude session identity", "invalid_session")
    return value
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
def reverse_binding_path(common_dir: Path, run_id: str) -> Path:
    lifecycle.validate_name(run_id, lifecycle.RUN_ID_RE, "run id")
    return adapter_root(common_dir) / "run-bindings" / f"{hashlib.sha256(run_id.encode()).hexdigest()}.json"
def contract_path(common_dir: Path, run_id: str) -> Path:
    lifecycle.validate_name(run_id, lifecycle.RUN_ID_RE, "run id")
    return adapter_root(common_dir) / "contracts" / f"{hashlib.sha256(run_id.encode()).hexdigest()}.json"
def strip_policy_comment(raw: str) -> str:
    quote: str | None = None
    result: list[str] = []
    for character in raw:
        if character in {"'", '"'}:
            quote = None if quote == character else character if quote is None else quote
        if character == "#" and quote is None:
            break
        result.append(character)
    return "".join(result).rstrip()
def policy_blocks(root: Path) -> tuple[bytes, dict[str, dict[str, str]]]:
    config = root / ".claude-atomic.yaml"
    try:
        fd = os.open(config, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise AdapterError("lifecycle policy is unavailable", "invalid_lifecycle_config") from exc
    try:
        metadata = os.fstat(fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
        ):
            raise AdapterError(
                "lifecycle policy must be an owned single-link regular file",
                "invalid_lifecycle_config",
            )
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        data = b"".join(chunks)
        text = data.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise AdapterError("lifecycle policy is unavailable", "invalid_lifecycle_config") from exc
    finally:
        os.close(fd)
    relevant = {"lifecycle", "pipeline", "autonomy_override"}
    blocks: dict[str, dict[str, str]] = {}
    current: str | None = None
    for number, raw in enumerate(text.splitlines(), 1):
        clean = strip_policy_comment(raw)
        if not clean.strip():
            continue
        if not clean[0].isspace():
            match = re.fullmatch(r"([A-Za-z0-9_-]+):\s*", clean)
            current = match.group(1) if match else None
            if current in relevant:
                if current in blocks:
                    raise AdapterError(f"duplicate lifecycle policy block at line {number}", "invalid_lifecycle_config")
                blocks[current] = {}
            continue
        if current not in relevant:
            continue
        match = re.fullmatch(r"  ([A-Za-z0-9_-]+):\s*(.*?)\s*", clean)
        if not match or not match.group(2):
            raise AdapterError(f"malformed lifecycle policy key at line {number}", "invalid_lifecycle_config")
        key, value = match.groups()
        if key in blocks[current]:
            raise AdapterError(f"duplicate lifecycle policy key at line {number}", "invalid_lifecycle_config")
        blocks[current][key] = value.strip("'\"")
    return data, blocks
def tier_number(value: str) -> int:
    match = re.fullmatch(r"A([0-4])", value)
    if match is None:
        raise AdapterError("lifecycle autonomy tier is malformed", "invalid_lifecycle_config")
    return int(match.group(1))
def policy_snapshot(root: Path) -> dict[str, Any]:
    data, blocks = policy_blocks(root)
    lifecycle_block = blocks.get("lifecycle", {})
    if lifecycle_block.get("enabled", "").lower() not in {"true", "yes", "on", "1"}:
        raise AdapterError("lifecycle control is not enabled", "not_opted_in")
    if lifecycle_block.get("rollout_approved", "").lower() not in {"true", "yes", "on", "1"}:
        raise AdapterError("lifecycle rollout is not approved", "rollout_not_approved")
    approver = lifecycle_block.get("rollout_approved_by", "")
    if not ACTOR_RE.fullmatch(approver):
        raise AdapterError("lifecycle rollout approver is invalid", "rollout_not_approved")
    github_actor = lifecycle_block.get("github_actor", "")
    if not ACTOR_RE.fullmatch(github_actor):
        raise AdapterError("lifecycle GitHub actor is invalid", "invalid_lifecycle_config")
    pipeline = blocks.get("pipeline", {})
    override = blocks.get("autonomy_override", {})
    allowed_stages = set(ACTION_STAGES.values())
    if set(pipeline) & allowed_stages != allowed_stages:
        raise AdapterError("lifecycle pipeline policy is incomplete", "invalid_lifecycle_config")
    required_override = {"tier", "basis", "stages", "expires", "signed_off_by", "decision"}
    if set(override) != required_override:
        raise AdapterError("lifecycle rollout override is incomplete", "invalid_lifecycle_config")
    if override["basis"] != "risk-accepted" or len(override["decision"].strip()) < 3:
        raise AdapterError("lifecycle rollout override basis is invalid", "invalid_lifecycle_config")
    try:
        expiry = dt.date.fromisoformat(override["expires"])
    except ValueError as exc:
        raise AdapterError("lifecycle rollout override expiry is malformed", "invalid_lifecycle_config") from exc
    if expiry < dt.datetime.now(dt.timezone.utc).date():
        raise AdapterError("lifecycle rollout override is expired", "invalid_lifecycle_config")
    if not ACTOR_RE.fullmatch(override["signed_off_by"]):
        raise AdapterError("lifecycle rollout override is unsigned", "invalid_lifecycle_config")
    stages = override["stages"].split()
    if not stages or len(stages) != len(set(stages)) or set(stages) != allowed_stages:
        raise AdapterError("lifecycle rollout override stages are invalid", "invalid_lifecycle_config")
    override_tier = tier_number(override["tier"])
    autonomy: dict[str, str] = {}
    for stage in sorted(allowed_stages):
        declared = tier_number(pipeline[stage])
        autonomy[stage] = f"A{min(declared, override_tier)}"
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "rollout_approved": True,
        "rollout_approved_by": approver,
        "github_actor": github_actor,
        "override_signed_off_by": override["signed_off_by"],
        "override_expires": override["expires"],
        "autonomy": autonomy,
    }
def remote_urls(target: lifecycle.Repo) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for name, args in (("fetch", ("remote", "get-url", "--all", "origin")),
                       ("push", ("remote", "get-url", "--push", "--all", "origin"))):
        proc = lifecycle.git(target.root, *args, check=False)
        result[name] = sorted(line.strip() for line in proc.stdout.splitlines() if line.strip()) if proc.returncode == 0 else []
    return result
def normalize_github_https_url(url: str | None) -> tuple[str, str] | None:
    if not isinstance(url, str) or not url:
        return None
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except (ValueError, UnicodeError):
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or port is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return None
    if parsed.username is not None and not re.fullmatch(r"[A-Za-z0-9._-]+", parsed.username):
        return None
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2:
        return None
    owner, name = parts
    if name.endswith(".git"):
        name = name[:-4]
    component = re.compile(r"[A-Za-z0-9_.-]+\Z")
    if not component.fullmatch(owner) or not component.fullmatch(name):
        return None
    repository = f"{owner}/{name}"
    return repository, f"https://github.com/{repository}.git"


def normalize_github_repository(url: str | None) -> str | None:
    normalized = normalize_github_https_url(url)
    return normalized[0] if normalized else None


def strict_origin_identity(remotes: dict[str, list[str]]) -> tuple[str, str]:
    fetch, push = remotes.get("fetch"), remotes.get("push")
    if not isinstance(fetch, list) or not isinstance(push, list) or len(fetch) != 1 or len(push) != 1:
        raise AdapterError("origin must have exactly one HTTPS fetch and push URL", "origin_url_ambiguous")
    fetch_identity = normalize_github_https_url(fetch[0])
    push_identity = normalize_github_https_url(push[0])
    if fetch_identity is None or push_identity is None:
        raise AdapterError("origin is not a recognized GitHub HTTPS URL", "origin_url_unrecognized")
    if (
        fetch_identity[0].casefold() != push_identity[0].casefold()
        or fetch_identity[1].casefold() != push_identity[1].casefold()
    ):
        raise AdapterError("origin fetch and push identities differ", "origin_url_drift")
    return fetch_identity


def capture_contract(repo: lifecycle.Repo, run_id: str, target: lifecycle.Repo) -> dict[str, Any]:
    policy = policy_snapshot(target.root)
    remotes = remote_urls(target)
    repository, github_url = strict_origin_identity(remotes)
    value = {
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "run_id": run_id,
        "captured_at": now(),
        "policy": policy,
        "origin": remotes,
        "github_repository": repository,
        "github_url": github_url,
        "expected_actor": policy["github_actor"],
    }
    lifecycle.atomic_json(contract_path(repo.common_dir, run_id), value)
    return value

def load_contract(repo: lifecycle.Repo, run_id: str) -> dict[str, Any]:
    value = read_json(contract_path(repo.common_dir, run_id), "invalid_run_contract")
    if value.get("schema_version") != ADAPTER_SCHEMA_VERSION or value.get("run_id") != run_id:
        raise AdapterError("lifecycle run contract is malformed", "invalid_run_contract")
    policy = value.get("policy")
    if (
        not isinstance(policy, dict)
        or not isinstance(value.get("origin"), dict)
        or value.get("expected_actor") != policy.get("github_actor")
        or not isinstance(value.get("expected_actor"), str)
        or not isinstance(value.get("github_repository"), str)
        or not isinstance(value.get("github_url"), str)
    ):
        raise AdapterError("lifecycle run contract is malformed", "invalid_run_contract")
    try:
        repository, github_url = strict_origin_identity(value["origin"])
    except AdapterError as exc:
        raise AdapterError("lifecycle run contract has invalid origin identity", "invalid_run_contract") from exc
    if (
        repository.casefold() != value["github_repository"].casefold()
        or github_url.casefold() != value["github_url"].casefold()
    ):
        raise AdapterError("lifecycle run contract identity is inconsistent", "invalid_run_contract")
    return value
def pipeline_gate_level() -> str:
    try:
        lines = HOOK_CONFIG.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise AdapterError("pipeline gate configuration is unavailable", "pipeline_gate_unavailable") from exc
    values = []
    for raw in lines:
        clean = strip_policy_comment(raw).strip()
        match = re.fullmatch(r"git-pipeline-gate:\s*([^\s]+)", clean)
        if match:
            values.append(match.group(1).strip("'\""))
    if len(values) != 1 or values[0] not in {"off", "warn", "block"}:
        raise AdapterError("pipeline gate configuration is malformed", "pipeline_gate_unavailable")
    return values[0]
def verify_contract(repo: lifecycle.Repo, state: dict[str, Any], target: lifecycle.Repo) -> dict[str, Any]:
    contract = load_contract(repo, state["run_id"])
    current_policy = policy_snapshot(target.root)
    if current_policy["sha256"] != contract["policy"].get("sha256"):
        raise AdapterError("lifecycle policy changed after run start", "policy_drift")
    if remote_urls(target) != contract["origin"]:
        raise AdapterError("origin identity changed after run start", "remote_drift")
    if pipeline_gate_level() == "off":
        raise AdapterError("live git pipeline gate is off", "pipeline_gate_off")
    return contract
def path_overlaps_control_plane(path: str) -> bool:
    parts = tuple(part.casefold() for part in PurePosixPath(path).parts)
    return any(
        parts[:len(control_parts)] == control_parts or control_parts[:len(parts)] == parts
        for control in CONTROL_PLANE_PATHS
        for control_parts in (tuple(part.casefold() for part in PurePosixPath(control).parts),)
    )
def validate_owned_paths(paths: Sequence[str], root: Path | None = None) -> None:
    resolved_root = root.resolve() if root is not None else None
    for path in paths:
        if path_overlaps_control_plane(path):
            raise AdapterError("owned path overlaps lifecycle control plane", "control_plane_owned")
        if resolved_root is not None:
            try:
                physical = (resolved_root / path).resolve(strict=False).relative_to(resolved_root).as_posix()
            except ValueError as exc:
                raise AdapterError("owned path escapes lifecycle worktree", "control_plane_owned") from exc
            if path_overlaps_control_plane(physical):
                raise AdapterError("owned path resolves into lifecycle control plane", "control_plane_owned")
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
def binding_record(repo: lifecycle.Repo, session_id: str) -> dict[str, Any]:
    value = read_json(binding_path(repo.common_dir, session_id), "invalid_binding")
    if (
        value.get("schema_version") != ADAPTER_SCHEMA_VERSION
        or value.get("session_key") != session_key(session_id)
        or not isinstance(value.get("run_id"), str)
        or value.get("status") not in {"bound", "released"}
    ):
        raise AdapterError("lifecycle session binding is malformed", "invalid_binding")
    return value

def load_binding(repo: lifecycle.Repo, session_id: str) -> dict[str, Any]:
    value = binding_record(repo, session_id)
    if value["status"] != "bound":
        raise AdapterError("Claude session has no bound lifecycle run", "run_unbound")
    reverse = read_json(reverse_binding_path(repo.common_dir, value["run_id"]), "invalid_binding")
    if (
        reverse.get("schema_version") != ADAPTER_SCHEMA_VERSION
        or reverse.get("run_id") != value["run_id"]
        or reverse.get("session_key") != session_key(session_id)
        or reverse.get("status") != "bound"
    ):
        raise AdapterError("reverse lifecycle session binding is malformed", "invalid_binding")
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
        try:
            current = binding_record(repo, session_id)
        except AdapterError as exc:
            if exc.code != "run_unbound":
                raise
            current = None
        if current and current["status"] == "bound":
            if current["run_id"] == run_id:
                load_binding(repo, session_id)
                return current
            if load_run_state(repo, current["run_id"])["terminal"] is None:
                raise AdapterError(
                    "Claude session is already bound to a nonterminal lifecycle run",
                    "session_already_bound",
                )
    reverse_path = reverse_binding_path(repo.common_dir, run_id)
    if reverse_path.exists():
        reverse = read_json(reverse_path, "invalid_binding")
        if (
            reverse.get("schema_version") != ADAPTER_SCHEMA_VERSION
            or reverse.get("run_id") != run_id
            or reverse.get("status") not in {"bound", "released"}
        ):
            raise AdapterError("reverse lifecycle session binding is malformed", "invalid_binding")
        if reverse["status"] == "bound" and reverse.get("session_key") != session_key(session_id):
            raise AdapterError("lifecycle run is bound to another live Claude session", "run_already_bound")
        if reverse["status"] == "released" and reverse.get("session_key") != session_key(session_id):
            raise AdapterError("released lifecycle run requires explicit takeover", "takeover_required")
    timestamp = now()
    value = {
        "schema_version": ADAPTER_SCHEMA_VERSION, "session_key": session_key(session_id),
        "run_id": run_id, "status": "bound", "bound_at": timestamp,
    }
    reverse = {
        "schema_version": ADAPTER_SCHEMA_VERSION, "run_id": run_id,
        "session_key": session_key(session_id), "status": "bound", "bound_at": timestamp,
    }
    lifecycle.atomic_json(reverse_path, reverse)
    lifecycle.atomic_json(path, value)
    return value
def write_binding(repo: lifecycle.Repo, session_id: str, run_id: str) -> dict[str, Any]:
    with lifecycle.RepoLock(adapter_lock_path(repo.common_dir), 10):
        return _write_binding_locked(repo, session_id, run_id)
def secure_directory(path: Path) -> int:
    absolute = Path(os.path.abspath(os.fspath(path)))
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open("/", flags)
    try:
        for part in absolute.parts[1:]:
            try:
                os.mkdir(part, 0o700, dir_fd=fd)
            except FileExistsError:
                pass
            next_fd = os.open(part, flags, dir_fd=fd)
            metadata = os.fstat(next_fd)
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid not in {0, os.getuid()}:
                os.close(next_fd)
                raise AdapterError("adapter state directory is unsafe", "audit_directory_invalid")
            os.close(fd)
            fd = next_fd
        if os.fstat(fd).st_uid != os.getuid():
            raise AdapterError("adapter state directory is not user-owned", "audit_directory_invalid")
        return fd
    except BaseException:
        os.close(fd)
        raise

def secure_file(path: Path, flags: int) -> int:
    parent_fd = secure_directory(path.parent)
    try:
        fd = os.open(
            path.name,
            flags | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_fd,
        )
    finally:
        os.close(parent_fd)
    metadata = os.fstat(fd)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
    ):
        os.close(fd)
        raise AdapterError("adapter state target is not an owned single-link file", "audit_file_invalid")
    os.fchmod(fd, 0o600)
    if stat.S_IMODE(os.fstat(fd).st_mode) != 0o600:
        os.close(fd)
        raise AdapterError("adapter state permissions are unsafe", "audit_mode_invalid")
    return fd

def write_all(fd: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(fd, data[offset:])
        if written <= 0:
            raise AdapterError("adapter audit append was incomplete", "audit_write_failed")
        offset += written

def read_adapter_audit(fd: int) -> tuple[dict[str, dict[str, Any]], int]:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    data = b"".join(chunks)
    newline = data.rfind(b"\n")
    complete_end = newline + 1 if newline >= 0 else 0
    complete = data[:complete_end]
    records: dict[str, dict[str, Any]] = {}
    for number, line in enumerate(complete.splitlines(), 1):
        if not line:
            raise AdapterError(f"adapter audit line {number} is empty", "audit_file_invalid")
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise AdapterError(f"adapter audit line {number} is malformed", "audit_file_invalid") from exc
        event_id = value.get("event_id") if isinstance(value, dict) else None
        if not isinstance(event_id, str) or event_id in records:
            raise AdapterError(f"adapter audit line {number} has invalid identity", "audit_file_invalid")
        records[event_id] = value
    if complete_end != len(data):
        os.ftruncate(fd, complete_end)
        os.fsync(fd)
    return records, complete_end

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
        fd = secure_file(path, os.O_RDWR)
        try:
            records, _ = read_adapter_audit(fd)
            prior = records.get(event_id)
            if prior is not None:
                comparable = {key: value for key, value in prior.items() if key != "timestamp"}
                expected = {key: value for key, value in record.items() if key != "timestamp"}
                if comparable != expected:
                    raise AdapterError("adapter audit event identity conflicts", "audit_file_invalid")
                return
            os.lseek(fd, 0, os.SEEK_END)
            write_all(fd, (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode())
            os.fsync(fd)
            directory_fd = secure_directory(path.parent)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            os.close(fd)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

def best_effort_audit(*args: Any, **kwargs: Any) -> None:
    try:
        append_adapter_audit(*args, **kwargs)
    except Exception:
        return
def decision_head(decision: dict[str, Any]) -> str | None:
    git_view = decision.get("evidence", {}).get("git")
    return git_view.get("head_sha") if isinstance(git_view, dict) else None
def inspect_bound(repo: lifecycle.Repo, run_id: str) -> dict[str, Any]:
    return lifecycle.inspect_run(repo.root, run_id)
def precheck_binding(repo: lifecycle.Repo, session_id: str, requested: str | None) -> str | None:
    if not binding_path(repo.common_dir, session_id).exists():
        return requested
    try:
        current = load_binding(repo, session_id)
    except AdapterError as exc:
        if exc.code == "run_unbound":
            return requested
        raise
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
    normalized_owned = lifecycle.normalize_paths(args.owned_paths, repo.root)
    validate_owned_paths(normalized_owned, repo.root)
    preflight_target = lifecycle.discover_repo(args.worktree) if args.worktree else repo
    if preflight_target.common_dir != repo.common_dir:
        raise AdapterError("requested worktree belongs to another repository", "worktree_repository_mismatch")
    policy_snapshot(preflight_target.root)
    strict_origin_identity(remote_urls(preflight_target))
    payload = {
        "task": args.task, "base_branch": args.base_branch, "base_sha": args.base_sha,
        "intended_branch": args.intended_branch, "owned_paths": normalized_owned,
        "worktree": args.worktree, "unit_id": args.work_unit_id, "unit": args.work_unit,
    }
    key = args.idempotency_key or stable_key("start", payload)
    with lifecycle.RepoLock(adapter_lock_path(repo.common_dir), args.lock_timeout):
        run_id = precheck_binding(repo, session_id, args.run_id)
        result = lifecycle.start_run(
            repo.root, run_id=run_id, task=args.task, base_branch=args.base_branch,
            base_sha=args.base_sha, intended_branch=args.intended_branch,
            owned_paths=normalized_owned, worktree=args.worktree, unit_id=args.work_unit_id,
            unit_description=args.work_unit, key=key, timeout=args.lock_timeout,
        )
        run_id = result["run_id"]
        try:
            state = load_run_state(repo, run_id)
            target = action_target(repo, state)
            validate_owned_paths(state["owned_paths"], target.root)
            contract_file = contract_path(repo.common_dir, run_id)
            if result.get("idempotent"):
                contract = load_contract(repo, run_id)
                if policy_snapshot(target.root)["sha256"] != contract["policy"].get("sha256"):
                    raise AdapterError("idempotent run policy no longer matches", "policy_drift")
            else:
                capture_contract(repo, run_id, target)
            _write_binding_locked(repo, session_id, run_id)
        except Exception as exc:
            if not result.get("idempotent"):
                halt_unbound_run(repo, run_id, args.lock_timeout)
                contract_file.unlink(missing_ok=True)
            code = exc.code if isinstance(exc, AdapterError) and exc.code in {
                "invalid_lifecycle_config", "rollout_not_approved", "policy_drift",
                "control_plane_owned", "invalid_run_contract", "origin_url_ambiguous",
                "origin_url_unrecognized", "origin_url_drift",
            } else "binding_persist_failed"
            raise AdapterError("Claude lifecycle start could not persist its immutable binding", code) from exc
    if not result.get("idempotent"):
        append_adapter_audit(repo.common_dir, run_id, "session_bind", "success")
    return {
        "ok": True, "enabled": True, "bound": True, "run_id": run_id,
        "controller": result, "status": inspect_bound(repo, run_id),
    }

def release_session(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    repo = require_opt_in(cwd)
    session_id = effective_session(args.session_id)
    with lifecycle.RepoLock(adapter_lock_path(repo.common_dir), args.lock_timeout):
        binding = load_binding(repo, session_id)
        if args.run_id != binding["run_id"]:
            raise AdapterError("release run does not match session binding", "run_binding_mismatch")
        timestamp = now()
        lifecycle.atomic_json(binding_path(repo.common_dir, session_id), {
            **binding, "status": "released", "released_at": timestamp, "release_reason": args.reason,
        })
        lifecycle.atomic_json(reverse_binding_path(repo.common_dir, args.run_id), {
            "schema_version": ADAPTER_SCHEMA_VERSION, "run_id": args.run_id,
            "session_key": session_key(session_id), "status": "released",
            "released_at": timestamp, "release_reason": args.reason,
        })
    append_adapter_audit(repo.common_dir, args.run_id, "session_release", "success")
    return {"ok": True, "enabled": True, "bound": False, "run_id": args.run_id}

def takeover_session(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    repo = require_opt_in(cwd)
    session_id = effective_session(args.session_id)
    prior_session = effective_session(args.from_session_id)
    with lifecycle.RepoLock(adapter_lock_path(repo.common_dir), args.lock_timeout):
        precheck_binding(repo, session_id, args.run_id)
        prior = binding_record(repo, prior_session)
        reverse = read_json(reverse_binding_path(repo.common_dir, args.run_id), "invalid_binding")
        if (
            prior.get("run_id") != args.run_id
            or prior.get("status") != "released"
            or reverse.get("schema_version") != ADAPTER_SCHEMA_VERSION
            or reverse.get("run_id") != args.run_id
            or reverse.get("status") != "released"
            or reverse.get("session_key") != session_key(prior_session)
        ):
            raise AdapterError("run is not explicitly released by the prior session", "takeover_not_released")
        value = {
            "schema_version": ADAPTER_SCHEMA_VERSION, "session_key": session_key(session_id),
            "run_id": args.run_id, "status": "bound", "bound_at": now(),
            "takeover_from": session_key(prior_session), "takeover_reason": args.reason,
        }
        lifecycle.atomic_json(reverse_binding_path(repo.common_dir, args.run_id), {
            "schema_version": ADAPTER_SCHEMA_VERSION, "run_id": args.run_id,
            "session_key": session_key(session_id), "status": "bound", "bound_at": value["bound_at"],
        })
        lifecycle.atomic_json(binding_path(repo.common_dir, session_id), value)
    append_adapter_audit(repo.common_dir, args.run_id, "session_takeover", "success")
    return {"ok": True, "enabled": True, "bound": True, "run_id": args.run_id}

def ready(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    session_id = effective_session(args.session_id)
    repo, binding, state = bound_state(cwd, session_id, args.run_id)
    validate_owned_paths(state["owned_paths"], action_target(repo, state).root)
    verify_contract(repo, state, action_target(repo, state))
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
    repo, binding, state = bound_state(cwd, session_id, args.run_id)
    validate_owned_paths(state["owned_paths"], action_target(repo, state).root)
    verify_contract(repo, state, action_target(repo, state))
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
def recover_edit(args: argparse.Namespace, cwd: Path) -> dict[str, Any]:
    session_id = effective_session(args.session_id)
    repo, binding, state = bound_state(cwd, session_id, args.run_id)
    marker = repo.common_dir / "autonomy-demoted-auto_commit"
    if not marker.is_file():
        raise AdapterError("commit recovery requires a persisted commit demotion", "recovery_not_required")
    validate_owned_paths(state["owned_paths"], action_target(repo, state).root)
    verify_contract(repo, state, action_target(repo, state))
    result = lifecycle.recover_edit_run(
        repo.root, run_id=binding["run_id"], reason=args.reason,
        key=args.idempotency_key or stable_key("recover-edit", {
            "run_id": binding["run_id"], "reason": args.reason,
        }), timeout=args.lock_timeout,
    )
    append_adapter_audit(repo.common_dir, binding["run_id"], "commit_recovery", "success", action="commit", stage="auto_commit")
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
def resolve_autonomy(
    repo: lifecycle.Repo, state: dict[str, Any], stage: str,
) -> tuple[bool, str]:
    contract = load_contract(repo, state["run_id"])
    raw = contract.get("policy", {}).get("autonomy", {}).get(stage)
    match = re.fullmatch(r"A([0-4])", raw) if isinstance(raw, str) else None
    if match is None:
        return False, "autonomy_snapshot_invalid"
    tier = int(match.group(1))
    marker = repo.common_dir / f"autonomy-demoted-{stage}"
    if marker.exists():
        tier = max(0, tier - 1)
    return (tier >= 2, "authorized" if tier >= 2 else "autonomy_below_a2")
def action_target(repo: lifecycle.Repo, state: dict[str, Any]) -> lifecycle.Repo:
    target, _ = lifecycle.target_repo(state, repo)
    return target
def action_create_stack(repo: lifecycle.Repo, state: dict[str, Any], _: dict[str, Any]) -> None:
    start_root = Path(state["repository"]["start_worktree"])
    run_command([STACK, "create", state["intended_branch"], state["base"]["branch"],
                 "--base-sha", state["base"]["sha"], "--strict"], start_root)
def staged_paths(repo: lifecycle.Repo, env: dict[str, str] | None = None) -> list[str]:
    raw = lifecycle.git(repo.root, "diff", "--cached", "--name-status", "-z",
                        "--find-renames", text=False, env=env).stdout
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
def private_index_path(repo: lifecycle.Repo, run_id: str) -> Path:
    root = adapter_root(repo.common_dir) / "private-indexes"
    directory_fd = secure_directory(root)
    os.close(directory_fd)
    fd, raw = tempfile.mkstemp(prefix=f"{hashlib.sha256(run_id.encode()).hexdigest()}-", dir=root)
    os.close(fd)
    path = Path(raw)
    path.unlink()
    return path
def regular_owned_bytes(path: Path) -> bytes | None:
    try:
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
        ):
            return None
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return None
    try:
        opened = os.fstat(fd)
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            return None
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    finally:
        os.close(fd)


def reconcile_default_index(target: lifecycle.Repo, prior: bytes, approved: Path) -> bool:
    index = target.git_dir / "index"
    lock = target.git_dir / "index.lock"
    proposed = regular_owned_bytes(approved)
    if proposed is None:
        return False
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(lock, flags, 0o600)
    except FileExistsError:
        return False
    except OSError:
        return False
    installed = False
    try:
        if regular_owned_bytes(index) != prior:
            return False
        write_all(fd, proposed)
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(lock, index)
        installed = True
        directory_fd = os.open(
            target.git_dir,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return True
    finally:
        if fd >= 0:
            os.close(fd)
        if not installed:
            lock.unlink(missing_ok=True)

def action_commit(repo: lifecycle.Repo, state: dict[str, Any], decision: dict[str, Any]) -> None:
    expected = commit_guard(state)
    target, ready = verify_commit_cas(repo, state, decision, expected)
    branch = state["intended_branch"]
    lifecycle.validate_branch(target, branch, intended=True)
    if decision.get("evidence", {}).get("git", {}).get("branch") != branch:
        raise AdapterError("commit target branch changed", "commit_cas_failed")
    index_path = private_index_path(repo, state["run_id"])
    index_env = {"GIT_INDEX_FILE": str(index_path)}
    pathspecs = [f":(literal){path}" for path in expected[1]]
    default_tree = lifecycle.git(target.root, "write-tree").stdout.strip()
    default_index = regular_owned_bytes(target.git_dir / "index")
    parent_tree = lifecycle.git(target.root, "show", "-s", "--format=%T", expected[0]).stdout.strip()
    try:
        lifecycle.git(target.root, "read-tree", expected[0], env=index_env)
        lifecycle.git(target.root, "add", "-A", "--", *pathspecs, env=index_env)
        if tuple(staged_paths(target, index_env)) != expected[1]:
            raise AdapterError("private index differs from approved paths", "staged_paths_mismatch")
        tree = lifecycle.git(target.root, "write-tree", env=index_env).stdout.strip()
        lifecycle.validate_oid(tree)
        if lifecycle.commit_fingerprint(target, tree, expected[1]) != expected[2]:
            raise AdapterError("private index tree differs from approved content", "commit_cas_failed")
        try:
            run_command([VALIDATE, "--json"], target.root, env=index_env)
        except AdapterError as exc:
            raise AdapterError("approved commit validation failed", "commit_validation_failed") from exc
        current = load_run_state(repo, state["run_id"])
        verify_commit_cas(repo, current, inspect_bound(repo, state["run_id"]), expected)
        if lifecycle.git(target.root, "write-tree", env=index_env).stdout.strip() != tree:
            raise AdapterError("private index changed during validation", "commit_cas_failed")
        commit_env = {
            **index_env,
            "LIFECYCLE_COMMIT_MODE": "private-v1",
            "LIFECYCLE_EXPECTED_PARENT": expected[0],
            "LIFECYCLE_EXPECTED_REF": f"refs/heads/{branch}",
            "LIFECYCLE_EXPECTED_TREE": tree,
        }
        run_command([COMMIT, "-m", ready["subject"], "-m", ready["body"]], target.root, env=commit_env)
        head = lifecycle.exact_head(target)
        parents = lifecycle.git(target.root, "rev-list", "--parents", "-n", "1", head).stdout.split()
        actual_tree = lifecycle.git(target.root, "show", "-s", "--format=%T", head).stdout.strip()
        if len(parents) != 2 or parents[1] != expected[0] or actual_tree != tree:
            raise AdapterError("canonical commit result violates approved CAS", "commit_cas_failed")
        # The commit never reads the default index. Install the approved private
        # index only while holding Git's index lock and only if the prior bytes are
        # unchanged; concurrent staging therefore survives and cannot enter commit.
        if default_tree == parent_tree and default_index is not None:
            reconcile_default_index(target, default_index, index_path)
    finally:
        index_path.unlink(missing_ok=True)
def pinned_github_environment(target: lifecycle.Repo, contract: dict[str, Any]) -> dict[str, str]:
    actor = contract.get("expected_actor")
    if not isinstance(actor, str) or not ACTOR_RE.fullmatch(actor):
        raise AdapterError("run lacks a pinned GitHub actor", "github_identity_unpinned")
    token_proc = run_command(
        ["gh", "auth", "token", "--hostname", "github.com", "--user", actor],
        target.root,
        check=False,
        env={"GH_TOKEN": "", "GITHUB_TOKEN": "", "GH_ENTERPRISE_TOKEN": "", "GITHUB_ENTERPRISE_TOKEN": ""},
    )
    token = token_proc.stdout.strip()
    if (
        token_proc.returncode
        or not token
        or len(token) > 4096
        or re.fullmatch(r"[A-Za-z0-9_.-]+", token) is None
    ):
        raise AdapterError("pinned GitHub credential is unavailable", "github_token_unavailable")
    env = {"GH_TOKEN": token}
    actor_proc = run_command(
        ["gh", "api", "--hostname", "github.com", "/user", "--jq", ".login"],
        target.root,
        check=False,
        env=env,
    )
    if actor_proc.returncode or actor_proc.stdout.strip() != actor:
        raise AdapterError("pinned GitHub credential belongs to another actor", "github_token_actor_mismatch")
    return env


@contextlib.contextmanager
def github_askpass_environment(
    credential_env: dict[str, str], actor: str,
) -> Any:
    with tempfile.TemporaryDirectory(prefix="claude-lifecycle-github-") as directory:
        askpass = Path(directory) / "askpass.sh"
        askpass.write_text(
            "#!/bin/sh\n"
            "case \"$1\" in\n"
            "  *sername*) printf '%s\\n' \"$LIFECYCLE_GITHUB_ACTOR\" ;;\n"
            "  *assword*) printf '%s\\n' \"$LIFECYCLE_GITHUB_TOKEN\" ;;\n"
            "  *) exit 1 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        askpass.chmod(0o700)
        yield {
            **credential_env,
            "GIT_ASKPASS": str(askpass),
            "GIT_TERMINAL_PROMPT": "0",
            "LIFECYCLE_GITHUB_ACTOR": actor,
            "LIFECYCLE_GITHUB_TOKEN": credential_env["GH_TOKEN"],
        }


def exact_remote_head(
    target: lifecycle.Repo, repository: str, branch: str,
    *, env: dict[str, str] | None = None,
) -> str | None:
    proc = run_command(
        ["git", "ls-remote", "--heads", repository, f"refs/heads/{branch}"],
        target.root, check=False, env=env,
    )
    if proc.returncode:
        raise AdapterError("remote branch inspection failed", "remote_inspection_failed")
    rows = [line.split() for line in proc.stdout.splitlines() if line.strip()]
    if not rows:
        return None
    if len(rows) != 1 or len(rows[0]) != 2 or rows[0][1] != f"refs/heads/{branch}" or not OID_RE.fullmatch(rows[0][0]):
        raise AdapterError("remote branch inspection is ambiguous", "remote_inspection_failed")
    return rows[0][0]


def repository_identity(
    target: lifecycle.Repo, expected_repository: str, env: dict[str, str],
) -> tuple[str, str]:
    repo_proc = run_command(
        ["gh", "repo", "view", "--repo", expected_repository, "--json", "nameWithOwner"],
        target.root,
        check=False,
        env=env,
    )
    actor_proc = run_command(
        ["gh", "api", "--hostname", "github.com", "/user", "--jq", ".login"],
        target.root,
        check=False,
        env=env,
    )
    try:
        value = json.loads(repo_proc.stdout)
        name = value["nameWithOwner"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise AdapterError("GitHub repository inspection returned malformed data", "repo_data_malformed") from exc
    actor = actor_proc.stdout.strip()
    if (
        repo_proc.returncode
        or actor_proc.returncode
        or not isinstance(name, str)
        or name.count("/") != 1
        or not ACTOR_RE.fullmatch(actor)
    ):
        raise AdapterError("GitHub repository or actor identity is unavailable", "repo_inspection_failed")
    return name, actor


def action_push(repo: lifecycle.Repo, state: dict[str, Any], decision: dict[str, Any]) -> None:
    target, branch = action_target(repo, state), state["intended_branch"]
    lifecycle.validate_branch(target, branch, intended=True)
    head = decision_head(decision)
    if head is None or lifecycle.exact_head(target) != head or decision["evidence"]["git"]["branch"] != branch:
        raise AdapterError("refusing to push stale action evidence", "stale_push_evidence")
    contract = load_contract(repo, state["run_id"])
    repository = contract["github_repository"]
    actor = contract["expected_actor"]
    pinned_url = contract["origin"]["fetch"][0]
    credential_env = pinned_github_environment(target, contract)
    current_repository, current_actor = repository_identity(target, repository, credential_env)
    if current_repository.casefold() != repository.casefold() or current_actor != actor:
        raise AdapterError("GitHub repository or actor drifted after run start", "github_identity_drift")
    with github_askpass_environment(credential_env, actor) as git_env:
        run_command(
            ["git", "push", pinned_url, f"{head}:refs/heads/{branch}"],
            target.root,
            env=git_env,
        )
        if exact_remote_head(target, pinned_url, branch, env=git_env) != head:
            raise AdapterError("pushed remote SHA does not match inspected SHA", "remote_sha_mismatch")
    tracking_ref = f"refs/remotes/origin/{branch}"
    prior = lifecycle.git(target.root, "rev-parse", "--verify", tracking_ref, check=False)
    prior_oid = prior.stdout.strip() if prior.returncode == 0 else "0" * len(head)
    update_args = [
        "git", "update-ref", "-m", "lifecycle verified push",
        tracking_ref, head, prior_oid,
    ]
    run_command(update_args, target.root)
    run_command(
        ["git", "branch", "--set-upstream-to", f"origin/{branch}", branch],
        target.root,
        env={"GIT_TERMINAL_PROMPT": "0"},
    )


def pr_owner(value: dict[str, Any]) -> str | None:
    owner = value.get("headRepositoryOwner")
    return owner.get("login") if isinstance(owner, dict) else owner if isinstance(owner, str) else None


def pr_author(value: dict[str, Any]) -> str | None:
    author = value.get("author")
    return author.get("login") if isinstance(author, dict) else author if isinstance(author, str) else None


def parse_prs(
    proc: subprocess.CompletedProcess[str], state: dict[str, Any], head: str,
    repository: str, owner: str, actor: str,
) -> list[dict[str, Any]]:
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
             and pr_owner(value) == owner and pr_author(value) == actor]
    if len(exact) != len(candidates):
        raise AdapterError("pull request owner, author, or base is not pinned", "pr_identity_mismatch")
    if len(exact) > 1:
        raise AdapterError("multiple exact-head pull requests are ambiguous", "pr_ambiguous")
    return [{**value, "repository": repository} for value in exact]


def query_exact_pr(
    target: lifecycle.Repo, state: dict[str, Any], head: str,
    contract: dict[str, Any] | None = None,
    credential_env: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    contract = contract or load_contract(lifecycle.discover_repo(state["repository"]["start_worktree"]), state["run_id"])
    expected_repo, expected_actor = contract.get("github_repository"), contract.get("expected_actor")
    if not isinstance(expected_repo, str) or not isinstance(expected_actor, str):
        raise AdapterError("run lacks pinned GitHub repository or actor", "github_identity_unpinned")
    env = credential_env or pinned_github_environment(target, contract)
    repository, actor = repository_identity(target, expected_repo, env)
    if repository.casefold() != expected_repo.casefold() or actor != expected_actor:
        raise AdapterError("GitHub repository or actor drifted after run start", "github_identity_drift")
    owner = expected_repo.split("/", 1)[0]
    proc = run_command([
        "gh", "pr", "list", "--repo", expected_repo, "--head", state["intended_branch"],
        "--state", "all", "--limit", "100", "--json",
        "number,state,isDraft,headRefOid,headRefName,baseRefName,headRepositoryOwner,author,url,mergeable,mergeStateStatus",
    ], target.root, check=False, env=env)
    exact = parse_prs(proc, state, head, expected_repo, owner, expected_actor)
    return exact[0] if exact else None

def pr_status(value: dict[str, Any]) -> str:
    state = value.get("state")
    if state == "OPEN":
        draft = value.get("isDraft")
        if not isinstance(draft, bool):
            raise AdapterError("pull request draft state is unknown", "pr_data_malformed")
        return "draft" if draft else "open"
    if state in {"MERGED", "CLOSED"}:
        return state.lower()
    raise AdapterError("pull request state is unknown", "pr_data_malformed")
def pr_snapshot(value: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(value.get(key) for key in (
        "repository", "number", "state", "isDraft", "headRefOid", "headRefName", "baseRefName",
        "mergeable", "mergeStateStatus",
    )) + (pr_owner(value), pr_author(value))
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
def create_pr_diagnostic(proc: subprocess.CompletedProcess[str]) -> str:
    for raw in reversed((proc.stderr or "").splitlines()):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(value, dict) or set(value) != {"lifecycle_pr_error"}:
            continue
        detail = value["lifecycle_pr_error"]
        if not isinstance(detail, dict) or set(detail) != {"exit_status", "reason"}:
            continue
        reason = detail.get("reason")
        status = detail.get("exit_status")
        unsafe_token = (
            isinstance(reason, str)
            and (
                re.search(r"(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)", reason) is not None
                or any(
                    secret and secret in reason
                    for secret in (
                        os.environ.get("GH_TOKEN", ""),
                        os.environ.get("GITHUB_TOKEN", ""),
                    )
                )
            )
        )
        if (
            isinstance(status, int)
            and 0 < status < 256
            and isinstance(reason, str)
            and 0 < len(reason) <= 300
            and not unsafe_token
        ):
            return reason
    return "canonical PR creation failed without a valid diagnostic"


def action_open_pr(repo: lifecycle.Repo, state: dict[str, Any], decision: dict[str, Any]) -> None:
    target, head = action_target(repo, state), decision_head(decision)
    if head is None or lifecycle.exact_head(target) != head:
        raise AdapterError("controller did not provide a fresh exact HEAD", "missing_head")
    contract = load_contract(repo, state["run_id"])
    repository = contract["github_repository"]
    actor = contract["expected_actor"]
    pinned_url = contract["origin"]["fetch"][0]
    credential_env = pinned_github_environment(target, contract)
    with github_askpass_environment(credential_env, actor) as git_env:
        if exact_remote_head(target, pinned_url, state["intended_branch"], env=git_env) != head:
            raise AdapterError("remote branch does not match approved HEAD", "remote_sha_mismatch")
        pull_request = query_exact_pr(target, state, head, contract, credential_env)
        if pull_request is None:
            ready = lifecycle.current_unit(state).get("ready")
            if not isinstance(ready, dict) or not isinstance(ready.get("subject"), str):
                raise AdapterError("conventional PR title evidence is missing", "ready_evidence_missing")
            create_env = {
                **credential_env,
                "LIFECYCLE_EXPECTED_ACTOR": actor,
                "LIFECYCLE_EXPECTED_REPOSITORY": repository,
                "LIFECYCLE_EXPECTED_SHA": head,
                "LIFECYCLE_EXPECTED_URL": pinned_url,
                "LIFECYCLE_EXPECTED_PUSH_URL": contract["origin"]["push"][0],
            }
            proc = run_command([
                STACK, "pr", state["intended_branch"], state["base"]["branch"],
                ready["subject"], "--no-push",
            ], target.root, check=False, env=create_env)
            if proc.returncode:
                raise AdapterError(
                    f"canonical PR creation failed: {create_pr_diagnostic(proc)}",
                    "pr_creation_failed",
                )
            if exact_remote_head(target, pinned_url, state["intended_branch"], env=git_env) != head:
                raise AdapterError("canonical PR creation changed remote SHA", "remote_sha_mismatch")
            pull_request = query_exact_pr(target, state, head, contract, credential_env)
    if pull_request is None or pr_status(pull_request) != "open" or pr_author(pull_request) != actor:
        raise AdapterError("canonical PR creation produced no actor-owned open exact PR", "pr_exact_head_missing")
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
def action_journal_path(common_dir: Path, run_id: str) -> Path:
    lifecycle.validate_name(run_id, lifecycle.RUN_ID_RE, "run id")
    return adapter_root(common_dir) / "action-journals" / f"{hashlib.sha256(run_id.encode()).hexdigest()}.json"


def write_action_journal(repo: lifecycle.Repo, value: dict[str, Any]) -> None:
    lifecycle.atomic_json(action_journal_path(repo.common_dir, value["run_id"]), value)


def load_action_journal(repo: lifecycle.Repo, run_id: str) -> dict[str, Any] | None:
    path = action_journal_path(repo.common_dir, run_id)
    if not path.exists():
        return None
    value = read_json(path, "invalid_action_journal")
    required = {
        "schema_version": int, "run_id": str, "action": str, "stage": str,
        "head_sha": (str, type(None)), "status": str, "result": (str, type(None)),
        "reason_code": (str, type(None)), "audit_status": str,
        "created_at": str, "updated_at": str,
    }
    if (
        any(not isinstance(value.get(key), kind) for key, kind in required.items())
        or value.get("schema_version") != ADAPTER_SCHEMA_VERSION
        or value.get("run_id") != run_id
        or value.get("action") not in ACTION_STAGES
        or value.get("stage") != ACTION_STAGES.get(value.get("action"))
        or value.get("status") not in {"pending", "completed"}
        or value.get("result") not in {None, "success", "failure"}
        or value.get("audit_status") not in {"pending", "complete"}
        or (value.get("status") == "pending" and value.get("result") is not None)
        or (value.get("status") == "completed" and value.get("result") is None)
    ):
        raise AdapterError("action reconciliation journal is malformed", "invalid_action_journal")
    return value


def begin_action_journal(
    repo: lifecycle.Repo, run_id: str, decision: dict[str, Any], stage: str,
) -> dict[str, Any]:
    current = load_action_journal(repo, run_id)
    if current is not None and current["audit_status"] != "complete":
        raise AdapterError("prior action audit reconciliation is pending", "action_audit_pending")
    timestamp = now()
    value = {
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "run_id": run_id,
        "action": decision["action"],
        "stage": stage,
        "head_sha": decision_head(decision),
        "status": "pending",
        "result": None,
        "reason_code": None,
        "audit_status": "pending",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    write_action_journal(repo, value)
    return value


def complete_action_journal(
    repo: lifecycle.Repo, journal: dict[str, Any], result: str,
    reason_code: str | None = None,
) -> dict[str, Any]:
    value = {
        **journal,
        "status": "completed",
        "result": result,
        "reason_code": reason_code,
        "audit_status": "pending",
        "updated_at": now(),
    }
    write_action_journal(repo, value)
    return value


def audit_action_journal(repo: lifecycle.Repo, journal: dict[str, Any]) -> dict[str, Any]:
    try:
        append_adapter_audit(
            repo.common_dir,
            journal["run_id"],
            "action",
            journal["result"],
            action=journal["action"],
            stage=journal["stage"],
            reason_code=journal["reason_code"],
            head_sha=journal["head_sha"],
        )
    except Exception as exc:
        raise AdapterError(
            "action completed but durable audit reconciliation is pending",
            "action_audit_pending",
        ) from exc
    value = {**journal, "audit_status": "complete", "updated_at": now()}
    write_action_journal(repo, value)
    return value


def reconcile_action_journal(repo: lifecycle.Repo, run_id: str) -> bool:
    journal = load_action_journal(repo, run_id)
    if journal is None or journal["audit_status"] == "complete":
        return False
    if journal["status"] == "pending":
        current = inspect_bound(repo, run_id)
        succeeded = current.get("action") in ACTION_SUCCESSORS[journal["action"]]
        if succeeded:
            journal = complete_action_journal(repo, journal, "success")
        else:
            demote_stage(repo.common_dir, journal["stage"], run_id)
            journal = complete_action_journal(
                repo, journal, "failure", "action_interrupted",
            )
    audit_action_journal(repo, journal)
    return True
def execute_action(repo: lifecycle.Repo, run_id: str, decision: dict[str, Any], state: dict[str, Any],
    action_fn: Callable[[lifecycle.Repo, dict[str, Any], dict[str, Any]], None]) -> dict[str, Any]:
    stage = ACTION_STAGES[decision["action"]]
    try:
        target = action_target(repo, state)
        verify_contract(repo, state, target)
    except Exception as exc:
        code = exc.code if isinstance(exc, (AdapterError, lifecycle.LifecycleError)) else "action_preflight_failed"
        best_effort_audit(
            repo.common_dir, run_id, "action", "refused", action=decision["action"],
            stage=stage, reason_code=code, head_sha=decision_head(decision),
        )
        return adapter_result(run_id, "blocked", decision, ok=False, reason_code=code)
    authorized, code = resolve_autonomy(repo, state, stage)
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
    try:
        target = action_target(repo, state)
        verify_contract(repo, state, target)
    except Exception as exc:
        code = exc.code if isinstance(exc, (AdapterError, lifecycle.LifecycleError)) else "action_preflight_failed"
        best_effort_audit(
            repo.common_dir, run_id, "action", "refused", action=decision["action"],
            stage=stage, reason_code=code, head_sha=decision_head(decision),
        )
        return adapter_result(run_id, "blocked", decision, ok=False, reason_code=code)
    journal = begin_action_journal(repo, run_id, decision, stage)
    action_audit(repo, run_id, decision, "attempt", stage=stage)
    try:
        action_fn(repo, state, decision)
    except Exception as exc:
        code = exc.code if isinstance(exc, (AdapterError, lifecycle.LifecycleError)) else "action_failed"
        demote_stage(repo.common_dir, stage, run_id)
        journal = complete_action_journal(repo, journal, "failure", code)
        try:
            audit_action_journal(repo, journal)
        except AdapterError:
            pass
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
    journal = complete_action_journal(repo, journal, "success")
    audit_action_journal(repo, journal)
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
def marker_age(value: dict[str, Any]) -> float:
    raw = value.get("updated_at")
    if not isinstance(raw, str):
        raise AdapterError("watcher marker timestamp is missing", "watcher_state_invalid")
    try:
        observed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AdapterError("watcher marker timestamp is malformed", "watcher_state_invalid") from exc
    if observed.tzinfo is None:
        raise AdapterError("watcher marker timestamp lacks timezone", "watcher_state_invalid")
    return (dt.datetime.now(dt.timezone.utc) - observed).total_seconds()
def valid_watcher_marker(path: Path, run_id: str, sha: str) -> dict[str, Any]:
    value = read_json(path, "watcher_state_invalid")
    if (
        value.get("schema_version") != ADAPTER_SCHEMA_VERSION
        or value.get("run_id") != run_id
        or value.get("sha") != sha
        or value.get("status") not in {"starting", "running"}
        or not isinstance(value.get("pid"), int)
        or value["pid"] <= 1
        or marker_age(value) < -5
        or marker_age(value) > WATCHER_STALE_SECONDS
    ):
        raise AdapterError("watcher marker is malformed or stale", "watcher_state_invalid")
    return value
def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
def watcher_active(repo: lifecycle.Repo, run_id: str, sha: str) -> bool:
    marker, _, execution_lock, ready = watcher_paths(repo.common_dir, run_id, sha)
    try:
        value = valid_watcher_marker(marker, run_id, sha)
        ready_value = read_json(ready, "watcher_state_invalid")
    except AdapterError:
        return False
    if (
        value["status"] != "running"
        or ready_value.get("schema_version") != ADAPTER_SCHEMA_VERSION
        or ready_value.get("run_id") != run_id
        or ready_value.get("sha") != sha
        or ready_value.get("status") != "ready"
        or ready_value.get("pid") != value["pid"]
        or not process_alive(value["pid"])
    ):
        return False
    fd = secure_file(execution_lock, os.O_RDWR)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)
def child_ready(path: Path, proc: subprocess.Popen[Any], run_id: str, sha: str) -> bool:
    deadline = time.monotonic() + WATCHER_READY_TIMEOUT
    while time.monotonic() < deadline:
        if path.exists():
            try:
                value = read_json(path, "watcher_state_invalid")
                if (
                    value.get("schema_version") == ADAPTER_SCHEMA_VERSION
                    and value.get("run_id") == run_id
                    and value.get("sha") == sha
                    and value.get("status") == "ready"
                    and value.get("pid") == proc.pid
                ):
                    return True
            except AdapterError:
                return False
        if proc.poll() is not None:
            proc.wait()
            return False
        time.sleep(0.02)
    return False
def stop_unready_child(proc: subprocess.Popen[Any]) -> None:
    try:
        terminate_process_group(proc)
    except (OSError, subprocess.SubprocessError):
        try:
            proc.wait(timeout=PROCESS_TERM_GRACE)
        except Exception:
            pass
def spawn_watcher(repo: lifecycle.Repo, run_id: str, sha: str) -> dict[str, Any]:
    marker, spawn_lock, _, ready = watcher_paths(repo.common_dir, run_id, sha)
    fd = secure_file(spawn_lock, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        if marker.exists() and watcher_active(repo, run_id, sha):
            return {"started": False, "duplicate": True, "sha": sha, "lease": "active"}
        ready.unlink(missing_ok=True)
        write_watcher_marker(marker, run_id, sha, "starting", None)
        try:
            proc = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "watch",
                 "--run-id", run_id, "--sha", sha], cwd=str(repo.root),
                env=process_environment(), stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True, close_fds=True,
            )
        except OSError as exc:
            write_watcher_marker(marker, run_id, sha, "failed", None)
            raise AdapterError("unable to start detached CI watcher", "watcher_spawn_failed") from exc
        write_watcher_marker(marker, run_id, sha, "starting", proc.pid)
        if not child_ready(ready, proc, run_id, sha):
            stop_unready_child(proc)
            write_watcher_marker(marker, run_id, sha, "failed", proc.pid)
            raise AdapterError("detached CI watcher did not become ready", "watcher_not_ready")
        if not watcher_active(repo, run_id, sha):
            stop_unready_child(proc)
            write_watcher_marker(marker, run_id, sha, "failed", proc.pid)
            raise AdapterError("detached CI watcher lease is not active", "watcher_not_ready")
        return {"started": True, "duplicate": False, "sha": sha, "lease": "active"}
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
def tick_locked(repo: lifecycle.Repo, run_id: str) -> dict[str, Any]:
    if reconcile_action_journal(repo, run_id):
        decision = inspect_bound(repo, run_id)
        return adapter_result(run_id, "reconciled", decision)
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
        repo, current, state = bound_state(cwd, session_id, args.run_id)
        if current["run_id"] != run_id:
            raise AdapterError("Claude session binding changed during tick", "run_binding_mismatch")
        validate_owned_paths(state["owned_paths"], action_target(repo, state).root)
        verify_contract(repo, state, action_target(repo, state))
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
def required_checks(
    target: lifecycle.Repo, number: int, contract: dict[str, Any],
    credential_env: dict[str, str] | None = None,
) -> tuple[str, dict[str, Any]]:
    repository = contract.get("github_repository")
    if not isinstance(repository, str):
        raise AdapterError("run lacks a pinned GitHub repository", "github_identity_unpinned")
    env = credential_env or pinned_github_environment(target, contract)
    proc = run_command([
        "gh", "pr", "checks", str(number), "--repo", repository,
        "--required", "--json", "name,state,bucket",
    ], target.root, check=False, env=env)
    try:
        checks = json.loads(proc.stdout)
    except json.JSONDecodeError:
        checks = None
    classified, metadata = classify_required_checks(checks)
    if proc.returncode == 0:
        status_value = classified
    elif proc.returncode == 1 and classified == "failed":
        status_value = "failed"
    elif proc.returncode == 8 and classified == "pending":
        status_value = "pending"
    else:
        status_value = "unknown"
        metadata["command_status"] = f"inconsistent_exit_{proc.returncode}"
    metadata["pr_number"] = number
    return status_value, metadata

def merge_readiness_complete(value: dict[str, Any], state: dict[str, Any], sha: str) -> bool:
    required = {
        "number": int, "state": str, "isDraft": bool, "headRefOid": str,
        "headRefName": str, "baseRefName": str, "repository": str,
        "mergeable": str, "mergeStateStatus": str,
    }
    if any(not isinstance(value.get(key), kind) for key, kind in required.items()):
        return False
    return (
        value["number"] > 0
        and value["state"] == "OPEN"
        and value["isDraft"] is False
        and value["headRefOid"] == sha
        and value["headRefName"] == state["intended_branch"]
        and value["baseRefName"] == state["base"]["branch"]
        and value["mergeable"] == "MERGEABLE"
        and value["mergeStateStatus"] == "CLEAN"
        and isinstance(pr_owner(value), str)
    )
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
    try:
        contract = verify_contract(repo, state, target)
    except Exception as exc:
        code = exc.code if isinstance(exc, (AdapterError, lifecycle.LifecycleError)) else "action_preflight_failed"
        metadata = {"required_count": 0, "check_names": [], "reason_code": code}
        record_ci(repo, run_id, expected_sha, "unknown", metadata)
        return {"ok": False, "outcome": "pending", "status": "unknown", "sha": expected_sha, "degraded": True}
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
            check_status, metadata = required_checks(target, number, contract)
        if check_status == "passing":
            if not merge_readiness_complete(pull_request, state, expected_sha):
                check_status, metadata = "unknown", {
                    "required_count": metadata.get("required_count", 0),
                    "check_names": metadata.get("check_names", []),
                    "reason_code": "merge_readiness_incomplete",
                }
            else:
                confirmed, confirm_error = observe_pr(target, state, expected_sha)
                if confirmed is not None:
                    record_pr(repo, run_id, expected_sha, confirmed)
                stable = (
                    confirmed is not None
                    and merge_readiness_complete(confirmed, state, expected_sha)
                    and pr_snapshot(confirmed) == pr_snapshot(pull_request)
                )
                if confirm_error or not stable:
                    check_status, metadata = "unknown", {
                        "required_count": metadata.get("required_count", 0),
                        "check_names": metadata.get("check_names", []),
                        "reason_code": confirm_error or "pr_changed",
                    }
    record_ci(repo, run_id, expected_sha, check_status, metadata)
    return {
        "ok": True, "outcome": "terminal" if check_status in {"passing", "failed"} else "pending",
        "status": check_status, "sha": expected_sha, "decision": inspect_bound(repo, run_id),
        "degraded": bool(query_error or metadata.get("command_status") or metadata.get("reason_code")),
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
        lifecycle.atomic_json(ready, {
            "schema_version": ADAPTER_SCHEMA_VERSION, "run_id": args.run_id,
            "sha": args.sha, "status": "ready", "pid": os.getpid(),
        })
        failures = 0
        for poll in range(1, args.max_polls + 1):
            update_watcher_marker(repo, args.run_id, args.sha, "running")
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
def hook_envelope(
    event: str, binding: str, *, run_id: str | None = None,
    native: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "schema_version": HOOK_ENVELOPE_VERSION,
        "processed": True,
        "event": event,
        "binding": binding,
    }
    if run_id is not None:
        metadata["run_id"] = run_id
    return {"lifecycle_hook": metadata, **(native or {})}
def deny(reason: str, *, binding: str = "bound", run_id: str | None = None) -> dict[str, Any]:
    return hook_envelope("PreToolUse", binding, run_id=run_id, native={
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"{HARD_BLOCK} {reason}",
        }
    })
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
    repo: lifecycle.Repo, run_id: str, result: str, reason_code: str,
    decision: dict[str, Any] | None = None,
) -> None:
    append_adapter_audit(
        repo.common_dir, run_id, "hook", result,
        action=decision.get("action") if decision else None,
        reason_code=reason_code,
        head_sha=decision_head(decision) if decision else None,
    )
def validate_hook_payload(event: str, payload: dict[str, Any]) -> str:
    session = payload.get("session_id")
    cwd = payload.get("cwd")
    session_id = effective_session(session if isinstance(session, str) else None)
    if not isinstance(cwd, str) or not cwd or not Path(cwd).is_absolute() or "\x00" in cwd:
        raise AdapterError("hook cwd is malformed", "invalid_hook_payload")
    if event == "PreToolUse":
        if not isinstance(payload.get("tool_name"), str) or not isinstance(payload.get("tool_input"), dict):
            raise AdapterError("PreToolUse payload is malformed", "invalid_hook_payload")
    elif event == "UserPromptSubmit":
        if not isinstance(payload.get("prompt"), str):
            raise AdapterError("UserPromptSubmit payload is malformed", "invalid_hook_payload")
    elif event == "SessionStart":
        source = payload.get("source")
        if source is not None and not isinstance(source, str):
            raise AdapterError("SessionStart payload is malformed", "invalid_hook_payload")
    elif event == "Stop":
        active = payload.get("stop_hook_active")
        if active is not None and not isinstance(active, bool):
            raise AdapterError("Stop payload is malformed", "invalid_hook_payload")
    return session_id
def command_tokens(command: Any) -> list[str] | None:
    if not isinstance(command, str) or not command or command != command.strip():
        return None
    if any(character in command for character in "\n\r;&|<>`$#*?[]{}~\\()!"):
        return None
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return None
    return tokens if tokens and all("\x00" not in token for token in tokens) else None
def tracked_adapter_path() -> Path:
    path = Path(__file__).resolve()
    try:
        relative = path.relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise AdapterError("adapter is outside the tracked dotfiles root", "adapter_untrusted") from exc
    proc = lifecycle.git(ROOT, "ls-files", "--error-unmatch", "--", relative, check=False)
    if proc.returncode or relative != "scripts/ai/lifecycle_adapter.py" or path.is_symlink() or not path.is_file():
        raise AdapterError("adapter is not the exact tracked lifecycle entrypoint", "adapter_untrusted")
    return path
def trusted_tool(token: str, names: set[str]) -> str | None:
    if token in names:
        exported = f"BASH_FUNC_{token}%%"
        return None if exported in os.environ else token
    candidate = Path(token)
    if not candidate.is_absolute():
        return None
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    for name in names:
        installed = shutil.which(name)
        if installed and resolved == Path(installed).resolve(strict=True):
            return name
    return None


def adapter_invocation(tokens: list[str], session_id: str) -> str | None:
    expected = tracked_adapter_path()
    if Path(tokens[0]).resolve(strict=False) == expected:
        args = tokens[1:]
    elif trusted_tool(tokens[0], {"python", "python3"}) is not None and len(tokens) > 1 and Path(tokens[1]).resolve(strict=False) == expected:
        args = tokens[2:]
    else:
        return None
    if not args or args[0] not in {"start", "ready", "next-unit", "status", "tick", "recover-edit", "release", "takeover"}:
        return None
    positions = [index for index, token in enumerate(args) if token == "--session-id"]
    if len(positions) != 1 or positions[0] + 1 >= len(args) or args[positions[0] + 1] != session_id:
        return None
    if any(token.startswith("--session-id=") for token in args):
        return None
    return args[0]
def read_only_command(tokens: list[str]) -> bool:
    executable = trusted_tool(tokens[0], {"git", "gh"})
    if executable == "git" and len(tokens) >= 2 and tokens[1] in READ_ONLY_GIT:
        forbidden = {"--exec-path", "--ext-diff", "--no-index", "--output", "--paginate", "--textconv"}
        return not any(
            token in forbidden
            or token.startswith(("--out", "--ext-diff=", "--textconv="))
            for token in tokens[2:]
        )
    if executable == "gh" and len(tokens) >= 3 and tokens[1] == "pr" and tokens[2] in READ_ONLY_GH_PR:
        return not any(token.startswith("--web") for token in tokens[3:])
    if executable == "gh" and len(tokens) >= 3 and tokens[1:3] == ["repo", "view"]:
        return not any(token.startswith("--web") for token in tokens[3:])
    return False
def trusted_validation(tokens: list[str], target: lifecycle.Repo) -> bool:
    executable = trusted_tool(tokens[0], {"bash", "sh", "shellcheck", "python", "python3"})
    if Path(tokens[0]).resolve(strict=False) == VALIDATE.resolve() and tokens[1:] == ["--json"]:
        return True
    if executable in {"bash", "sh"} and len(tokens) >= 3 and tokens[1] == "-n":
        return all(token.endswith((".sh", ".bash")) and not token.startswith("-") for token in tokens[2:])
    if executable == "shellcheck" and len(tokens) >= 2:
        return all(not token.startswith("-") or token in {"-x", "--external-sources"} for token in tokens[1:])
    if executable in {"python", "python3"} and len(tokens) == 4 and tokens[1:3] == ["-m", "json.tool"]:
        return True
    return False
def bash_gate(
    payload: dict[str, Any], repo: lifecycle.Repo, target: lifecycle.Repo,
    state: dict[str, Any], run_id: str, session_id: str, decision: dict[str, Any],
) -> dict[str, Any]:
    tool_input = payload.get("tool_input")
    tokens = command_tokens(tool_input.get("command") if isinstance(tool_input, dict) else None)
    if tokens is None:
        audit_hook(repo, run_id, "deny", "bash_shape_denied", decision)
        return deny("Bash is default-deny; shell operators, substitutions, redirects, and malformed commands are forbidden.", run_id=run_id)
    invocation = adapter_invocation(tokens, session_id)
    if invocation is not None:
        audit_hook(repo, run_id, "allow", "adapter_command", decision)
        return hook_envelope("PreToolUse", "bound", run_id=run_id)
    if read_only_command(tokens):
        audit_hook(repo, run_id, "allow", "read_only_command", decision)
        return hook_envelope("PreToolUse", "bound", run_id=run_id)
    if decision.get("action") in EDITING_ACTIONS and trusted_validation(tokens, target):
        audit_hook(repo, run_id, "allow", "trusted_validation", decision)
        return hook_envelope("PreToolUse", "bound", run_id=run_id)
    audit_hook(repo, run_id, "deny", "bash_default_deny", decision)
    return deny("Bash command is outside the lifecycle read/validation allowlist; use the exact lifecycle adapter command.", run_id=run_id)
def owned_path_gate(
    payload: dict[str, Any], repo: lifecycle.Repo, target: lifecycle.Repo,
    state: dict[str, Any], run_id: str, decision: dict[str, Any],
) -> dict[str, Any]:
    try:
        validate_owned_paths(state["owned_paths"], target.root)
        verify_contract(repo, state, target)
    except Exception as exc:
        code = exc.code if isinstance(exc, (AdapterError, lifecycle.LifecycleError)) else "write_preflight_failed"
        best_effort_audit(repo.common_dir, run_id, "hook", "deny", action=decision.get("action"), reason_code=code, head_sha=decision_head(decision))
        return deny("Lifecycle ownership or immutable policy validation failed.", run_id=run_id)
    raw_paths = hook_paths(payload)
    if not raw_paths:
        audit_hook(repo, run_id, "deny", "write_path_missing", decision)
        return deny("Write tool input does not identify a path inside the run-owned boundary.", run_id=run_id)
    for raw in raw_paths:
        candidate = Path(raw).expanduser()
        candidate = candidate if candidate.is_absolute() else target.root / candidate
        try:
            relative = candidate.resolve(strict=False).relative_to(target.root.resolve()).as_posix()
        except ValueError:
            audit_hook(repo, run_id, "deny", "path_outside_worktree", decision)
            return deny("Write path is outside the lifecycle run worktree.", run_id=run_id)
        if path_overlaps_control_plane(relative):
            audit_hook(repo, run_id, "deny", "control_plane_write", decision)
            return deny("Lifecycle control-plane files are human-owned and may not be written by this run.", run_id=run_id)
        if not lifecycle.owns(relative, state["owned_paths"]):
            audit_hook(repo, run_id, "deny", "path_not_owned", decision)
            return deny("Write path is outside the lifecycle run-owned boundary.", run_id=run_id)
    audit_hook(repo, run_id, "allow", "editing_state_valid", decision)
    return hook_envelope("PreToolUse", "bound", run_id=run_id)
def bootstrap_bash(payload: dict[str, Any], session_id: str) -> dict[str, Any] | None:
    tool_input = payload.get("tool_input")
    tokens = command_tokens(tool_input.get("command") if isinstance(tool_input, dict) else None)
    if tokens is not None and adapter_invocation(tokens, session_id) == "start":
        return hook_envelope("PreToolUse", "unbound")
    return None
def hook_pre_write(payload: dict[str, Any], repo: lifecycle.Repo, session_id: str) -> dict[str, Any]:
    tool_name = payload.get("tool_name")
    try:
        binding = load_binding(repo, session_id)
    except AdapterError as exc:
        if exc.code == "run_unbound" and tool_name == "Bash":
            bootstrap = bootstrap_bash(payload, session_id)
            if bootstrap is not None:
                return bootstrap
        return deny("Lifecycle run is not bound to this Claude session; invoke the exact lifecycle_adapter.py start command first.", binding="unbound")
    run_id = binding["run_id"]
    try:
        decision = inspect_bound(repo, run_id)
        state = load_run_state(repo, run_id)
        target = action_target(repo, state)
        validate_owned_paths(state["owned_paths"], target.root)
        verify_contract(repo, state, target)
    except Exception:
        best_effort_audit(repo.common_dir, run_id, "hook", "deny", reason_code="invalid_binding")
        return deny("Bound lifecycle state or immutable run contract is invalid.", run_id=run_id)
    if tool_name == "mcp__pctx__execute_typescript":
        audit_hook(repo, run_id, "deny", "pctx_execution_denied", decision)
        return deny("Mutation-capable pctx TypeScript execution is disabled while lifecycle control is enabled.", run_id=run_id)
    if tool_name in {"EnterWorktree", "ExitWorktree"}:
        audit_hook(repo, run_id, "deny", "worktree_tool_denied", decision)
        return deny("Worktree entry and exit are disabled while lifecycle control owns the run.", run_id=run_id)
    if tool_name == "Bash":
        return bash_gate(payload, repo, target, state, run_id, session_id, decision)
    if tool_name not in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
        audit_hook(repo, run_id, "deny", "unknown_mutation_tool", decision)
        return deny("Lifecycle PreToolUse received an unsupported mutation-capable tool.", run_id=run_id)
    if decision["action"] not in EDITING_ACTIONS:
        audit_hook(repo, run_id, "deny", "invalid_editing_state", decision)
        return deny(
            f"Lifecycle state is {decision['action']}; refresh readiness or start the next work unit before writing.",
            run_id=run_id,
        )
    return owned_path_gate(payload, repo, target, state, run_id, decision)
def status_instruction(value: dict[str, Any], session_id: str) -> str:
    quoted = shlex.quote(session_id)
    adapter_command = shlex.quote(str(Path(__file__).resolve()))
    if not value.get("bound"):
        return f"Lifecycle enabled: bind a run with {adapter_command} start --session-id {quoted} before editing tracked work."
    action = value.get("action", "blocked")
    reason = value.get("reason", "fresh lifecycle inspection required")
    instructions = {
        "create_stack": f"Run {adapter_command} tick --session-id {quoted} to create the exact-base stack.",
        "editing": f"Continue only within owned paths; call {adapter_command} ready with --session-id {quoted} when complete.",
        "awaiting_work": "Begin the current work unit only within owned paths.",
        "commit": f"Run {adapter_command} tick --session-id {quoted}; direct writes are blocked.",
        "push": f"Run {adapter_command} tick --session-id {quoted} to push the exact committed HEAD.",
        "open_pr": f"Run {adapter_command} tick --session-id {quoted} to create the exact-head PR.",
        "wait_ci": "CI is observed asynchronously; do not poll in the hook.",
        "merge_eligible": "Merge is deferred and remains blocked in this adapter.",
        "sync": "Sync is deferred and remains blocked in this adapter.",
        "cleanup": "Cleanup is deferred and remains blocked in this adapter.",
        "blocked": "Resolve the reported lifecycle invariant before continuing.",
        "done": "Lifecycle run is complete.",
    }
    return f"Lifecycle {action}: {reason}. {instructions.get(action, 'Inspect the lifecycle run before continuing.')}"
def hook_context(event: str, repo: lifecycle.Repo, session_id: str) -> dict[str, Any]:
    probe = argparse.Namespace(session_id=session_id, run_id=None)
    value = status(probe, repo.root)
    binding = "bound" if value.get("bound") else "unbound"
    run_id = value.get("run_id") if binding == "bound" else None
    if run_id:
        audit_hook(repo, run_id, "inject", "status_context", value)
    return hook_envelope(event, binding, run_id=run_id, native={
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": status_instruction(value, session_id),
        }
    })
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
        return "Lifecycle CI watcher readiness or lease is not proven."
    return f"Lifecycle is not complete ({action}): {reason}"
def hook_stop(repo: lifecycle.Repo, session_id: str) -> dict[str, Any]:
    try:
        binding = load_binding(repo, session_id)
    except AdapterError as exc:
        if exc.code == "run_unbound":
            return hook_envelope("Stop", "unbound")
        raise
    run_id = binding["run_id"]
    args = argparse.Namespace(session_id=session_id, run_id=run_id)
    try:
        value = tick(args, repo.root)
    except Exception as exc:
        code = exc.code if isinstance(exc, (AdapterError, lifecycle.LifecycleError)) else "tick_failed"
        best_effort_audit(repo.common_dir, run_id, "hook", "block", reason_code=code)
        return hook_envelope("Stop", "bound", run_id=run_id, native={
            "decision": "block", "reason": f"Lifecycle tick failed closed: {code}",
        })
    after, outcome = value.get("after", {}), value.get("outcome")
    action = after.get("action", "blocked")
    if outcome == "done" or action == "done":
        audit_hook(repo, run_id, "allow", "terminal_done", after)
        return hook_envelope("Stop", "bound", run_id=run_id)
    if outcome == "watching":
        head = decision_head(after)
        if head and watcher_active(repo, run_id, head):
            audit_hook(repo, run_id, "allow", "watcher_lease_active", after)
            return hook_envelope("Stop", "bound", run_id=run_id)
    audit_hook(repo, run_id, "block", value.get("reason_code", "lifecycle_incomplete"), after)
    return hook_envelope("Stop", "bound", run_id=run_id, native={
        "decision": "block", "reason": stop_reason(value),
    })
def hook_failure(event: str) -> dict[str, Any]:
    if event == "PreToolUse":
        return deny("Lifecycle pre-write inspection failed closed.")
    if event == "Stop":
        return hook_envelope("Stop", "bound", native={
            "decision": "block", "reason": "Lifecycle Stop inspection failed closed.",
        })
    return hook_envelope(event, "bound", native={
        "hookSpecificOutput": {"hookEventName": event, "additionalContext":
            "Lifecycle inspection failed closed; repair lifecycle state before mutation."}
    })
def dispatch_hook_event(event: str, payload: dict[str, Any], repo: lifecycle.Repo,
                        session_id: str) -> dict[str, Any]:
    if event == "PreToolUse":
        return hook_pre_write(payload, repo, session_id)
    if event in {"SessionStart", "UserPromptSubmit"}:
        return hook_context(event, repo, session_id)
    return hook_stop(repo, session_id)
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
    try:
        session_id = validate_hook_payload(args.event, payload)
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
    command.add_argument("--session-id", required=True)
    command.add_argument("--run-id")
def mutation_args(command: argparse.ArgumentParser) -> None:
    session_args(command)
    command.add_argument("--idempotency-key")
    command.add_argument("--lock-timeout", type=timeout_value, default=10)
def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Claude adapter for deterministic git lifecycle control")
    commands = root.add_subparsers(dest="command", required=True)
    start_parser = commands.add_parser("start")
    start_parser.add_argument("--session-id", required=True)
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
    recover_parser = commands.add_parser("recover-edit")
    mutation_args(recover_parser)
    recover_parser.add_argument("--reason", required=True)
    release_parser = commands.add_parser("release")
    mutation_args(release_parser)
    release_parser.add_argument("--reason", required=True)
    takeover_parser = commands.add_parser("takeover")
    mutation_args(takeover_parser)
    takeover_parser.add_argument("--from-session-id", required=True)
    takeover_parser.add_argument("--reason", required=True)
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
        "recover-edit": recover_edit,
        "release": release_session,
        "takeover": takeover_session,
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
