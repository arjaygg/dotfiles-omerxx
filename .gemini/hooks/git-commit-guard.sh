#!/usr/bin/env bash
# PreToolUse (run_command): git-commit-guard.sh — Antigravity CLI port
# Global guard for git commit message format and squash merge advisory.
# Ported from ~/.dotfiles/.claude/hooks/git-commit-guard.sh (Claude Code).
# Schema differences vs the Claude version:
#   - input:  .toolCall.args.CommandLine   (was .tool_input.command)
#   - output: {"allow_tool": bool, "deny_reason": str} on stdout, always exit 0
#             (was: exit 1 + stderr message)
#   - advisories (non-blocking notes) go to stderr since only allow_tool/deny_reason
#     are documented as respected on stdout.

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

# =============================================================
# POLICY A: Conventional Commits format on git commit -m
# =============================================================
if echo "$CMD" | grep -qE 'git commit.*-m'; then
    commit_msg=$(echo "$CMD" | sed -n 's/.*-m[[:space:]]*"\([^"]*\)".*/\1/p')

    if [[ -n "$commit_msg" ]]; then
        subject=$(echo "$commit_msg" | head -1)

        if echo "$subject" | grep -qE '^(Merge|Revert) '; then
            allow
        fi

        VALIDATOR="$HOME/.dotfiles/.claude/scripts/pr-stack/lib/pr-title.sh"
        valid=false
        if [[ -f "$VALIDATOR" ]]; then
            # shellcheck disable=SC1090
            source "$VALIDATOR"
            is_conventional_pr_title "$subject" && valid=true
            echo "$subject" | grep -qE '^(wip|build)(\([a-z0-9._/-]+\))?(!)?:[[:space:]].+$' && valid=true
        else
            echo "$subject" | grep -qE \
                '^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert|wip)(\([a-z0-9._/-]+\))?(!)?:[[:space:]].+$' \
                && valid=true
        fi

        if [[ "$valid" != "true" ]]; then
            deny "Commit message does not follow Conventional Commits format. Expected: <type>(<optional-scope>): <summary>. Allowed types: feat, fix, docs, style, refactor, test, chore, perf, ci, build, revert, wip. Your message: ${subject}"
        fi

        if ! echo "$commit_msg" | grep -q "Co-authored-by:"; then
            echo "[ADVISORY] AI-generated commits should include: Co-authored-by: <agent> <noreply@...>" >&2
        fi
    fi
fi

# =============================================================
# POLICY B: Squash merge advisory for large PRs (advisory only, never blocks)
# =============================================================
if echo "$CMD" | grep -qE '(gh pr merge.*--squash|az repos pr update.*--squash)'; then
    pr_number=$(echo "$CMD" | grep -oE '(merge|update) [0-9]+' | grep -oE '[0-9]+$' | head -1)
    if [[ -n "$pr_number" ]] && command -v gh &>/dev/null; then
        files_changed=$(gh pr view "$pr_number" --json files --jq '.files | length' 2>/dev/null || echo "")
        if [[ -n "$files_changed" && "$files_changed" -gt 5 ]]; then
            echo "[ADVISORY] Squash merging PR #$pr_number with $files_changed files changed. Consider: gh pr merge $pr_number --merge" >&2
        fi
    fi
fi

allow
