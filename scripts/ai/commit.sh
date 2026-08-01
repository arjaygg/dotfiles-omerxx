#!/usr/bin/env bash
# Canonical AI commit entrypoint.
# Usage: commit.sh -m "type(scope): subject" -m "body explaining why"
set -euo pipefail

SCRIPTS_AI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if git diff --cached --quiet; then
    echo "⛔ Nothing is staged for commit." >&2
    exit 1
fi

STATUS=$("$SCRIPTS_AI/atomic-status.sh" || echo "unknown")
if [[ "$STATUS" == "blocked" ]]; then
    echo "⛔ Commit blocked: working tree contains mixed concerns." >&2
    echo "   Run: $SCRIPTS_AI/atomic-status.sh  to see details." >&2
    exit 1
fi

SUBJECT=""
BODY=""
MSG_COUNT=0
while [[ $# -gt 0 ]]; do
    case $1 in
        -m)
            if [[ -z "${2:-}" ]]; then
                echo "⛔ Missing value for -m" >&2
                exit 1
            fi
            MSG_COUNT=$((MSG_COUNT + 1))
            if [[ $MSG_COUNT -eq 1 ]]; then
                SUBJECT="$2"
            elif [[ $MSG_COUNT -eq 2 ]]; then
                BODY="$2"
            else
                BODY="$BODY

$2"
            fi
            shift 2
            ;;
        *)
            echo "⛔ Unknown argument: $1" >&2
            echo "Usage: $0 -m \"type(scope): subject\" -m \"body explaining why\"" >&2
            exit 1
            ;;
    esac
done

if [[ -z "$SUBJECT" || -z "$BODY" ]]; then
    echo "⛔ A conventional subject and explanatory body are required." >&2
    exit 1
fi

CONVENTIONAL_PATTERN='^(feat|fix|docs|style|refactor|test|chore|build|ci|perf|revert)(\([a-zA-Z0-9_/-]+\))?: .+'
if ! printf '%s\n' "$SUBJECT" | grep -qE "$CONVENTIONAL_PATTERN"; then
    echo "⛔ Subject must follow conventional commit format." >&2
    exit 1
fi

MSG_FILE=$(mktemp)
trap 'rm -f "$MSG_FILE"' EXIT
printf '%s\n\n%s\n' "$SUBJECT" "$BODY" > "$MSG_FILE"
if ! grep -qi "Co-authored-by:.*AI" "$MSG_FILE"; then
    printf '\nCo-authored-by: AI Agent <ai@local>\n' >> "$MSG_FILE"
fi

validate_message_file() {
    local final_subject final_body
    final_subject=$(python3 - "$MSG_FILE" <<'PYMSG'
from pathlib import Path
import sys
lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
print(lines[0] if lines else "")
PYMSG
)
    final_body=$(python3 - "$MSG_FILE" <<'PYBODY'
from pathlib import Path
import sys
lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
print("\n".join(lines[1:]).strip())
PYBODY
)
    if ! printf '%s\n' "$final_subject" | grep -qE "$CONVENTIONAL_PATTERN"; then
        echo "⛔ Commit hook produced a non-conventional subject." >&2
        exit 1
    fi
    if [[ -z "$final_body" ]]; then
        echo "⛔ Commit hook removed the required body." >&2
        exit 1
    fi
    SUBJECT="$final_subject"
}

if [[ "${LIFECYCLE_COMMIT_MODE:-}" == "private-v1" ]]; then
    EXPECTED_PARENT="${LIFECYCLE_EXPECTED_PARENT:-}"
    EXPECTED_REF="${LIFECYCLE_EXPECTED_REF:-}"
    EXPECTED_TREE="${LIFECYCLE_EXPECTED_TREE:-}"
    if [[ ! "$EXPECTED_PARENT" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]] \
        || [[ ! "$EXPECTED_TREE" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]] \
        || [[ ! "$EXPECTED_REF" =~ ^refs/heads/(feature|feat|bugfix|fix|hotfix|release|chore)/[A-Za-z0-9._/-]+$ ]]; then
        echo "⛔ Invalid lifecycle private-commit evidence." >&2
        exit 1
    fi
    if [[ -z "${GIT_INDEX_FILE:-}" || -L "$GIT_INDEX_FILE" || ! -f "$GIT_INDEX_FILE" ]]; then
        echo "⛔ Lifecycle private index is unavailable or unsafe." >&2
        exit 1
    fi
    CURRENT_REF=$(git symbolic-ref -q HEAD 2>/dev/null || true)
    CURRENT_PARENT=$(git rev-parse --verify "$EXPECTED_REF^{commit}" 2>/dev/null || true)
    CURRENT_TREE=$(git write-tree 2>/dev/null || true)
    if [[ "$CURRENT_REF" != "$EXPECTED_REF" || "$CURRENT_PARENT" != "$EXPECTED_PARENT" || "$CURRENT_TREE" != "$EXPECTED_TREE" ]]; then
        echo "⛔ Lifecycle private-commit evidence changed before commit." >&2
        exit 1
    fi
    # Lifecycle mode uses adapter-owned validation, message evidence, and CAS.
    # Repository hooks are mutable project code and must never execute here.
    validate_message_file
    COMMIT_OID=$(git -c core.hooksPath=/dev/null commit-tree "$EXPECTED_TREE" -p "$EXPECTED_PARENT" < "$MSG_FILE")
    if [[ ! "$COMMIT_OID" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]]; then
        echo "⛔ Object creation did not return an exact object id." >&2
        exit 1
    fi
    if ! git -c core.hooksPath=/dev/null update-ref -m "lifecycle approved commit" "$EXPECTED_REF" "$COMMIT_OID" "$EXPECTED_PARENT"; then
        echo "⛔ Branch changed concurrently; lifecycle commit CAS refused." >&2
        exit 1
    fi
else
    git commit -F "$MSG_FILE"
fi
echo "✅ Commit successful."

_REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -n "$_REPO_ROOT" ]]; then
    _INTENT_FILE="$_REPO_ROOT/.claude-atomic-intent"
    _COMMIT_TYPE=$(echo "$SUBJECT" | sed -n 's/^\([a-z]*\).*/\1/p')
    _COMMIT_SCOPE=$(echo "$SUBJECT" | sed -n 's/^[a-z]*(\([^)]*\)).*/\1/p')
    _COMMIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    _COMMIT_TIME=$(date '+%s')
    python3 - "$_INTENT_FILE" "$_COMMIT_TYPE" "$_COMMIT_SCOPE" "$_COMMIT_HASH" "$_COMMIT_TIME" <<'PYINTENT'
import os
import pathlib
import tempfile
import sys

path = pathlib.Path(sys.argv[1])
payload = (
    f"LAST_COMMIT_TYPE={sys.argv[2]}\n"
    f"LAST_COMMIT_SCOPE={sys.argv[3]}\n"
    f"LAST_COMMIT_HASH={sys.argv[4]}\n"
    f"LAST_COMMIT_TIME={sys.argv[5]}\n"
).encode()
fd, temporary = tempfile.mkstemp(prefix=".claude-atomic-intent.", dir=path.parent)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "wb", closefd=True) as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
except BaseException:
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
    raise
PYINTENT
fi
