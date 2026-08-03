#!/usr/bin/env python3
"""Headroom single-proxy hardening and recursive-CCR safety checks."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence


NATIVE_CONTEXT_TOOLS = frozenset(
    {
        "bash",
        "codebase_search",
        "exec_command",
        "glob",
        "grep",
        "grep_search",
        "list_directory",
        "list_files",
        "listdirectory",
        "listfiles",
        "read",
        "read_file",
        "read_many_files",
        "read_text_file",
        "readfile",
        "run_command",
        "run_shell_command",
        "search",
        "search_file_content",
        "search_files",
        "semantic_search",
        "shell",
        "shell_command",
        "view",
        "view_file",
    }
)
LEANCTX_CONTEXT_TOOLS = frozenset(
    {
        "ctx_call",
        "ctx_compose",
        "ctx_expand",
        "ctx_glob",
        "ctx_read",
        "ctx_search",
        "ctx_session",
        "ctx_shell",
        "ctx_tree",
        "shell",
    }
)
HEADROOM_EXCLUDED_TOOLS = frozenset(
    NATIVE_CONTEXT_TOOLS
    | LEANCTX_CONTEXT_TOOLS
    | {
        f"{prefix}{tool}"
        for prefix in ("mcp__lean_ctx__", "mcp__lean-ctx__")
        for tool in LEANCTX_CONTEXT_TOOLS
    }
)

_CCR_RE = re.compile(r"<<ccr:([a-fA-F0-9]+)[^>]*>>")


class CCRRecoveryError(ValueError):
    """A local CCR entry cannot be recovered safely."""


def hardening_environment() -> dict[str, str]:
    return {
        "HEADROOM_CONTEXT_TOOL": "lean-ctx",
        "HEADROOM_DISABLE_KOMPRESS": "1",
        "HEADROOM_EXCLUDE_TOOLS": ",".join(sorted(HEADROOM_EXCLUDED_TOOLS)),
        "HEADROOM_NO_SUBSCRIPTION_TRACKING": "1",
    }


def detect_recursive_ccr(content: str, content_hash: str) -> list[str]:
    findings: list[str] = []
    markers = _CCR_RE.findall(content)
    if markers:
        findings.append("nested-ccr")
    if any(marker.lower() == content_hash.lower() for marker in markers):
        findings.append("self-referential-ccr")
    return findings


def remove_headroom_mcp_server(text: str) -> str:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    skipping = False
    for line in lines:
        table = re.match(r"^\s*\[([^\]]+)\]\s*$", line)
        if table:
            skipping = table.group(1).strip() == "mcp_servers.headroom"
            if skipping:
                while output and not output[-1].strip():
                    output.pop()
                continue
        if not skipping:
            output.append(line)
    cleaned = "".join(output)
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def audit_ccr_database(
    path: Path,
    *,
    delete_invalid: bool = False,
) -> dict[str, Any]:
    connection = sqlite3.connect(path)
    invalid_hashes: list[str] = []
    total = 0
    try:
        rows = connection.execute("select hash, entry_json from ccr_entries")
        for content_hash, entry_json in rows:
            total += 1
            try:
                entry = json.loads(entry_json)
            except json.JSONDecodeError:
                invalid_hashes.append(content_hash)
                continue
            original = entry.get("original_content", "")
            if not isinstance(original, str) or detect_recursive_ccr(
                original, content_hash
            ):
                invalid_hashes.append(content_hash)
        if delete_invalid and invalid_hashes:
            connection.executemany(
                "delete from ccr_entries where hash = ?",
                [(content_hash,) for content_hash in invalid_hashes],
            )
            connection.commit()
    finally:
        connection.close()
    return {
        "total": total,
        "invalid": len(invalid_hashes),
        "deleted": len(invalid_hashes) if delete_invalid else 0,
        "ok": not invalid_hashes,
    }


def recover_ccr_bytes(path: Path, content_hash: str) -> bytes:
    try:
        connection = sqlite3.connect(path)
        try:
            row = connection.execute(
                "select entry_json from ccr_entries where hash = ?",
                (content_hash,),
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise CCRRecoveryError(f"CCR database error: {error}") from error

    if row is None:
        raise CCRRecoveryError(f"CCR entry not found: {content_hash}")
    try:
        entry = json.loads(row[0])
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as error:
        raise CCRRecoveryError(f"CCR entry is malformed: {content_hash}") from error
    if not isinstance(entry, dict) or not isinstance(
        entry.get("original_content"), str
    ):
        raise CCRRecoveryError(f"CCR entry is malformed: {content_hash}")

    original = entry["original_content"]
    findings = detect_recursive_ccr(original, content_hash)
    if findings:
        raise CCRRecoveryError(
            f"CCR entry is unsafe ({', '.join(findings)}): {content_hash}"
        )
    try:
        return original.encode("utf-8")
    except UnicodeEncodeError as error:
        raise CCRRecoveryError(f"CCR entry is malformed: {content_hash}") from error


def summarize_containers(rows: Iterable[dict[str, str]]) -> dict[str, Any]:
    containers = list(rows)
    persistent_healthy = sum(
        row.get("kind") == "persistent" and row.get("health") == "healthy"
        for row in containers
    )
    orphan_mcp = sum(
        row.get("kind") in {"mcp", "orphan"} for row in containers
    )
    return {
        "total": len(containers),
        "persistent_healthy": persistent_healthy,
        "orphan_mcp": orphan_mcp,
        "ok": persistent_healthy == 1 and orphan_mcp == 0,
    }


def docker_containers() -> list[dict[str, str]]:
    try:
        process = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "ancestor=ghcr.io/chopratejas/headroom:latest",
                "--format",
                "{{json .}}",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    if process.returncode != 0:
        return []

    rows: list[dict[str, str]] = []
    for line in process.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = str(item.get("Names", ""))
        command = str(item.get("Command", "")).lower()
        status = str(item.get("Status", "")).lower()
        if name == "headroom-default":
            kind = "persistent"
        elif "headroom mcp serve" in command:
            kind = "mcp"
        else:
            kind = "orphan"
        rows.append(
            {
                "name": name,
                "health": (
                    "healthy"
                    if "(healthy)" in status
                    else "unhealthy"
                    if "(unhealthy)" in status
                    else "unknown"
                ),
                "kind": kind,
            }
        )
    return rows


def stop_orphan_containers(rows: Iterable[dict[str, str]]) -> list[str]:
    stopped: list[str] = []
    for row in rows:
        name = row.get("name", "")
        if row.get("kind") not in {"mcp", "orphan"} or not name:
            continue
        try:
            result = subprocess.run(
                ["docker", "stop", name],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            continue
        if result.returncode == 0:
            stopped.append(name)
    return stopped


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("env")
    cleanup = subparsers.add_parser("clean-codex")
    cleanup.add_argument("path", type=Path)
    cleanup.add_argument("--write", action="store_true")
    containers = subparsers.add_parser("containers")
    containers.add_argument("--stop-orphans", action="store_true")
    audit = subparsers.add_parser("audit-ccr")
    audit.add_argument("path", type=Path)
    audit.add_argument("--delete-invalid", action="store_true")
    recovery = subparsers.add_parser("recover-ccr")
    recovery.add_argument("path", type=Path)
    recovery.add_argument("hash")
    args = parser.parse_args(argv)

    if args.command == "env":
        print(json.dumps(hardening_environment(), indent=2, sort_keys=True))
        return 0
    if args.command == "clean-codex":
        source = args.path.read_text(encoding="utf-8")
        cleaned = remove_headroom_mcp_server(source)
        if args.write:
            args.path.write_text(cleaned, encoding="utf-8")
        else:
            print(cleaned, end="")
        return 0
    if args.command == "audit-ccr":
        report = audit_ccr_database(args.path, delete_invalid=args.delete_invalid)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["ok"] or args.delete_invalid else 1
    if args.command == "recover-ccr":
        try:
            content = recover_ccr_bytes(args.path, args.hash)
        except CCRRecoveryError as error:
            print(f"headroom_hardening: {error}", file=sys.stderr)
            return 1
        sys.stdout.buffer.write(content)
        return 0

    rows = docker_containers()
    stopped = stop_orphan_containers(rows) if args.stop_orphans else []
    summary = summarize_containers(docker_containers() if stopped else rows)
    summary["stopped"] = stopped
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
