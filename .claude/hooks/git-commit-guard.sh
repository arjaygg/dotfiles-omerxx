#!/usr/bin/env bash
# PreToolUse: git-commit-guard.sh
# Global guard for git commit message format and squash merge advisory.
# Applies to all repos on this machine. Project hooks handle repo-specific policies.

set -euo pipefail
trap 'exit 0' ERR

INPUT="$(cat 2>/dev/null || echo "{}")"
TOOL_NAME="$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")"
CMD="$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")"

[[ "$TOOL_NAME" == "Bash" ]] || exit 0

# =============================================================
# POLICY A: Conventional Commits format on git commit -m
# =============================================================
if echo "$CMD" | grep -qE 'git commit.*-m'; then
    commit_msg=$(echo "$CMD" | sed -n 's/.*-m[[:space:]]*"\([^"]*\)".*/\1/p')

    if [[ -n "$commit_msg" ]]; then
        subject=$(echo "$commit_msg" | head -1)

        # Skip auto-generated merge/revert commits
        if echo "$subject" | grep -qE '^(Merge|Revert) '; then
            exit 0
        fi

        # Use shared pr-title.sh lib (canonical types); extend with wip/build for commits.
        VALIDATOR="$HOME/.dotfiles/.claude/scripts/pr-stack/lib/pr-title.sh"
        valid=false
        if [[ -f "$VALIDATOR" ]]; then
            # shellcheck disable=SC1090
            source "$VALIDATOR"
            is_conventional_pr_title "$subject" && valid=true
            # wip and build are valid commit types but not PR title types
            echo "$subject" | grep -qE '^(wip|build)(\([a-z0-9._/-]+\))?(!)?:[[:space:]].+$' && valid=true
        else
            echo "$subject" | grep -qE \
                '^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert|wip)(\([a-z0-9._/-]+\))?(!)?:[[:space:]].+$' \
                && valid=true
        fi

        if [[ "$valid" != "true" ]]; then
            echo "BLOCKED: Commit message does not follow Conventional Commits format." >&2
            echo "" >&2
            echo "  Your message: $subject" >&2
            echo "  Expected:     <type>(<optional-scope>): <summary>" >&2
            echo "" >&2
            echo "  Allowed types: feat, fix, docs, style, refactor, test, chore, perf, ci, build, revert, wip" >&2
            echo "" >&2
            echo "  Examples:" >&2
            echo "    feat(auth): add JWT refresh token support" >&2
            echo "    fix(worker): resolve bulk insert timeout" >&2
            echo "    wip(migration): experimenting with sequence algorithm" >&2
            exit 1
        fi

        # Co-authored-by advisory for AI commits (warning only, non-blocking)
        if ! echo "$commit_msg" | grep -q "Co-authored-by:"; then
            echo "[ADVISORY] AI-generated commits should include:" >&2
            echo "  Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>" >&2
        fi
    fi
fi

# =============================================================
# POLICY B: Squash merge advisory for large PRs
# =============================================================
if echo "$CMD" | grep -qE '(gh pr merge.*--squash|az repos pr update.*--squash)'; then
    pr_number=$(echo "$CMD" | grep -oE '(merge|update) [0-9]+' | grep -oE '[0-9]+$' | head -1)

    if [[ -n "$pr_number" ]] && command -v gh &>/dev/null; then
        files_changed=$(gh pr view "$pr_number" --json files --jq '.files | length' 2>/dev/null || echo "")

        if [[ -n "$files_changed" && "$files_changed" -gt 5 ]]; then
            echo "[ADVISORY] Squash merging PR #$pr_number with $files_changed files changed." >&2
            echo "  Consider regular merge to preserve commit history for git bisect:" >&2
            echo "    gh pr merge $pr_number --merge" >&2
        fi
    fi
fi

exit 0
