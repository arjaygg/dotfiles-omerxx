#!/usr/bin/env bash
# PreToolUse (run_command): pre-push-remote-check.sh — Antigravity CLI port
# Warn-only remote/auth pre-flight for git push and PR creation commands. Never blocks.
# Ported from ~/.dotfiles/.claude/hooks/pre-push-remote-check.sh (Claude Code).
# All advisory output goes to stderr; stdout carries only the allow_tool decision JSON.

set -euo pipefail
trap 'echo "{\"allow_tool\": true}"; exit 0' ERR

INPUT="$(cat 2>/dev/null || echo "{}")"

if command -v jq >/dev/null 2>&1; then
    CMD="$(echo "$INPUT" | jq -r '.toolCall.args.CommandLine // ""' 2>/dev/null || echo "")"
else
    CMD="$(echo "$INPUT" | grep -oE '"CommandLine"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | cut -d'"' -f4)"
fi

if ! echo "$CMD" | grep -qE '(git push|gh pr create|gh pr edit|az repos pr)'; then
    echo '{"allow_tool": true}'
    exit 0
fi

REMOTE_INFO=$(git remote -v 2>/dev/null | awk '/^origin.*\(fetch\)/{print $2}' | sed -n '1p' || echo "unknown")
GH_USER=$(gh auth status --active 2>&1 | awk '/Logged in to/{print $(NF-1)}' | tr -d '"()' | sed -n '1p' || echo "unknown")

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

echo "Remote: origin -> ${REMOTE_HOST}/${REMOTE_REPO} | branch: ${CURRENT_BRANCH} | gh: ${GH_USER}" >&2

if [[ "$REMOTE_HOST" == "github.com" && "$GH_USER" != "arjaygg" && "$GH_USER" != "unknown" ]]; then
    echo "WARNING: gh CLI authenticated as '${GH_USER}' — expected 'arjaygg' for GitHub personal repos. Run: gh auth switch --user arjaygg" >&2
fi

if [[ "$REMOTE_HOST" == dev.azure.com* || "$REMOTE_HOST" == visualstudio.com* ]]; then
    if echo "$CMD" | grep -q 'gh pr'; then
        echo "WARNING: 'gh pr' targets GitHub but remote is ADO (${REMOTE_HOST}). Use: az repos pr create --organization https://bofaz.visualstudio.com" >&2
    fi
fi

echo '{"allow_tool": true}'
exit 0
