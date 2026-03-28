#!/usr/bin/env bash
# Canonical bounded-stop path for incomplete but verified work.
# Stages all changes and commits as chore(checkpoint) with --no-verify.
# Usage: checkpoint.sh ["message"]
set -euo pipefail

MSG="chore(checkpoint): bounded incomplete work"

if [[ $# -gt 0 ]]; then
    if [[ "$1" == "-m" && -n "${2:-}" ]]; then
        MSG="chore(checkpoint): $2

bounded incomplete work"
    else
        MSG="chore(checkpoint): $*

bounded incomplete work"
    fi
fi

# Stage everything
git add .

printf '%s\n' "$MSG" | git commit --no-verify -F -

echo "✅ Checkpoint created. Agent loop reset."
