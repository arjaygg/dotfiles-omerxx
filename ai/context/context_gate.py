#!/usr/bin/env python3
"""Portable, standard-library-only large-file routing gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Sequence


Decision = Literal["allow", "warn", "deny"]
SizeClass = Literal["small", "medium", "large", "huge", "unknown"]
POLICY_PATH = Path(__file__).with_name("context-routing.json")


@dataclass(frozen=True)
class PathClassification:
    size_class: SizeClass
    size_bytes: int
    line_count: int
    generated: bool = False


@dataclass(frozen=True)
class GateRequest:
    client: str
    event: str
    tool: str
    command: str | None = None
    path: str | None = None
    mode: str | None = None
    limit: int | None = None
    command_class: str | None = None
    unparseable: bool = False
    returned_tokens: int | None = None
    expandable_reference: bool = False
    cache_hit: bool = False


@dataclass(frozen=True)
class GateResult:
    decision: Decision
    reason_code: str
    message: str
    size_class: SizeClass
    elapsed_ms: float


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _line_count(path: Path) -> int:
    count = 0
    last = b""
    with path.open("rb") as stream:
        while chunk := stream.read(64 * 1024):
            count += chunk.count(b"\n")
            last = chunk[-1:]
    return count + (1 if path.stat().st_size and last != b"\n" else 0)


def _is_generated(path: Path, policy: dict[str, Any]) -> bool:
    generated = policy["generated"]
    lower_name = path.name.lower()
    if lower_name in {name.lower() for name in generated["names"]}:
        return True
    if any(lower_name.endswith(suffix.lower()) for suffix in generated["suffixes"]):
        return True
    return bool(
        {part.lower() for part in path.parts}
        & {part.lower() for part in generated["path_parts"]}
    )


def classify_path(
    path: str | Path,
    policy: dict[str, Any] | None = None,
) -> PathClassification:
    policy = policy or load_policy()
    candidate = Path(path).expanduser()
    try:
        size_bytes = candidate.stat().st_size
        line_count = _line_count(candidate)
    except (OSError, ValueError):
        return PathClassification("unknown", 0, 0)

    generated = _is_generated(candidate, policy)
    thresholds = policy["thresholds"]
    if generated or size_bytes > thresholds["huge_over_bytes"]:
        size_class: SizeClass = "huge"
    elif (
        size_bytes > thresholds["large_over_bytes"]
        or line_count > thresholds["large_over_lines"]
    ):
        size_class = "large"
    elif (
        size_bytes > thresholds["small_max_bytes"]
        or line_count > thresholds["small_max_lines"]
    ):
        size_class = "medium"
    else:
        size_class = "small"
    return PathClassification(size_class, size_bytes, line_count, generated)


def _non_option_paths(
    tokens: list[str],
    start: int = 1,
    *,
    options_with_value: set[str] | None = None,
) -> list[str]:
    paths: list[str] = []
    skip_next = False
    options_with_value = options_with_value or set()
    for token in tokens[start:]:
        if skip_next:
            skip_next = False
            continue
        if token in options_with_value:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        paths.append(token)
    return paths


def _shell_tokens(command: str) -> list[str] | None:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return None


def _split_tokens(tokens: list[str], separator: str) -> list[list[str]]:
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token == separator:
            segments.append([])
        else:
            segments[-1].append(token)
    return segments


def _extract_input_redirect(tokens: list[str]) -> tuple[list[str], str | None, bool]:
    command: list[str] = []
    redirected_path: str | None = None
    index = 0
    while index < len(tokens):
        if tokens[index] != "<":
            command.append(tokens[index])
            index += 1
            continue
        if redirected_path is not None or index + 1 >= len(tokens):
            return tokens, None, True
        redirected_path = tokens[index + 1]
        index += 2
    return command, redirected_path, False


def _head_tail_limit(tokens: list[str]) -> int | None:
    if any(token in {"-f", "--follow"} or token.startswith("--follow=") for token in tokens):
        return None
    for index, token in enumerate(tokens[1:], start=1):
        if token in {"-n", "--lines"}:
            if index + 1 >= len(tokens) or not re.fullmatch(r"\d+", tokens[index + 1]):
                return None
            return int(tokens[index + 1])
        if token.startswith("--lines="):
            value = token.partition("=")[2]
            return int(value) if value.isdigit() else None
        if re.fullmatch(r"-\d+", token):
            return int(token[1:])
        if token in {"-c", "--bytes"}:
            if index + 1 >= len(tokens) or not re.fullmatch(r"\d+", tokens[index + 1]):
                return None
            return max(1, (int(tokens[index + 1]) + 79) // 80)
        if token.startswith("--bytes="):
            value = token.partition("=")[2]
            return max(1, (int(value) + 79) // 80) if value.isdigit() else None
    return 10


def _sed_program_and_paths(tokens: list[str]) -> tuple[list[str], list[str], bool]:
    programs: list[str] = []
    paths: list[str] = []
    quiet = False
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in {"-n", "--quiet", "--silent"}:
            quiet = True
        elif token in {"-e", "--expression"}:
            if index + 1 >= len(tokens):
                return programs, paths, quiet
            programs.append(tokens[index + 1])
            index += 1
        elif token.startswith("--expression="):
            programs.append(token.partition("=")[2])
        elif token in {"-f", "--file"} or token.startswith("--file="):
            return programs, paths, quiet
        elif token.startswith("-"):
            pass
        elif not programs:
            programs.append(token)
        else:
            paths.append(token)
        index += 1
    return programs, paths, quiet


def _sed_limit(tokens: list[str]) -> int | None:
    programs, _, quiet = _sed_program_and_paths(tokens)
    if not quiet or len(programs) != 1:
        return None
    match = re.fullmatch(r"\s*(\d+)(?:\s*,\s*(\d+))?p\s*", programs[0])
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2) or match.group(1))
    return end - start + 1 if end >= start else None


def _segment_likely_reads_file(tokens: list[str]) -> bool:
    if "<" in tokens:
        return True
    command, _, malformed_redirect = _extract_input_redirect(tokens)
    if malformed_redirect or not command:
        return malformed_redirect
    executable = Path(command[0]).name.lower()
    if executable in {"cat", "head", "tail", "less", "more", "tac", "nl", "wc"}:
        return bool(_non_option_paths(
            command,
            options_with_value={"-n", "--lines", "-c", "--bytes"},
        ))
    if executable == "sed":
        _, paths, _ = _sed_program_and_paths(command)
        return bool(paths)
    if executable in {"grep", "egrep", "fgrep", "rg", "awk", "jq"}:
        return len(_non_option_paths(command)) >= 2
    return False


def _classify_segment(
    tokens: list[str],
) -> tuple[str | None, str, int | None, bool]:
    command, redirected_path, malformed_redirect = _extract_input_redirect(tokens)
    if malformed_redirect:
        return None, "unparseable", None, True
    if not command:
        return (
            (redirected_path, "full", None, False)
            if redirected_path
            else (None, "other", None, False)
        )

    executable = Path(command[0]).name.lower()
    if executable == "cat":
        paths = _non_option_paths(command)
        if redirected_path and not paths:
            paths = [redirected_path]
        if len(paths) != 1:
            return None, "compound", None, bool(paths or redirected_path)
        return paths[0], "full", None, False

    if executable in {"head", "tail"}:
        paths = _non_option_paths(
            command,
            options_with_value={"-n", "--lines", "-c", "--bytes"},
        )
        if redirected_path and not paths:
            paths = [redirected_path]
        if len(paths) != 1:
            return None, "compound", None, bool(paths or redirected_path)
        limit = _head_tail_limit(command)
        return (
            (paths[0], "bounded", limit, False)
            if limit is not None
            else (paths[0], "full", None, False)
        )

    if executable == "sed":
        _, paths, _ = _sed_program_and_paths(command)
        if redirected_path and not paths:
            paths = [redirected_path]
        if len(paths) != 1:
            return None, "compound", None, bool(paths or redirected_path)
        limit = _sed_limit(command)
        return (
            (paths[0], "bounded", limit, False)
            if limit is not None
            else (paths[0], "full", None, False)
        )

    if executable == "wc":
        paths = _non_option_paths(command)
        if redirected_path and not paths:
            paths = [redirected_path]
        if len(paths) == 1:
            return paths[0], "metadata", None, False
        if paths:
            return None, "compound", None, True

    if redirected_path:
        return redirected_path, "full", None, False
    return None, "other", None, False


def _pipeline_consumer(
    tokens: list[str],
) -> tuple[str | None, str, int | None, bool]:
    path, command_class, limit, unparseable = _classify_segment(tokens)
    if unparseable or path is not None:
        return path, command_class, limit, unparseable
    command, redirected_path, malformed_redirect = _extract_input_redirect(tokens)
    if malformed_redirect or redirected_path or not command:
        return None, "full", None, malformed_redirect
    executable = Path(command[0]).name.lower()
    if executable in {"head", "tail"}:
        limit = _head_tail_limit(command)
        return (
            (None, "bounded", limit, False)
            if limit is not None
            else (None, "full", None, False)
        )
    if executable == "sed":
        limit = _sed_limit(command)
        return (
            (None, "bounded", limit, False)
            if limit is not None
            else (None, "full", None, False)
        )
    if executable == "wc":
        return None, "metadata", None, False
    return None, "full", None, False


def _parse_simple_shell(command: str) -> tuple[str | None, str, int | None, bool]:
    tokens = _shell_tokens(command)
    if tokens is None:
        likely_read = bool(
            re.search(r"(^|[;&|]\s*)(cat|head|tail|sed|less|more|wc)\b|<", command)
        )
        return (
            (None, "unparseable", None, True)
            if likely_read
            else (None, "other", None, False)
        )
    if not tokens:
        return None, "other", None, False

    compound_operators = {"&&", "||", ";", "&"}
    if any(token in compound_operators for token in tokens):
        segments: list[list[str]] = [[]]
        for token in tokens:
            if token in compound_operators:
                segments.append([])
            else:
                segments[-1].append(token)
        likely_read = any(_segment_likely_reads_file(segment) for segment in segments)
        return (
            (None, "compound", None, True)
            if likely_read
            else (None, "other", None, False)
        )

    pipeline = _split_tokens(tokens, "|")
    if any(not segment for segment in pipeline):
        likely_read = any(
            _segment_likely_reads_file(segment) for segment in pipeline if segment
        )
        return (
            (None, "unparseable", None, True)
            if likely_read
            else (None, "other", None, False)
        )

    path, command_class, limit, unparseable = _classify_segment(pipeline[0])
    if len(pipeline) == 1 or unparseable:
        return path, command_class, limit, unparseable

    for consumer in pipeline[1:]:
        (
            consumer_path,
            consumer_class,
            consumer_limit,
            consumer_unparseable,
        ) = _pipeline_consumer(consumer)
        if consumer_unparseable:
            return None, "compound", None, True
        if consumer_path is not None:
            path = consumer_path
            command_class = consumer_class
            limit = consumer_limit
            continue
        if command_class == "metadata":
            continue
        if consumer_class == "metadata":
            command_class, limit = "metadata", None
        elif consumer_class == "bounded":
            command_class = "bounded"
            limit = (
                min(limit, consumer_limit)
                if limit is not None and consumer_limit is not None
                else consumer_limit
            )
        elif command_class != "bounded":
            command_class, limit = "full", None
    return (
        (path, command_class, limit, False)
        if path is not None
        else (None, "other", None, False)
    )


def _first_mapping(payload: dict[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def parse_payload(
    payload: dict[str, Any],
    *,
    client: str,
    event: str = "pre_tool_use",
) -> GateRequest:
    tool_call = payload.get("toolCall") if isinstance(payload.get("toolCall"), dict) else {}
    tool_input = _first_mapping(payload, ("tool_input", "input", "arguments", "params"))
    if not tool_input and isinstance(tool_call.get("args"), dict):
        tool_input = tool_call["args"]
    tool = str(
        payload.get("tool_name")
        or payload.get("tool")
        or payload.get("name")
        or tool_call.get("name")
        or tool_input.get("tool")
        or ""
    )
    command = (
        tool_input.get("command")
        or tool_input.get("CommandLine")
        or tool_input.get("cmd")
        or payload.get("command")
    )
    path_value = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or payload.get("file_path")
        or payload.get("path")
    )
    mode = tool_input.get("mode") or payload.get("mode")
    limit = tool_input.get("limit") or payload.get("limit")
    returned_tokens = payload.get("returned_tokens")
    if returned_tokens is None and event.lower().startswith("post"):
        response = (
            payload.get("tool_response")
            or payload.get("tool_output")
            or payload.get("output")
            or payload.get("result")
        )
        if response is not None:
            if isinstance(response, dict):
                response = (
                    response.get("output")
                    or response.get("content")
                    or response.get("text")
                    or response.get("result")
                    or response
                )
            if isinstance(response, str):
                response_text = response
            else:
                try:
                    response_text = json.dumps(response, separators=(",", ":"))
                except (TypeError, ValueError):
                    response_text = str(response)
            returned_tokens = (len(response_text.encode("utf-8")) + 3) // 4
            if re.search(r"<<ccr:[^>]+>>|\[Archived:[^\]]+\]", response_text):
                reference = True
    reference = bool(
        locals().get("reference", False)
        or
        payload.get("expandable_reference")
        or payload.get("reference_id")
        or tool_input.get("reference_id")
    )

    command_class = None
    unparseable = False
    if isinstance(command, str):
        parsed_path, command_class, parsed_limit, unparseable = _parse_simple_shell(command)
        path_value = path_value or parsed_path
        limit = limit or parsed_limit

    return GateRequest(
        client=client,
        event=event,
        tool=tool,
        command=str(command) if isinstance(command, str) else None,
        path=str(path_value) if path_value is not None else None,
        mode=str(mode) if mode is not None else None,
        limit=int(limit) if isinstance(limit, int | str) and str(limit).isdigit() else None,
        command_class=command_class,
        unparseable=unparseable,
        returned_tokens=(
            int(returned_tokens)
            if isinstance(returned_tokens, int | str) and str(returned_tokens).isdigit()
            else None
        ),
        expandable_reference=reference,
        cache_hit=bool(payload.get("cache_hit")),
    )


def _is_ctx_read(tool: str) -> bool:
    normalized = tool.lower().replace("-", "_")
    return normalized == "ctx_read" or normalized.endswith("__ctx_read")


def _is_focused(request: GateRequest, policy: dict[str, Any]) -> bool:
    if request.command_class in {"bounded", "metadata", "targeted"}:
        if request.command_class != "bounded":
            return True
        return bool(
            request.limit is not None
            and request.limit <= policy["thresholds"]["focused_limit_lines"]
        )
    if request.limit is not None:
        return request.limit <= policy["thresholds"]["focused_limit_lines"]
    mode = (request.mode or "").lower()
    return mode in {"task", "reference"} or mode.startswith("lines:")


def _local_demotes(size_class: SizeClass) -> bool:
    config_home = Path(
        os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    )
    path = config_home / "context-routing" / "override.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get(size_class)
    except (OSError, json.JSONDecodeError, AttributeError):
        return False
    return value in {"warn", "allow"}


def _metric_path() -> Path:
    state_home = Path(
        os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
    )
    return state_home / "context-routing" / "metrics.jsonl"


def _path_hash(path: str | None) -> str:
    if not path:
        return ""
    try:
        canonical = str(Path(path).expanduser().resolve())
    except (OSError, ValueError):
        canonical = path
    return hashlib.sha256(canonical.encode("utf-8", errors="replace")).hexdigest()


def _write_metric(
    request: GateRequest,
    result: GateResult,
) -> None:
    metric = {
        "timestamp": datetime.now(UTC).isoformat(),
        "client": request.client,
        "decision": result.decision,
        "reason_code": result.reason_code,
        "file_extension": Path(request.path).suffix.lower() if request.path else "",
        "size_class": result.size_class,
        "requested_mode": request.mode,
        "command_class": request.command_class,
        "elapsed_ms": round(result.elapsed_ms, 3),
        "path_hash": _path_hash(request.path),
    }
    if request.returned_tokens is not None:
        metric["returned_tokens"] = request.returned_tokens
    if request.cache_hit:
        metric["cache_hit"] = True
    path = _metric_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(metric, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError:
        pass


def evaluate_request(
    request: GateRequest,
    *,
    policy: dict[str, Any] | None = None,
) -> GateResult:
    started = time.perf_counter()
    policy = policy or load_policy()
    classification = classify_path(request.path, policy) if request.path else PathClassification(
        "unknown", 0, 0
    )
    decision: Decision = "allow"
    reason = "unrelated-tool"
    message = ""

    if request.event.lower().startswith("post") and request.returned_tokens is None:
        reason = "post-output-unavailable"
    elif request.unparseable:
        decision, reason = "warn", "unparseable-compound-shell"
        message = "Compound shell read was not classified; prefer a dedicated focused tool"
    elif request.event.lower().startswith("post") and request.returned_tokens is not None:
        over_limit = (
            request.returned_tokens
            > policy["thresholds"]["post_compression_max_tokens"]
        )
        if over_limit and not request.expandable_reference:
            decision, reason = "warn", "oversized-unreferenced-output"
            message = "Output exceeds 4,000 tokens without an expandable reference"
        else:
            reason = "bounded-output"
    elif not request.path:
        reason = "no-file-read"
    elif _is_ctx_read(request.tool):
        mode = (request.mode or "").lower()
        if mode in policy["exact_modes"]:
            reason = "exactness-escape"
        elif _is_focused(request, policy):
            reason = "focused-read"
        elif classification.size_class in {"large", "huge"}:
            decision, reason = "warn", "ctx-read-missing-mode"
            message = policy["messages"]["large"]
        else:
            reason = "ctx-read"
    elif _is_focused(request, policy):
        reason = "focused-native-read"
    elif classification.size_class == "small":
        reason = "small-read"
    elif classification.size_class == "medium":
        decision, reason = "warn", "medium-unscoped-read"
        message = policy["messages"]["medium"]
    elif classification.size_class == "large":
        rollout = os.environ.get(
            "CONTEXT_ROUTING_ROLLOUT", policy["rollout"]["default_phase"]
        ).lower()
        decision = "deny" if rollout == "block" else "warn"
        reason = "large-unscoped-read"
        message = policy["messages"]["large"]
    elif classification.size_class == "huge":
        decision, reason = "deny", "huge-native-full-read"
        message = policy["messages"]["huge"]
    else:
        reason = "missing-or-unknown-path"

    if decision == "deny" and _local_demotes(classification.size_class):
        decision, reason = "warn", "local-demotion"
        message = f"Local override demoted enforcement; {message}"

    result = GateResult(
        decision=decision,
        reason_code=reason,
        message=message,
        size_class=classification.size_class,
        elapsed_ms=(time.perf_counter() - started) * 1_000,
    )
    _write_metric(request, result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", required=True)
    parser.add_argument("--event", default="pre_tool_use")
    parser.add_argument("--json", action="store_true", dest="emit_json")
    parser.add_argument("--hook", action="store_true")
    args = parser.parse_args(argv)

    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("payload root must be an object")
        request = parse_payload(payload, client=args.client, event=args.event)
        result = evaluate_request(request)
    except (json.JSONDecodeError, OSError, TypeError, ValueError) as error:
        if args.emit_json:
            print(
                json.dumps(
                    {
                        "decision": "allow",
                        "reason_code": "payload-parse-failed",
                        "message": str(error),
                        "size_class": "unknown",
                    }
                )
            )
        return 0

    if args.emit_json:
        print(json.dumps(asdict(result), sort_keys=True))
    if args.hook and result.decision in {"warn", "deny"}:
        print(f"CONTEXT ROUTING {result.decision.upper()}: {result.message}", file=sys.stderr)
    return 2 if args.hook and result.decision == "deny" else 0


if __name__ == "__main__":
    sys.exit(main())
