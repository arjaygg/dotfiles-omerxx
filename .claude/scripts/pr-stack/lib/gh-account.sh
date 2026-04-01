#!/usr/bin/env bash
# gh-account.sh — Silent, parallel-safe GitHub account resolution
#
# Replaces the _ensure_gh_account / gh auth switch pattern.
# Uses GH_TOKEN env var injection (process-scoped) instead of global auth state.
#
# Usage:
#   source "$SCRIPT_DIR/lib/gh-account.sh"
#   gh_setup_git
#   GH_TOKEN=$(gh_token_for_remote) gh pr create ...

# Prevent multiple sourcing
if [ -n "${_GH_ACCOUNT_SOURCED:-}" ]; then
    return 0
fi
_GH_ACCOUNT_SOURCED=1

# Map remote URL → gh account login name.
# Add more cases here to support additional accounts.
_gh_target_account() {
    local remote_url="${1:-$(git remote get-url origin 2>/dev/null || true)}"
    local org
    org=$(echo "$remote_url" | sed 's|.*github\.com[/:]||;s|/.*||')
    case "$org" in
        arjaygg) echo "arjaygg" ;;
        *)       echo "Arjay-Gallentes_axosEnt" ;;
    esac
}

# Return the stored OAuth token for the correct account.
# Uses `gh auth token --user` — reads from local keychain, no network call, no global state change.
# Falls back to the current active token if account-specific lookup fails.
#
# Usage: GH_TOKEN=$(gh_token_for_remote) gh pr create ...
gh_token_for_remote() {
    local remote_url="${1:-}"
    local account
    account="$(_gh_target_account "$remote_url")"
    gh auth token --user "$account" 2>/dev/null \
        || gh auth token 2>/dev/null \
        || true
}

# Ensure the gh credential helper is registered (one-time, idempotent, silent).
# Prevents git credential.helper= override from blocking push.
gh_setup_git() {
    gh auth setup-git 2>/dev/null || true
}
