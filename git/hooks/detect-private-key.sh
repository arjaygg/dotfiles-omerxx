#!/usr/bin/env bash
# Pre-commit: block staged files containing private key headers.
set -euo pipefail

PATTERN='-----BEGIN (RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY'
STAGED=$(git diff --cached --name-only 2>/dev/null || true)

if [[ -z "$STAGED" ]]; then
    exit 0
fi

while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    [[ -f "$file" ]] || continue
    if grep -qE "$PATTERN" "$file" 2>/dev/null; then
        echo "⛔ git-hook: Private key detected in staged file: $file" >&2
        echo "   Remove the key before committing." >&2
        exit 1
    fi
done <<< "$STAGED"

exit 0
