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
# Extract commit message from either form:
#   git commit -m "single line"
#   git commit -m "$(cat <<'EOF' ... EOF)"   (heredoc — the mandated form
#   for multi-line/co-authored commits per this repo's git instructions;
#   the old single-line sed pattern silently matched nothing for this form)
# =============================================================
extract_commit_message() {
    local cmd="$1"
    local delim
    delim=$(printf '%s\n' "$cmd" | grep -oE "<<-?[\"']?[A-Za-z_][A-Za-z0-9_]*[\"']?" | head -1 | sed -E "s/^<<-?[\"']?//; s/[\"']?\$//")
    if [[ -n "$delim" ]]; then
        printf '%s\n' "$cmd" | awk -v delim="$delim" '
            found && $0 == delim { exit }
            found { print; next }
            index($0, "<<") > 0 && index($0, delim) > 0 { found=1 }
        '
        return 0
    fi
    printf '%s\n' "$cmd" | sed -n 's/.*-m[[:space:]]*"\([^"]*\)".*/\1/p'
}

# =============================================================
# POLICY A: Conventional Commits format on git commit -m
# =============================================================
if echo "$CMD" | grep -qE 'git commit.*-m'; then
    commit_msg=$(extract_commit_message "$CMD")

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
# POLICY A2: commitlint body-max-line-length (default rule: 100 chars)
# Catches the recurring CI failure class where a wrapped body line
# still exceeds commitlint's limit, before the commit is even made.
# =============================================================
if [[ -n "${commit_msg:-}" ]]; then
    body_violations=""
    line_no=0
    while IFS= read -r line; do
        line_no=$((line_no + 1))
        # skip subject line and blank lines
        [[ $line_no -eq 1 || -z "$line" ]] && continue
        # skip trailer/footer lines — commitlint scopes body-max-line-length
        # to the body, not footer trailers like Co-authored-by/Signed-off-by
        echo "$line" | grep -qiE '^(co-authored-by|signed-off-by|reviewed-by|fixes|closes|refs):' && continue
        line_len=${#line}
        if [[ $line_len -gt 100 ]]; then
            body_violations+="  Line $line_no ($line_len chars): ${line:0:70}...
"
        fi
    done <<< "$commit_msg"

    if [[ -n "$body_violations" ]]; then
        echo "BLOCKED: Commit message body exceeds commitlint's body-max-line-length (100 chars)." >&2
        echo "" >&2
        printf '%s' "$body_violations" >&2
        echo "" >&2
        echo "  Wrap body lines at ~100 chars. Trailer lines (Co-authored-by, Signed-off-by, etc.) are exempt." >&2
        exit 1
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
