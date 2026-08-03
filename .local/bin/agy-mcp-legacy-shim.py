#!/usr/bin/env python3
"""Bridge AGY's draft MCP discovery probe to legacy stdio MCP servers.

AGY sends ``server/discover`` before the legacy ``initialize`` handshake. A
legacy server closes its stream on that request. Returning the normal JSON-RPC
"method not found" error lets AGY fall back to ``initialize``. The legacy
server is started only when that initialize request arrives, so AGY's
pre-initialize notifications cannot reach or terminate it.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from collections.abc import Sequence
from typing import BinaryIO


DISCOVERY_METHOD = "server/discover"
INITIALIZE_METHOD = "initialize"
METHOD_NOT_FOUND = -32601


def _write_line(stream: BinaryIO, data: bytes, lock: threading.Lock) -> None:
    with lock:
        stream.write(data)
        stream.flush()


def _discovery_error(message: dict[object, object]) -> bytes:
    response = {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "error": {
            "code": METHOD_NOT_FOUND,
            "message": f"Method not found: {DISCOVERY_METHOD}",
        },
    }
    return json.dumps(response, separators=(",", ":")).encode("utf-8") + b"\n"


def _decode_message(line: bytes) -> dict[object, object] | None:
    try:
        message = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return message if isinstance(message, dict) else None


def _is_notification(message: dict[object, object] | None) -> bool:
    return message is not None and "id" not in message


def _forward_stream(source: BinaryIO, destination: BinaryIO, lock: threading.Lock | None = None) -> None:
    for line in source:
        try:
            if lock is None:
                destination.write(line)
                destination.flush()
            else:
                _write_line(destination, line, lock)
        except BrokenPipeError:
            return


def _start_backend(command: Sequence[str], output_lock: threading.Lock) -> tuple[subprocess.Popen[bytes], list[threading.Thread]]:
    backend = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert backend.stdout is not None
    assert backend.stderr is not None

    # stdin is read by main(), rather than a daemon reader. That keeps Python
    # from trying to tear down a live stdin thread during interpreter shutdown.
    threads = [
        threading.Thread(
            target=_forward_stream,
            args=(backend.stdout, sys.stdout.buffer, output_lock),
        ),
        threading.Thread(
            target=_forward_stream,
            args=(backend.stderr, sys.stderr.buffer),
        ),
    ]
    for thread in threads:
        thread.start()
    return backend, threads


def _close_stdin(backend: subprocess.Popen[bytes]) -> None:
    if backend.stdin is None:
        return
    try:
        backend.stdin.close()
    except BrokenPipeError:
        pass


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments or arguments[0] != "--" or len(arguments) == 1:
        print(f"usage: {sys.argv[0]} -- <legacy-mcp-command> [args...]", file=sys.stderr)
        return 2

    backend: subprocess.Popen[bytes] | None = None
    backend_threads: list[threading.Thread] = []
    output_lock = threading.Lock()
    returncode = 0

    try:
        for line in sys.stdin.buffer:
            message = _decode_message(line)
            method = message.get("method") if message is not None else None

            if method == DISCOVERY_METHOD:
                # Notifications do not have an id and must not receive a response.
                if message is not None and not _is_notification(message):
                    _write_line(sys.stdout.buffer, _discovery_error(message), output_lock)
                continue

            if backend is None:
                if method != INITIALIZE_METHOD:
                    # AGY can send notifications such as roots/list_changed before
                    # initialize. Discard every pre-initialize message so none can
                    # reach the legacy server.
                    continue
                backend, backend_threads = _start_backend(arguments[1:], output_lock)

            assert backend.stdin is not None
            try:
                backend.stdin.write(line)
                backend.stdin.flush()
            except BrokenPipeError:
                break
    finally:
        if backend is not None:
            _close_stdin(backend)
            returncode = backend.wait()
            for thread in backend_threads:
                thread.join()

    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
