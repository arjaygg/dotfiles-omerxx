#!/usr/bin/env bash
# Append normalized context-evaluation events to a gitignored local store.

set -euo pipefail

EVENT="${1:-}"
[[ -n "$EVENT" ]] || exit 0

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
STORE_DIR="${CONTEXT_EVAL_STORE_DIR:-$REPO_ROOT/.claude/cache/context-eval}"
STORE_FILE="$STORE_DIR/events.jsonl"

mkdir -p "$STORE_DIR"

PAYLOAD_FILE=$(mktemp)
trap 'rm -f "$PAYLOAD_FILE"' EXIT
cat > "$PAYLOAD_FILE" || true

python3 - "$STORE_FILE" "$PAYLOAD_FILE" "$EVENT" "$REPO_ROOT" "${CONTEXT_EVAL_MODE:-baseline}" "${CONTEXT_EVAL_WORKFLOW:-}" <<'PYEOF'
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

store_file, payload_file, event, repo_root, mode, workflow = sys.argv[1:7]
root = Path(repo_root)
payload_path = Path(payload_file)


def load_payload() -> dict:
    try:
        raw = payload_path.read_text(encoding="utf-8", errors="replace").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"value": data}
    except Exception:
        return {}


def git_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def file_present(rel_path: str) -> bool:
    path = root / rel_path
    return path.exists() and path.is_file() and path.stat().st_size > 0


def extract_text(obj) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        parts = []
        for item in obj:
            parts.append(extract_text(item))
        return "\n".join([p for p in parts if p])
    if not isinstance(obj, dict):
        return ""

    pieces = []
    content = obj.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str) and text:
                    pieces.append(text)
    elif isinstance(content, str) and content:
        pieces.append(content)

    for key in ("output", "stdout", "stderr", "text"):
        value = obj.get(key)
        if isinstance(value, str) and value:
            pieces.append(value)

    tool_response = obj.get("tool_response")
    if isinstance(tool_response, dict):
        nested = extract_text(tool_response)
        if nested:
            pieces.append(nested)

    return "\n".join([p for p in pieces if p])


def count_lines(text: str) -> int:
    stripped = text.strip("\n")
    if not stripped:
        return 0
    return stripped.count("\n") + 1


def shorten(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


payload = load_payload()
record = {
    "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    "event": event,
    "mode": mode or "baseline",
    "workflow": workflow or None,
    "repo_root": str(root),
    "branch": git_branch(),
    "session_id": payload.get("session_id") or None,
}

data = {}

if event == "session-start":
    handoff_path = root / "plans/session-handoff.md"
    data = {
        "handoff_present": file_present("plans/session-handoff.md"),
        "active_context_present": file_present("plans/active-context.md"),
        "decisions_present": file_present("plans/decisions.md"),
        "progress_present": file_present("plans/progress.md"),
    }
    if handoff_path.exists() and handoff_path.is_file():
        try:
            age_seconds = max(0, int(datetime.now().timestamp() - handoff_path.stat().st_mtime))
            data["handoff_age_minutes"] = round(age_seconds / 60, 1)
        except Exception:
            pass
elif event == "notification":
    message = str(
        payload.get("message")
        or payload.get("title")
        or payload.get("body")
        or payload
    )
    remaining = None
    match = re.search(r"(\d+)%\s*remaining", message, re.IGNORECASE)
    if match:
        remaining = int(match.group(1))
    else:
        match = re.search(r"context.*?(\d+)%\s*used", message, re.IGNORECASE)
        if match:
            remaining = max(0, 100 - int(match.group(1)))
    data = {
        "context_remaining": remaining,
        "matched_context_warning": remaining is not None,
        "artifact_risk": "artifact risk" in message.lower(),
        "message": shorten(message),
    }
elif event == "pre-compact":
    trigger = payload.get("trigger")
    transcript_path = payload.get("transcript_path")
    data = {
        "trigger": trigger or None,
        "transcript_path_present": bool(transcript_path),
    }
elif event == "post-bash":
    output_text = extract_text(payload)
    line_count = count_lines(output_text)
    tool_name = payload.get("tool_name") or payload.get("name") or "Bash"
    data = {
        "tool_name": tool_name,
        "output_line_count": line_count,
        "compacted": line_count > 300,
    }
elif event == "stop":
    data = {
        "handoff_written": file_present("plans/session-handoff.md"),
        "active_context_present": file_present("plans/active-context.md"),
        "progress_present": file_present("plans/progress.md"),
    }
else:
    data = {"payload_keys": sorted(payload.keys())[:20]}

record["data"] = data

with open(store_file, "a", encoding="utf-8") as f:
    f.write(json.dumps(record, sort_keys=True) + "\n")
PYEOF
