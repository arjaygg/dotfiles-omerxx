#!/usr/bin/env bash

# pr-title.sh - Conventional Commit style validation for PR titles

# Allowed types must match repository PR title lint configuration.
readonly PR_TITLE_ALLOWED_TYPES='feat|fix|perf|refactor|test|ci|chore|docs|style|revert'

_pr_title_error() {
    local msg="$1"
    if type print_error >/dev/null 2>&1; then
        print_error "$msg"
    else
        echo "ERROR: $msg" >&2
    fi
}

_pr_title_info() {
    local msg="$1"
    if type print_info >/dev/null 2>&1; then
        print_info "$msg"
    else
        echo "INFO: $msg"
    fi
}

is_conventional_pr_title() {
    local title="${1:-}"
    [[ -n "$title" ]] || return 1
    [[ "$title" =~ ^(${PR_TITLE_ALLOWED_TYPES})(\([a-z0-9._/-]+\))?(!)?:[[:space:]].+$ ]]
}

suggest_pr_title_from_branch() {
    local branch="${1:-}"
    local normalized="${branch#refs/heads/}"
    local prefix="${normalized%%/*}"
    local rest="$normalized"
    local type="chore"

    if [[ "$normalized" == */* ]]; then
        rest="${normalized#*/}"
    fi

    case "$prefix" in
        feat|feature) type="feat" ;;
        fix|bugfix|hotfix) type="fix" ;;
        perf) type="perf" ;;
        refactor) type="refactor" ;;
        test|tests) type="test" ;;
        ci) type="ci" ;;
        chore) type="chore" ;;
        docs|doc) type="docs" ;;
        style) type="style" ;;
        revert) type="revert" ;;
        release) type="chore" ;;
    esac

    local summary
    summary="$(echo "$rest" \
        | tr '[:upper:]' '[:lower:]' \
        | sed -E 's@[_/.-]+@ @g; s@[^a-z0-9 ]+@@g; s@ +@ @g; s@^ @@; s@ $@@')"

    if [[ -z "$summary" ]]; then
        summary="update"
    fi

    echo "${type}: ${summary}"
}

validate_conventional_pr_title_or_die() {
    local title="${1:-}"

    if is_conventional_pr_title "$title"; then
        return 0
    fi

    _pr_title_error "Invalid PR title: \"$title\""
    _pr_title_info "Title must match Conventional Commits:"
    _pr_title_info "  <type>(optional-scope): <summary>"
    _pr_title_info "Allowed types: feat, fix, perf, refactor, test, ci, chore, docs, style, revert"
    _pr_title_info "Example: feat(worker): add auto-retry for transient DB errors"
    return 1
}

export -f is_conventional_pr_title 2>/dev/null || true
export -f suggest_pr_title_from_branch 2>/dev/null || true
export -f validate_conventional_pr_title_or_die 2>/dev/null || true
