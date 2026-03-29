#!/usr/bin/env bash
# Pre-commit: block staged files larger than MAX_KB (default 500KB).
# Configurable via .claude-atomic.yaml:
#   limits:
#     max_file_size_kb: 1024
set -euo pipefail

MAX_KB=500

# Load per-repo override if .claude-atomic.yaml exists
_REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
_OVERRIDE_FILE="$_REPO_ROOT/.claude-atomic.yaml"
if [[ -f "$_OVERRIDE_FILE" ]]; then
    _custom_kb=$(grep -E '^\s+max_file_size_kb:' "$_OVERRIDE_FILE" 2>/dev/null | head -1 | awk '{print $2}' || true)
    [[ -n "$_custom_kb" ]] && MAX_KB="$_custom_kb"
fi
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
