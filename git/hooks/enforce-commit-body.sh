#!/usr/bin/env bash
# Commit-msg: enforce a non-empty body explaining the "Why" behind the change.
set -euo pipefail

COMMIT_MSG_FILE="$1"

if ! perl -0777 -ne 'exit 1 unless /^.+\n\n.+/s' "$COMMIT_MSG_FILE"; then
    echo "⛔ git-hook: Commit message MUST include a body explaining the 'WHY' (intent)." >&2
    echo "" >&2
    echo "Example:" >&2
    echo "  feat(zsh): add fzf history search" >&2
    echo "" >&2
    echo "  Speeds up command recall during pairing sessions." >&2
    echo "  Without this, reverse-search only matches prefix, not substrings." >&2
    exit 1
fi

# Body quality: minimum 10 meaningful characters (after stripping trailers)
BODY=$(sed -n '/^$/,$ p' "$COMMIT_MSG_FILE" | sed '1d' | grep -v '^Co-authored-by:' | grep -v '^Signed-off-by:' | tr -d '[:space:]')
if [[ ${#BODY} -lt 10 ]]; then
    echo "⛔ git-hook: Commit body is too short (${#BODY} chars, min 10)." >&2
    echo "   Write a meaningful explanation of WHY this change is needed." >&2
    exit 1
fi

exit 0
