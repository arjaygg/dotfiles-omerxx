#!/usr/bin/env bash
# Pre-commit: block staged files larger than 500KB.
set -euo pipefail

MAX_KB=500
MAX_BYTES=$(( MAX_KB * 1024 ))
STAGED=$(git diff --cached --name-only 2>/dev/null || true)

if [[ -z "$STAGED" ]]; then
    exit 0
fi

while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    [[ -f "$file" ]] || continue
    SIZE=$(wc -c < "$file" 2>/dev/null || echo 0)
    if [[ "$SIZE" -gt "$MAX_BYTES" ]]; then
        KB=$(( SIZE / 1024 ))
        echo "⛔ git-hook: $file is too large (${KB}KB > ${MAX_KB}KB)." >&2
        echo "   Large files should not be committed to this repo." >&2
        exit 1
    fi
done <<< "$STAGED"

exit 0
