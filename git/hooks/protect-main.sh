#!/usr/bin/env bash
# Pre-commit: block direct commits to main/master.
set -euo pipefail

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"

if [[ "$BRANCH" == "main" || "$BRANCH" == "master" ]]; then
    echo "⛔ git-hook: Direct commits to '$BRANCH' are not allowed." >&2
    echo "   Create a feature branch first:" >&2
    echo "   git checkout -b feat/<name>" >&2
    exit 1
fi

exit 0
