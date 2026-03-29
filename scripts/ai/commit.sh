#!/usr/bin/env bash
# Canonical AI commit entrypoint.
# Usage: commit.sh -m "type(scope): subject" -m "body explaining why"
# Requires two -m flags: subject and body. Enforces conventional commit format.
set -euo pipefail

SCRIPTS_AI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Validate staged changes ---
if git diff --cached --quiet; then
    echo "⛔ Nothing is staged for commit." >&2
    exit 1
fi

# --- Check atomicity ---
STATUS=$("$SCRIPTS_AI/atomic-status.sh" || echo "unknown")
if [[ "$STATUS" == "blocked" ]]; then
    echo "⛔ Commit blocked: working tree contains mixed concerns." >&2
    echo "   Run: $SCRIPTS_AI/atomic-status.sh  to see details." >&2
    exit 1
fi

# --- Parse -m arguments ---
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
            MSG_COUNT=$(( MSG_COUNT + 1 ))
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

if [[ -z "$SUBJECT" ]]; then
    echo "⛔ Usage: $0 -m \"type(scope): subject\" -m \"body explaining why\"" >&2
    exit 1
fi

if [[ -z "$BODY" ]]; then
    echo "⛔ A commit body is required. Explain the 'Why' behind this change." >&2
    echo "Usage: $0 -m \"type(scope): subject\" -m \"body explaining why\"" >&2
    exit 1
fi

# --- Validate conventional commit format ---
CONVENTIONAL_PATTERN='^(feat|fix|docs|style|refactor|test|chore|build|ci|perf|revert)(\([a-zA-Z0-9_/-]+\))?: .+'
if ! echo "$SUBJECT" | grep -qE "$CONVENTIONAL_PATTERN"; then
    echo "⛔ Subject must follow conventional commit format:" >&2
    echo "   type(scope): description" >&2
    echo "   Types: feat fix docs style refactor test chore build ci perf revert" >&2
    echo "   Got: $SUBJECT" >&2
    exit 1
fi

# --- Write commit message to temp file ---
MSG_FILE=$(mktemp)
trap 'rm -f "$MSG_FILE"' EXIT

printf '%s\n\n%s\n' "$SUBJECT" "$BODY" > "$MSG_FILE"

# --- Add AI attribution if missing ---
if ! grep -qi "Co-authored-by:.*AI" "$MSG_FILE"; then
    printf '\nCo-authored-by: AI Agent <ai@local>\n' >> "$MSG_FILE"
fi

# --- Commit ---
git commit -F "$MSG_FILE"
echo "✅ Commit successful."

# --- Write intent file for drift detection ---
_REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -n "$_REPO_ROOT" ]]; then
    _INTENT_FILE="$_REPO_ROOT/.claude-atomic-intent"
    # Extract type and scope from subject: type(scope): desc
    _COMMIT_TYPE=$(echo "$SUBJECT" | sed -n 's/^\([a-z]*\).*/\1/p')
    _COMMIT_SCOPE=$(echo "$SUBJECT" | sed -n 's/^[a-z]*(\([^)]*\)).*/\1/p')
    _COMMIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    cat > "$_INTENT_FILE" <<INTENT
LAST_COMMIT_TYPE=$_COMMIT_TYPE
LAST_COMMIT_SCOPE=$_COMMIT_SCOPE
LAST_COMMIT_HASH=$_COMMIT_HASH
LAST_COMMIT_TIME=$(date '+%s')
INTENT
fi
