#!/usr/bin/env bash
# Canonical bounded-stop path for incomplete but verified work.
# Stages all changes and commits as type(checkpoint) with --no-verify.
# Usage: checkpoint.sh [--type <type>] ["message"]
#   --type <type>  Commit type (default: chore). E.g., refactor, feat, fix.
set -euo pipefail

COMMIT_TYPE="chore"
CUSTOM_MSG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)
            COMMIT_TYPE="${2:-chore}"
            shift 2
            ;;
        -m)
            CUSTOM_MSG="${2:-}"
            shift 2
            ;;
        *)
            CUSTOM_MSG="$*"
            break
            ;;
    esac
done

if [[ -n "$CUSTOM_MSG" ]]; then
    MSG="${COMMIT_TYPE}(checkpoint): $CUSTOM_MSG

bounded incomplete work"
else
    MSG="${COMMIT_TYPE}(checkpoint): bounded incomplete work"
fi

# Stage everything
git add .

printf '%s\n' "$MSG" | git commit --no-verify -F -

echo "✅ Checkpoint created. Agent loop reset."
