#!/usr/bin/env python3
"""Adapt Content-Length framed MCP stdio clients to pctx's JSONL stdio."""
import os
import shutil
import subprocess
import sys
import threading


def read_content_length_message(stream):
    content_length = None
    while True:
        line = stream.readline()
        if line == b"":
            return None
        if line in (b"\r\n", b"\n"):
            break
        name, sep, value = line.partition(b":")
        if sep and name.strip().lower() == b"content-length":
            content_length = int(value.strip())
    if content_length is None:
        raise ValueError("missing Content-Length header")
    body = stream.read(content_length)
    if len(body) != content_length:
        return None
    return body


def client_to_pctx(child):
    try:
        while True:
            body = read_content_length_message(sys.stdin.buffer)
            if body is None:
                break
            child.stdin.write(body.rstrip(b"\r\n") + b"\n")
            child.stdin.flush()
    except Exception as exc:
        print(f"pctx shim client->pctx error: {exc}", file=sys.stderr, flush=True)
    finally:
        try:
            child.stdin.close()
        except Exception:
            pass


def pctx_to_client(child):
    try:
        while True:
            line = child.stdout.readline()
            if line == b"":
                break
            body = line.rstrip(b"\r\n")
            if not body:
                continue
            sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
            sys.stdout.buffer.flush()
    except Exception as exc:
        print(f"pctx shim pctx->client error: {exc}", file=sys.stderr, flush=True)


def stderr_to_stderr(child):
    while True:
        chunk = child.stderr.read(8192)
        if not chunk:
            break
        sys.stderr.buffer.write(chunk)
        sys.stderr.buffer.flush()


def main():
    pctx_bin = os.environ.get("PCTX_BIN") or shutil.which("pctx") or "/Users/axos-agallentes/homebrew/bin/pctx"
    args = sys.argv[1:] or ["mcp", "start", "--stdio", "-c", os.path.expanduser("~/.config/pctx/pctx.json")]
    child = subprocess.Popen(
        [pctx_bin, *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd(),
    )
    threads = [
        threading.Thread(target=client_to_pctx, args=(child,), daemon=True),
        threading.Thread(target=pctx_to_client, args=(child,), daemon=True),
        threading.Thread(target=stderr_to_stderr, args=(child,), daemon=True),
    ]
    for thread in threads:
        thread.start()
    threads[0].join()
    return child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
