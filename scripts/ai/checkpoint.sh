#!/usr/bin/env bash
# Canonical bounded-stop path for incomplete but verified work.
# Usage: checkpoint.sh [--type <type>] [-m <message>] [--path <path>]... [--] <path>...
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMIT_TYPE="chore"
CUSTOM_MSG=""
PATHS=()

usage() {
    echo "Usage: $0 [--type <type>] [-m <message>] [--path <path>]... [--] <path>..." >&2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)
            [[ -n "${2:-}" ]] || { echo "⛔ --type requires a value." >&2; exit 1; }
            COMMIT_TYPE="$2"
            shift 2
            ;;
        -m)
            [[ -n "${2:-}" ]] || { echo "⛔ -m requires a value." >&2; exit 1; }
            CUSTOM_MSG="$2"
            shift 2
            ;;
        --path)
            [[ -n "${2:-}" ]] || { echo "⛔ --path requires a value." >&2; exit 1; }
            PATHS+=("$2")
            shift 2
            ;;
        --)
            shift
            while [[ $# -gt 0 ]]; do
                PATHS+=("$1")
                shift
            done
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo "⛔ Unknown option: $1" >&2
            usage
            exit 1
            ;;
        *)
            PATHS+=("$1")
            shift
            ;;
    esac
done

if [[ ${#PATHS[@]} -eq 0 ]]; then
    echo "⛔ Checkpoint requires at least one explicit path." >&2
    usage
    exit 1
fi

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
    echo "⛔ Checkpoint must run inside a git repository." >&2
    exit 1
fi

# Refuse an index containing staged files outside the explicit path set.
if ! git diff --cached --quiet; then
    UNRELATED=$(comm -23 \
        <(git diff --cached --name-only | LC_ALL=C sort) \
        <(git diff --cached --name-only -- "${PATHS[@]}" | LC_ALL=C sort))
    if [[ -n "$UNRELATED" ]]; then
        echo "⛔ Refusing checkpoint: unrelated paths are already staged:" >&2
        printf '   %s\n' "$UNRELATED" >&2
        exit 1
    fi
fi

git add -- "${PATHS[@]}"

if git diff --cached --quiet; then
    echo "⛔ No changes from the explicit paths are staged." >&2
    exit 1
fi

if [[ -n "$CUSTOM_MSG" ]]; then
    SUBJECT="${COMMIT_TYPE}(checkpoint): $CUSTOM_MSG"
else
    SUBJECT="${COMMIT_TYPE}(checkpoint): bounded incomplete work"
fi

"$SCRIPT_DIR/commit.sh" \
    -m "$SUBJECT" \
    -m "Preserve explicitly selected incomplete work without staging unrelated changes."

echo "✅ Checkpoint created. Agent loop reset."
