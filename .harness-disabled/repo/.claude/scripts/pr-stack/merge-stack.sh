#!/usr/bin/env bash

# merge-stack.sh - Merge a GitHub PR and update all dependent branches
# Usage: ./merge-stack.sh <pr-number-or-branch>
#
# Accepts either a PR number (e.g. 42) or a branch name (e.g. feature/my-feature).
# Merges via squash + delete-branch and rebases all dependent branches locally.
# Updates dependent PR base branches on GitHub and syncs worktrees.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/validation.sh"
source "$SCRIPT_DIR/lib/charcoal-compat.sh"
source "$SCRIPT_DIR/lib/gh-account.sh"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
print_error()   { echo -e "${RED}ERROR:${NC} $1"; }
print_success() { echo -e "${GREEN}SUCCESS:${NC} $1"; }
print_info()    { echo -e "${BLUE}INFO:${NC} $1"; }
print_warning() { echo -e "${YELLOW}WARNING:${NC} $1"; }

print_usage() {
    echo -e "${BLUE}Usage:${NC}"
    echo "  ./merge-stack.sh <pr-number-or-branch>"
    echo ""
    echo -e "${BLUE}Description:${NC}"
    echo "  Merges a GitHub PR (squash + delete branch) and rebases all dependent"
    echo "  branches in the Charcoal stack. Updates GitHub PR base targets automatically."
    echo ""
    echo -e "${BLUE}Examples:${NC}"
    echo "  ./merge-stack.sh 12345"
    echo "  ./merge-stack.sh feature/my-feature"
    echo "  ./merge-stack.sh  # auto-detect from current branch"
}

# Update all dependent branches after a PR merge
# Rebases locally via Charcoal and syncs GitHub PR base branches
_update_dependent_branches() {
    local merged_branch="$1"

    print_info "Rebasing dependent branches via Charcoal..."

    # Rebase all branches that depend on the merged branch
    local default_branch
    default_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")

    # Use Charcoal to rebase the stack
    if charcoal_available && charcoal_initialized; then
        if charcoal_rebase_stack "$merged_branch" 2>/dev/null; then
            print_success "Stack rebased via Charcoal"
        else
            print_warning "Charcoal rebase encountered issues (non-fatal)"
        fi
    else
        print_warning "Charcoal not available — skipping automatic rebase"
    fi

    # Sync GitHub PR base branches to match Charcoal stack relationships
    print_info "Syncing GitHub PR base branches with stack..."
    _sync_github_pr_bases "$default_branch"
}

# Sync all GitHub PR base branches to match Charcoal parent relationships
_sync_github_pr_bases() {
    local default_branch="$1"
    local updated=0 skipped=0

    while IFS= read -r branch; do
        [ "$branch" = "$default_branch" ] && continue
        [ -z "$branch" ] && continue

        # Get Charcoal parent for this branch
        local parent
        parent=$(charcoal_get_parent "$branch" 2>/dev/null || true)
        [ -z "$parent" ] && { skipped=$((skipped + 1)); continue; }

        # Get the PR number for this branch
        local pr_num
        if ! pr_num=$(gh pr view "$branch" --json number -q '.number' 2>/dev/null); then
            skipped=$((skipped + 1))
            continue
        fi
        [ -z "$pr_num" ] && { skipped=$((skipped + 1)); continue; }

        # Update PR base if different from parent
        if gh pr edit "$pr_num" --base "$parent" 2>/dev/null; then
            print_info "  PR #$pr_num ($branch) → base: $parent"
            updated=$((updated + 1))
        else
            print_warning "  Could not update PR base for $branch (PR #$pr_num)"
            skipped=$((skipped + 1))
        fi
    done < <(git branch --format='%(refname:short)')

    print_info "PR base sync: $updated updated, $skipped skipped/no PR"
}

if [ $# -lt 1 ]; then
    # Default: current branch
    ARG=$(git branch --show-current 2>/dev/null || true)
    if [ -z "$ARG" ]; then
        print_error "No branch argument provided and not on a branch"
        print_usage
        exit 1
    fi
    print_info "No argument given — using current branch: $ARG"
else
    ARG=$1
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    print_error "Not in a git repository"; exit 1
fi

if ! command -v gh &>/dev/null; then
    print_error "gh CLI is not installed. Install: https://cli.github.com"; exit 1
fi

gh_setup_git

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

# Resolve PR number — accept either a number or branch name
if [[ "$ARG" =~ ^[0-9]+$ ]]; then
    PR_NUM="$ARG"
else
    print_info "Looking up PR for branch: $ARG"
    PR_NUM=$(gh pr view "$ARG" --json number -q '.number' 2>/dev/null || true)
    if [ -z "$PR_NUM" ]; then
        print_error "No open PR found for branch: $ARG"; exit 1
    fi
fi

print_info "Fetching PR #$PR_NUM details..."
if ! PR_JSON=$(gh pr view "$PR_NUM" \
    --json title,headRefName,baseRefName,state 2>&1); then
    print_error "Failed to fetch PR #$PR_NUM"
    echo "$PR_JSON"
    exit 1
fi

SOURCE_BRANCH=$(echo "$PR_JSON" | jq -r '.headRefName')
TARGET_BRANCH=$(echo "$PR_JSON" | jq -r '.baseRefName')
PR_STATE=$(echo "$PR_JSON" | jq -r '.state')
PR_TITLE=$(echo "$PR_JSON" | jq -r '.title')

echo ""
print_info "PR Details:"
echo "  Title:  $PR_TITLE"
echo "  Source: $SOURCE_BRANCH"
echo "  Target: $TARGET_BRANCH"
echo "  State:  $PR_STATE"
echo ""

if [ "$PR_STATE" = "MERGED" ]; then
    print_warning "PR #$PR_NUM is already merged. Updating stack..."
else
    if [ "$PR_STATE" != "OPEN" ]; then
        print_error "PR #$PR_NUM is $PR_STATE — cannot merge"; exit 1
    fi

    print_info "Merging PR #$PR_NUM (squash + delete branch)..."
    if MERGE_OUTPUT=$(gh pr merge "$PR_NUM" --squash --delete-branch 2>&1); then
        print_success "PR #$PR_NUM merged!"
    else
        print_error "Merge failed:"
        echo "$MERGE_OUTPUT"
        exit 1
    fi
fi

echo ""

# Update stack: rebase dependent branches and sync PR base targets
_update_dependent_branches "$SOURCE_BRANCH"

print_success "Stack merge complete!"
echo ""
print_info "Next steps:"
echo "  - Review updated PRs: stack status"
echo "  - Verify CI for dependent branches"
