#!/usr/bin/env bash

# create-stack.sh - Create a new branch in the PR stack
# Usage: ./create-stack.sh <new-branch-name> [base-branch] [commit-message]

set -e

# Load libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/validation.sh"
source "$SCRIPT_DIR/lib/charcoal-compat.sh"

# Functions
print_usage() {
    echo -e "${BLUE}Usage:${NC}"
    echo "  ./create-stack.sh <new-branch-name> [base-branch] [commit-message]"
    echo ""
    echo -e "${BLUE}Arguments:${NC}"
    echo "  new-branch-name    Name of the new branch to create (required)"
    echo "  base-branch        Branch to base the new branch on (default: main)"
    echo "  commit-message     Initial commit message (optional)"
    echo ""
    echo -e "${BLUE}Examples:${NC}"
    echo "  ./create-stack.sh feature/new-api main"
    echo "  ./create-stack.sh feature/ui feature/api"
    echo "  ./create-stack.sh feature/tests feature/ui 'Initial test setup'"
}

# Validate arguments
if [ $# -lt 1 ]; then
    print_error "Missing required argument: new-branch-name"
    print_usage
    exit 1
fi

# Determine default branch
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")

NEW_BRANCH=$1
BASE_BRANCH=${2:-$DEFAULT_BRANCH}
COMMIT_MESSAGE=$3

# Validate prerequisites using library functions
validate_stack_create_prerequisites "$NEW_BRANCH" "$BASE_BRANCH" || exit 1

# Get repository root (already at root from validation)
REPO_ROOT=$(get_repo_root)

print_info "Creating new branch: $NEW_BRANCH"
print_info "Based on: $BASE_BRANCH"

# Fetch latest changes
print_info "Fetching latest changes..."
git fetch origin

# Check if base branch is up to date with remote
BASE_BEHIND=$(git rev-list --count "$BASE_BRANCH..origin/$BASE_BRANCH" 2>/dev/null || echo "0")
if [ "$BASE_BEHIND" -gt 0 ]; then
    print_warning "Local $BASE_BRANCH is $BASE_BEHIND commit(s) behind origin/$BASE_BRANCH"
    read -p "Update $BASE_BRANCH from remote? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git checkout "$BASE_BRANCH"
        git pull origin "$BASE_BRANCH"
    fi
fi

# Create the new branch
print_info "Creating branch $NEW_BRANCH from $BASE_BRANCH..."
git checkout -b "$NEW_BRANCH" "$BASE_BRANCH"

print_success "Branch $NEW_BRANCH created successfully"

# If commit message provided, create initial commit
if [ -n "$COMMIT_MESSAGE" ]; then
    print_info "Creating initial commit..."

    # Create a simple .gitkeep or README
    mkdir -p ".branch-info"
    cat > ".branch-info/$NEW_BRANCH.md" << EOF
# Branch: $NEW_BRANCH

## Base Branch
$BASE_BRANCH

## Created
$(date)

## Purpose
$COMMIT_MESSAGE

## Dependencies
- Based on: $BASE_BRANCH
EOF

    git add ".branch-info/$NEW_BRANCH.md"
    git commit -m "$COMMIT_MESSAGE"

    print_success "Initial commit created"
fi

# Show current status
echo ""
print_info "Current branch: $(git branch --show-current)"
print_info "Files changed from $BASE_BRANCH:"
git diff --stat "$BASE_BRANCH"

# Show next steps
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "  1. Make your changes and commit them"
echo "  2. Push branch: git push -u origin $NEW_BRANCH"
echo "  3. Create PR: ./scripts/pr-stack/create-pr.sh $NEW_BRANCH $BASE_BRANCH \"Title\""
echo ""
echo -e "${BLUE}Optional:${NC} Create a worktree for parallel development:"
echo "  git worktree add .trees/${NEW_BRANCH##*/} -b $NEW_BRANCH"
echo ""

# Store stack information
STACK_INFO_FILE="$REPO_ROOT/.git/pr-stack-info"
echo "$NEW_BRANCH:$BASE_BRANCH:$(date +%s)" >> "$STACK_INFO_FILE"

# Sync to Charcoal if available
if charcoal_initialized; then
    print_info "Syncing branch to Charcoal..."
    gt branch track "$NEW_BRANCH" --parent "$BASE_BRANCH" 2>/dev/null || true
fi

print_success "Stack updated. Run './scripts/stack status' to see your PR stack"
