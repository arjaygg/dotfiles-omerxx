#!/usr/bin/env bash
# PreToolUse (run_command): pr-title-conventional-guard.sh — Antigravity CLI port
# Enforce conventional PR titles for direct `gh pr` commands.
# Ported from ~/.dotfiles/.claude/hooks/pr-title-conventional-guard.sh (Claude Code).
# See git-commit-guard.sh (this dir) for schema-difference notes.

set -euo pipefail
trap 'echo "{\"allow_tool\": true}"; exit 0' ERR

INPUT="$(cat 2>/dev/null || echo "{}")"

if command -v jq >/dev/null 2>&1; then
    CMD="$(echo "$INPUT" | jq -r '.toolCall.args.CommandLine // ""' 2>/dev/null || echo "")"
else
    CMD="$(echo "$INPUT" | grep -oE '"CommandLine"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | cut -d'"' -f4)"
fi

allow() { echo '{"allow_tool": true}'; exit 0; }
deny() {
    local reason="$1"
    reason="${reason//\"/\\\"}"
    printf '{"allow_tool": false, "deny_reason": "%s"}\n' "$reason"
    exit 0
}

if [[ ! "$CMD" =~ ^[[:space:]]*gh[[:space:]]+pr[[:space:]]+(create|edit)([[:space:]]|$) ]]; then
    allow
fi

ACTION="${BASH_REMATCH[1]}"
TITLE=""

if [[ "$CMD" =~ (--title|-t)[[:space:]]+\"([^\"]+)\" ]]; then
    TITLE="${BASH_REMATCH[2]}"
elif [[ "$CMD" =~ (--title|-t)[[:space:]]+\'([^\']+)\' ]]; then
    TITLE="${BASH_REMATCH[2]}"
elif [[ "$CMD" =~ (--title|-t)[[:space:]]+([^[:space:]]+) ]]; then
    TITLE="${BASH_REMATCH[2]}"
fi

if [[ "$ACTION" == "create" && -z "$TITLE" ]]; then
    deny 'gh pr create requires --title in Conventional Commits format. Use: gh pr create --title "feat: <summary>" ...'
fi

if [[ -n "$TITLE" ]]; then
    VALIDATOR="$HOME/.dotfiles/.claude/scripts/pr-stack/lib/pr-title.sh"
    if [[ -f "$VALIDATOR" ]]; then
        # shellcheck disable=SC1090
        source "$VALIDATOR"
        if ! is_conventional_pr_title "$TITLE"; then
            deny "PR title is not Conventional Commits compliant: \\\"${TITLE}\\\". Expected: <type>(optional-scope): <summary>. Allowed types: feat, fix, perf, refactor, test, ci, chore, docs, style, revert"
        fi
    fi
fi

allow
