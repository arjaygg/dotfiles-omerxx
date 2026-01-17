#!/usr/bin/env bash

# merge-stack.sh - Complete a PR merge and update all dependent branches
# Usage: ./merge-stack.sh <pr-id>

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Azure DevOps Configuration
# NOTE: Prefer dev.azure.com format (current Azure DevOps standard)
ORGANIZATION="https://dev.azure.com/bofaz"
PROJECT="Axos-Universal-Core"

print_usage() {
    echo -e "${BLUE}Usage:${NC}"
    echo "  ./merge-stack.sh <pr-id>"
    echo ""
    echo -e "${BLUE}Description:${NC}"
    echo "  Completes a PR merge in Azure DevOps and automatically updates"
    echo "  all dependent branches in the stack."
    echo ""
    echo -e "${BLUE}Examples:${NC}"
    echo "  ./merge-stack.sh 12345"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

print_success() {
    echo -e "${GREEN}SUCCESS:${NC} $1"
}

print_info() {
    echo -e "${BLUE}INFO:${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

# Validate arguments
if [ $# -lt 1 ]; then
    print_error "Missing required argument: pr-id"
    print_usage
    exit 1
fi

PR_ID=$1

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not in a git repository"
    exit 1
fi

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    print_error "Azure CLI is not installed"
    print_info "Install it from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

print_info "Fetching PR #$PR_ID information..."

# Get PR details
PR_JSON=$(az repos pr show \
    --id "$PR_ID" \
    --organization "$ORGANIZATION" \
    --output json 2>&1)

if [ $? -ne 0 ]; then
    print_error "Failed to fetch PR #$PR_ID"
    echo "$PR_JSON"
    exit 1
fi

# Extract PR information
SOURCE_BRANCH=$(echo "$PR_JSON" | jq -r '.sourceRefName' | sed 's|refs/heads/||')
TARGET_BRANCH=$(echo "$PR_JSON" | jq -r '.targetRefName' | sed 's|refs/heads/||')
PR_STATUS=$(echo "$PR_JSON" | jq -r '.status')
PR_TITLE=$(echo "$PR_JSON" | jq -r '.title')

print_info "PR Details:"
echo "  Title: $PR_TITLE"
echo "  Source: $SOURCE_BRANCH"
echo "  Target: $TARGET_BRANCH"
echo "  Status: $PR_STATUS"
echo ""

# Check if PR is already completed
if [ "$PR_STATUS" == "completed" ]; then
    print_warning "PR #$PR_ID is already merged"
    print_info "Proceeding with stack update..."
else
    # Check if PR can be completed
    MERGE_STATUS=$(echo "$PR_JSON" | jq -r '.mergeStatus')

    if [ "$MERGE_STATUS" != "succeeded" ]; then
        print_error "PR cannot be merged. Merge status: $MERGE_STATUS"
        print_info "Please resolve any conflicts or build failures first"
        exit 1
    fi

    # Confirm merge
    echo -e "${YELLOW}Ready to merge PR #$PR_ID${NC}"
    read -p "Proceed with merge? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Merge cancelled"
        exit 0
    fi

    # Complete the PR
    print_info "Completing PR #$PR_ID..."

    COMPLETE_RESULT=$(az repos pr update \
        --id "$PR_ID" \
        --organization "$ORGANIZATION" \
        --status completed \
        --output json 2>&1)

    if [ $? -eq 0 ]; then
        print_success "PR #$PR_ID merged successfully!"
    else
        print_error "Failed to merge PR #$PR_ID"
        echo "$COMPLETE_RESULT"
        exit 1
    fi
fi

# Update local repository
print_info "Updating local repository..."
git fetch origin

# Checkout and update target branch
if git rev-parse --verify "$TARGET_BRANCH" > /dev/null 2>&1; then
    print_info "Updating local $TARGET_BRANCH..."
    git checkout "$TARGET_BRANCH"
    git pull origin "$TARGET_BRANCH"
else
    print_warning "Local $TARGET_BRANCH does not exist"
    print_info "Creating $TARGET_BRANCH from origin..."
    git checkout -b "$TARGET_BRANCH" "origin/$TARGET_BRANCH"
fi

# Delete the merged source branch (optional)
echo ""
read -p "Delete merged branch $SOURCE_BRANCH locally? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if git rev-parse --verify "$SOURCE_BRANCH" > /dev/null 2>&1; then
        git branch -d "$SOURCE_BRANCH" 2>/dev/null || \
            git branch -D "$SOURCE_BRANCH"
        print_success "Local branch $SOURCE_BRANCH deleted"
    fi
fi

read -p "Delete merged branch $SOURCE_BRANCH remotely? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git push origin --delete "$SOURCE_BRANCH" 2>/dev/null || \
        print_warning "Could not delete remote branch (may already be deleted)"
fi

# Update dependent branches
echo ""
print_info "Updating dependent branches in the stack..."

./scripts/pr-stack/update-stack.sh "$SOURCE_BRANCH"

print_success "Stack merge complete!"
echo ""
print_info "Next steps:"
echo "  1. Review updated branches: ./scripts/pr-stack/list-stack.sh"
echo "  2. Verify CI builds for dependent PRs"
echo "  3. Continue reviewing dependent PRs"
