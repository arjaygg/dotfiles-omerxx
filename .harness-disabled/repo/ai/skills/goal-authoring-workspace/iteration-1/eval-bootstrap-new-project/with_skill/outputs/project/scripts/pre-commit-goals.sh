#!/usr/bin/env bash
set -euo pipefail

changed="$(git diff --cached --name-only --diff-filter=ACMRD -- goals plans/active-context.md 2>/dev/null || true)"

if [[ -z "$changed" ]]; then
  exit 0
fi

python3 scripts/validate_goals.py
