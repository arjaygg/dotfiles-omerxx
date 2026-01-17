#!/usr/bin/env bash

# update-stack.sh - Update all dependent branches after a base branch is merged
# Usage: ./update-stack.sh [merged-branch]

set -e

# Load libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/validation.sh"
source "$SCRIPT_DIR/lib/charcoal-compat.sh"

print_usage() {
    echo -e "${BLUE}Usage:${NC}"
    echo "  ./update-stack.sh [merged-branch]"
    echo "  ./update-stack.sh --restack"
    echo ""
    echo -e "${BLUE}Description:${NC}"
    echo "  Updates all branches that depend on the merged branch by rebasing them"
    echo "  onto the branch's target (usually main)."
    echo ""
    echo -e "${BLUE}Options:${NC}"
    echo "  --restack    Use Charcoal's restack command (if available)"
    echo ""
    echo -e "${BLUE}Examples:${NC}"
    echo "  ./update-stack.sh feature/base-implementation"
    echo "  ./update-stack.sh  # Interactive mode - will prompt for branch"
    echo "  ./update-stack.sh --restack  # Use Charcoal restack"
}

# Check for --restack flag
if [ "$1" == "--restack" ]; then
    if charcoal_initialized; then
        print_info "Using Charcoal to restack all branches..."
        if gt restack; then
            print_success "Stack rebased successfully with Charcoal"
            sync_charcoal_to_native
        else
            print_error "Charcoal restack failed"
            exit 1
        fi
        exit 0
    else
        print_warning "Charcoal not available, falling back to standard update"
        print_info "Install Charcoal for easier restacking: brew install danerwilliams/tap/charcoal"
        shift  # Remove --restack flag
    fi
fi

# Validate prerequisites using library functions
validate_stack_update_prerequisites || exit 1

REPO_ROOT=$(get_repo_root)
# NOTE: Worktree-safe path resolution (in worktrees, .git is not a directory)
STACK_INFO_FILE="$(git rev-parse --git-path pr-stack-info)"

# Get merged branch
MERGED_BRANCH=$1

if [ -z "$MERGED_BRANCH" ]; then
    # Interactive mode - show branches and let user select
    echo -e "${BLUE}Select a merged branch to update dependents:${NC}"
    echo ""

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

print_info "Finding branches that depend on: $MERGED_BRANCH"

# Find the target branch for the merged branch
TARGET_BRANCH=""
while IFS=: read -r branch target timestamp; do
    if [ "$branch" == "$MERGED_BRANCH" ]; then
        TARGET_BRANCH=$target
        break
    fi
done < "$STACK_INFO_FILE"

if [ -z "$TARGET_BRANCH" ]; then
    print_error "Could not find target branch for $MERGED_BRANCH"
    exit 1
fi

print_info "Target branch: $TARGET_BRANCH"

# Find all branches that depend on MERGED_BRANCH
DEPENDENT_BRANCHES=()
while IFS=: read -r branch target timestamp; do
    if [ "$target" == "$MERGED_BRANCH" ]; then
        DEPENDENT_BRANCHES+=("$branch")
    fi
done < "$STACK_INFO_FILE"

if [ ${#DEPENDENT_BRANCHES[@]} -eq 0 ]; then
    print_warning "No dependent branches found"
    print_info "Stack update complete - no action needed"
    exit 0
fi

print_info "Found ${#DEPENDENT_BRANCHES[@]} dependent branch(es):"
for dep_branch in "${DEPENDENT_BRANCHES[@]}"; do
    echo "  - $dep_branch"
done

echo ""
read -p "Update all dependent branches? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Update cancelled"
    exit 0
fi

# Fetch latest changes
print_info "Fetching latest changes from remote..."
git fetch origin

# Update each dependent branch
UPDATED=0
FAILED=0

for dep_branch in "${DEPENDENT_BRANCHES[@]}"; do
    echo ""
    print_info "Updating $dep_branch..."

    # Check if branch exists locally
    if ! git rev-parse --verify "$dep_branch" > /dev/null 2>&1; then
        print_warning "Branch $dep_branch does not exist locally, skipping..."
        continue
    fi

    # Stash current changes if any
    CURRENT_BRANCH=$(git branch --show-current)
    STASHED=false
    if [ -n "$(git status --porcelain)" ]; then
        print_info "Stashing current changes..."
        git stash push -m "Auto-stash before updating $dep_branch"
        STASHED=true
    fi

    # Checkout the dependent branch
    git checkout "$dep_branch"

    # Rebase onto the target branch
    print_info "Rebasing $dep_branch onto $TARGET_BRANCH..."

    if git rebase "origin/$TARGET_BRANCH"; then
        print_success "Successfully rebased $dep_branch"

        # Push the updated branch
        print_info "Pushing updated branch..."
        if git push --force-with-lease; then
            print_success "$dep_branch updated and pushed"
            UPDATED=$((UPDATED + 1))

            # Update stack info - change target from MERGED_BRANCH to TARGET_BRANCH
            sed -i.bak "s/^${dep_branch}:${MERGED_BRANCH}:/${dep_branch}:${TARGET_BRANCH}:/" "$STACK_INFO_FILE"
            rm -f "${STACK_INFO_FILE}.bak"
        else
            print_error "Failed to push $dep_branch"
            print_info "You may need to resolve conflicts and push manually"
            FAILED=$((FAILED + 1))
        fi
    else
        print_error "Rebase failed for $dep_branch"
        print_warning "Resolve conflicts manually, then run:"
        print_warning "  git add <resolved-files>"
        print_warning "  git rebase --continue"
        print_warning "  git push --force-with-lease"
        FAILED=$((FAILED + 1))

        # Abort the rebase
        git rebase --abort 2>/dev/null || true
    fi

    # Return to original branch
    if [ "$CURRENT_BRANCH" != "$dep_branch" ]; then
        git checkout "$CURRENT_BRANCH" 2>/dev/null || git checkout main
    fi

    # Restore stashed changes
    if [ "$STASHED" = true ]; then
        print_info "Restoring stashed changes..."
        git stash pop
    fi
done

# Remove merged branch from stack info
print_info "Cleaning up stack information..."
grep -v "^${MERGED_BRANCH}:" "$STACK_INFO_FILE" > "${STACK_INFO_FILE}.tmp" && mv "${STACK_INFO_FILE}.tmp" "$STACK_INFO_FILE"

# Summary
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Update Summary:${NC}"
echo "  Successfully updated: $UPDATED branch(es)"
if [ $FAILED -gt 0 ]; then
    echo -e "  ${RED}Failed to update: $FAILED branch(es)${NC}"
fi
echo ""

if [ $UPDATED -gt 0 ]; then
    print_success "Stack updated successfully!"
    print_info "Run ./scripts/pr-stack/list-stack.sh to see updated stack"
fi

if [ $FAILED -gt 0 ]; then
    print_warning "Some branches failed to update"
    print_info "Check the errors above and resolve manually"
fi

# Sync to Charcoal if available
if charcoal_initialized; then
    print_info "Syncing metadata to Charcoal..."
    sync_charcoal_to_native
fi
