#!/usr/bin/env bash

# merge-stack.sh - Merge a GitHub PR and update all dependent branches
# Usage: ./merge-stack.sh <pr-number-or-branch>
#
# Accepts either a PR number (e.g. 42) or a branch name (e.g. feature/my-feature).
# Merges via squash + delete-branch, then calls update-stack.sh to rebase dependents.

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
    PR_NUM=$(GH_TOKEN=$(gh_token_for_remote) gh pr view "$ARG" --json number -q '.number' 2>/dev/null || true)
    if [ -z "$PR_NUM" ]; then
        print_error "No open PR found for branch: $ARG"; exit 1
    fi
fi

print_info "Fetching PR #$PR_NUM details..."
PR_JSON=$(GH_TOKEN=$(gh_token_for_remote) gh pr view "$PR_NUM" \
    --json title,headRefName,baseRefName,state 2>&1)
if [ $? -ne 0 ]; then
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
    MERGE_OUTPUT=$(GH_TOKEN=$(gh_token_for_remote) \
        gh pr merge "$PR_NUM" --squash --delete-branch 2>&1)
    if [ $? -eq 0 ]; then
        print_success "PR #$PR_NUM merged!"
    else
        print_error "Merge failed:"
        echo "$MERGE_OUTPUT"
        exit 1
    fi
fi

echo ""

# Update stack: rebase dependent branches, sync PR base targets on GitHub
"$SCRIPT_DIR/update-stack.sh" "$SOURCE_BRANCH"

print_success "Stack merge complete!"
echo ""
print_info "Next steps:"
echo "  - Review updated PRs: stack status"
echo "  - Verify CI for dependent branches"
