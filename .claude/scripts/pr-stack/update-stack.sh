#!/usr/bin/env bash

# update-stack.sh - Update stack after a branch is merged
# Usage: ./update-stack.sh [merged-branch]
#
# This script updates the entire stack after a PR is merged by:
# 1. Using Charcoal to restack all branches
# 2. Syncing all worktrees
# 3. Updating metadata to reflect the merge

set -e

# Load libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/validation.sh"
source "$SCRIPT_DIR/lib/charcoal-compat.sh"

# Only source worktree-charcoal if file exists
if [ -f "$SCRIPT_DIR/lib/worktree-charcoal.sh" ]; then
    source "$SCRIPT_DIR/lib/worktree-charcoal.sh"
fi

print_usage() {
    echo -e "${BLUE}Usage:${NC}"
    echo "  ./update-stack.sh [merged-branch]"
    echo ""
    echo -e "${BLUE}Description:${NC}"
    echo "  Updates all branches that depend on the merged branch using Charcoal."
    echo "  Rebases dependent branches and syncs all worktrees."
    echo ""
    echo -e "${BLUE}Requirements:${NC}"
    echo "  - Charcoal CLI (gt) must be installed"
    echo "  - Install: brew install danerwilliams/tap/charcoal"
    echo ""
    echo -e "${BLUE}Examples:${NC}"
    echo "  ./update-stack.sh feature/base-implementation"
    echo "  ./update-stack.sh  # Interactive mode"
}

# Check for help flag
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    print_usage
    exit 0
fi

# Validate git repository
validate_git_repository || exit 1

# REQUIRE Charcoal - no fallback
if ! charcoal_available; then
    print_error "Charcoal CLI is required but not installed"
    echo ""
    echo -e "${YELLOW}Charcoal provides:${NC}"
    echo "  • Automatic stack rebasing"
    echo "  • Dependency resolution"
    echo "  • Conflict handling"
    echo "  • Branch relationship tracking"
    echo ""
    echo -e "${BLUE}Install Charcoal:${NC}"
    echo "  brew install danerwilliams/tap/charcoal"
    echo ""
    echo -e "${BLUE}Then initialize in this repo:${NC}"
    echo "  ~/.claude/scripts/stack init"
    exit 1
fi

if ! charcoal_initialized; then
    print_error "Charcoal is not initialized in this repository"
    echo ""
    echo -e "${BLUE}Initialize Charcoal:${NC}"
    echo "  ~/.claude/scripts/stack init"
    exit 1
fi

# Robust Repo Root detection (handles worktrees correctly)
REPO_ROOT=$(git rev-parse --show-toplevel)

# Worktree-safe path resolution
STACK_INFO_FILE="$(git rev-parse --git-path pr-stack-info)"
if [[ "$STACK_INFO_FILE" != /* ]]; then
    GIT_DIR=$(git rev-parse --git-dir)
    STACK_INFO_FILE="$GIT_DIR/$STACK_INFO_FILE"
fi

# Get merged branch
MERGED_BRANCH=$1

if [ -z "$MERGED_BRANCH" ]; then
    # Interactive mode - show branches and let user select
    echo -e "${BLUE}Select a merged branch to update dependents:${NC}"
    echo ""

    if [ ! -f "$STACK_INFO_FILE" ]; then
        print_error "No stack information found"
        print_info "Create stacked branches first: ~/.claude/scripts/stack create"
        exit 1
    fi

    # Read branches from stack file
    i=1
    declare -a BRANCHES
    while IFS=: read -r branch target timestamp; do
        BRANCHES[$i]="$branch:$target"
        echo "  $i) $branch (target: $target)"
        i=$((i + 1))
    done < "$STACK_INFO_FILE"

    echo ""
    read -p "Enter number (or branch name): " SELECTION

    # Check if selection is a number
    if [[ "$SELECTION" =~ ^[0-9]+$ ]]; then
        MERGED_BRANCH=$(echo "${BRANCHES[$SELECTION]}" | cut -d: -f1)
    else
        MERGED_BRANCH=$SELECTION
    fi
fi

if [ -z "$MERGED_BRANCH" ]; then
    print_error "No branch selected"
    exit 1
fi

print_info "Updating stack after merge of: $MERGED_BRANCH"
echo ""

# Find the target branch for the merged branch (for cleanup)
TARGET_BRANCH=""
if [ -f "$STACK_INFO_FILE" ]; then
    while IFS=: read -r branch target timestamp; do
        if [ "$branch" == "$MERGED_BRANCH" ]; then
            TARGET_BRANCH=$target
            break
        fi
    done < "$STACK_INFO_FILE"
fi

# Use Charcoal to restack everything
print_info "Using Charcoal to restack dependent branches..."
echo ""

# Navigate to main repo if in worktree
MAIN_REPO=$(get_main_repo_path)
CURRENT_DIR=$(pwd)

cd "$MAIN_REPO"

# Run Charcoal restack
if gt restack; then
    print_success "Stack rebased successfully"
    echo ""

    # Sync worktrees if any exist
    print_info "Syncing worktrees..."
    sync_all_worktrees
    echo ""

    # Sync metadata
    print_info "Updating metadata..."
    sync_charcoal_to_native

    # Clean up merged branch from stack info
    if [ -n "$TARGET_BRANCH" ] && [ -f "$STACK_INFO_FILE" ]; then
        print_info "Cleaning up stack information for merged branch..."
        grep -v "^${MERGED_BRANCH}:" "$STACK_INFO_FILE" > "${STACK_INFO_FILE}.tmp" && mv "${STACK_INFO_FILE}.tmp" "$STACK_INFO_FILE"

        # Update any branches that targeted the merged branch to now target its parent
        sed -i.bak "s/:${MERGED_BRANCH}:/:${TARGET_BRANCH}:/" "$STACK_INFO_FILE"
        rm -f "${STACK_INFO_FILE}.bak"
    fi

    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    print_success "Stack update complete!"
    echo ""
    print_info "Next steps:"
    echo "  • Review updated branches: ~/.claude/scripts/stack status"
    echo "  • Push force if needed: git push --force-with-lease"
    echo "  • Delete merged branch: git branch -d $MERGED_BRANCH"

else
    print_error "Restack failed"
    echo ""
    print_info "Common causes:"
    echo "  • Merge conflicts in dependent branches"
    echo "  • Uncommitted changes in worktrees"
    echo ""
    print_info "To resolve:"
    echo "  1. Check conflict messages above"
    echo "  2. Resolve conflicts: git add <files> && git rebase --continue"
    echo "  3. Run this script again: ~/.claude/scripts/stack update $MERGED_BRANCH"
    exit 1
fi

# Return to original directory
cd "$CURRENT_DIR"
