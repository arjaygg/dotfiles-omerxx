#!/usr/bin/env bash
# PreToolUse hook: warn-only remote/auth pre-flight for git push and PR creation commands
# Matcher: Bash
# Fires on: git push, gh pr create/edit, az repos pr

set -euo pipefail
trap 'exit 0' ERR

INPUT=$(cat)

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")

# Only act on push/PR commands
if ! echo "$CMD" | grep -qE '(git push|gh pr create|gh pr edit|az repos pr)'; then
    exit 0
fi

# Gather remote info non-interactively
REMOTE_INFO=$(git remote -v 2>/dev/null | awk '/^origin.*\(fetch\)/{print $2}' | sed -n '1p' || echo "unknown")
GH_USER=$(gh auth status --active 2>&1 | awk '/Logged in to/{print $(NF-1)}' | tr -d '"()' | sed -n '1p' || echo "unknown")

# Parse remote host and repo
REMOTE_HOST="unknown"
REMOTE_REPO="unknown"
if [[ "$REMOTE_INFO" =~ github\.com[:/](.+)\.git$ ]] || [[ "$REMOTE_INFO" =~ github\.com[:/](.+)$ ]]; then
    REMOTE_HOST="github.com"
    REMOTE_REPO="${BASH_REMATCH[1]}"
elif [[ "$REMOTE_INFO" =~ dev\.azure\.com/([^/]+)/([^/]+)/_git/(.+) ]]; then
    REMOTE_HOST="dev.azure.com/${BASH_REMATCH[1]}"
    REMOTE_REPO="${BASH_REMATCH[2]}/${BASH_REMATCH[3]}"
elif [[ "$REMOTE_INFO" =~ visualstudio\.com/([^/]+)/_git/(.+) ]]; then
    REMOTE_HOST="visualstudio.com"
    REMOTE_REPO="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
else
    REMOTE_HOST="$REMOTE_INFO"
fi

CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")

# Print one-line summary
echo "Remote: origin → ${REMOTE_HOST}/${REMOTE_REPO} | branch: ${CURRENT_BRANCH} | gh: ${GH_USER}"

# Warn if gh user is not arjaygg on GitHub repos
if [[ "$REMOTE_HOST" == "github.com" && "$GH_USER" != "arjaygg" && "$GH_USER" != "unknown" ]]; then
    echo "WARNING: gh CLI authenticated as '${GH_USER}' — expected 'arjaygg' for GitHub personal repos."
    echo "  Run: gh auth switch --user arjaygg"
fi

# Warn if ADO remote but command uses gh pr (GitHub-only tool)
if [[ "$REMOTE_HOST" == dev.azure.com* || "$REMOTE_HOST" == visualstudio.com* ]]; then
    if echo "$CMD" | grep -q 'gh pr'; then
        echo "WARNING: 'gh pr' targets GitHub but remote is ADO (${REMOTE_HOST})."
        echo "  Use: az repos pr create --organization https://bofaz.visualstudio.com"
    fi
fi

exit 0
