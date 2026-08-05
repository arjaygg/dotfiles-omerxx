#!/bin/bash
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}INFO:${NC} $1"; }
log_success() { echo -e "${GREEN}SUCCESS:${NC} $1"; }
log_warning() { echo -e "${YELLOW}WARNING:${NC} $1"; }
log_error() { echo -e "${RED}ERROR:${NC} $1"; }

# Parse arguments
BASE_BRANCH=""
BRANCH_NAME=""
CHANGES_DESC=""
CURRENT_BRANCH=""
DRY_RUN=false
ORIGINAL_DIR=""
WORKTREE_PATH=""
WORKTREE_NAME=""

usage() {
    cat <<EOF
Usage: $0 --base <branch> --branch <name> --changes "<description>" [OPTIONS]

Required:
  --base <branch>           Base branch (e.g., main)
  --branch <name>           New branch name (e.g., chore/fix-typo)
  --changes "<description>" What changes to make (human-readable)

Optional:
  --current-branch <name>   Branch to update after merge (optional)
  --dry-run                 Show what would happen without executing
  -h, --help                Show this help message

Examples:
  $0 --base main --branch chore/readme --changes "Fix typo in README"
  $0 --base main --branch fix/lint --changes "Fix lint errors" --current-branch feature/ui

EOF
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --base)
            BASE_BRANCH="$2"
            shift 2
            ;;
        --branch)
            BRANCH_NAME="$2"
            shift 2
            ;;
        --changes)
            CHANGES_DESC="$2"
            shift 2
            ;;
        --current-branch)
            CURRENT_BRANCH="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [[ -z "$BASE_BRANCH" ]] || [[ -z "$BRANCH_NAME" ]] || [[ -z "$CHANGES_DESC" ]]; then
    log_error "Missing required arguments"
    usage
fi

# Validate branch name format
if [[ ! "$BRANCH_NAME" =~ ^(feat|fix|chore|docs|refactor|test|style|perf)/ ]]; then
    log_warning "Branch name '$BRANCH_NAME' doesn't follow convention (feat/*, fix/*, chore/*, etc.)"
fi

log_info "=========================================="
log_info "Stack Auto PR Merge"
log_info "=========================================="
log_info "Base branch:    $BASE_BRANCH"
log_info "New branch:     $BRANCH_NAME"
log_info "Changes:        $CHANGES_DESC"
[[ -n "$CURRENT_BRANCH" ]] && log_info "Update branch:  $CURRENT_BRANCH"
[[ "$DRY_RUN" == true ]] && log_warning "DRY RUN MODE - No changes will be made"
log_info "=========================================="

if [[ "$DRY_RUN" == true ]]; then
    log_info "Would execute the following steps:"
    log_info "  1. Create isolated worktree: .trees/${BRANCH_NAME##*/}"
    log_info "  2. Change to worktree directory"
    log_info "  3. Verify changes exist: $CHANGES_DESC"
    log_info "  4. Commit changes"
    log_info "  5. Push to remote"
    log_info "  6. Create PR using stack pr"
    log_info "  7. Auto-approve PR"
    log_info "  8. Merge PR"
    log_info "  9. Return to original directory"
    [[ -n "$CURRENT_BRANCH" ]] && log_info " 10. Update branch '$CURRENT_BRANCH' (with stash if needed)"
    log_info " 11. Clean up worktree"
    exit 0
fi

# Store original directory
ORIGINAL_DIR=$(pwd)

# Calculate worktree path
WORKTREE_NAME="${BRANCH_NAME##*/}"
WORKTREE_PATH=".trees/${WORKTREE_NAME}"

# Step 1: Create stack branch with worktree
log_info "Step 1/8: Creating isolated worktree for branch '$BRANCH_NAME'..."
if ! $HOME/.dotfiles/.claude/scripts/stack create "$BRANCH_NAME" "$BASE_BRANCH" --worktree; then
    log_error "Failed to create stack branch with worktree"
    exit 1
fi
log_success "Worktree created at: $WORKTREE_PATH"

# Step 2: Change to worktree directory
log_info "Step 2/8: Changing to worktree directory..."
if ! cd "$WORKTREE_PATH"; then
    log_error "Failed to change to worktree directory: $WORKTREE_PATH"
    exit 1
fi
log_success "Now working in isolated worktree"

# Step 3: Verify changes exist
log_info "Step 3/8: Verifying changes..."
# Check if there are changes to commit (modified, staged, or untracked)
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    log_success "Changes detected and ready to commit"
    # Show what changed
    log_info "Files changed:"
    git diff --name-only 2>/dev/null || true
    git diff --cached --name-only 2>/dev/null || true
    git ls-files --others --exclude-standard 2>/dev/null || true
else
    log_error "No changes detected."
    log_error "Make sure changes are made before calling this script."
    log_error "Changes description: $CHANGES_DESC"
    exit 1
fi

# Step 4: Commit changes
log_info "Step 4/8: Committing changes..."
COMMIT_TYPE=$(echo "$BRANCH_NAME" | cut -d'/' -f1)
COMMIT_SCOPE=$(echo "$BRANCH_NAME" | cut -d'/' -f2)
COMMIT_MSG="${COMMIT_TYPE}(${COMMIT_SCOPE}): ${CHANGES_DESC}

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

if ! git add -A; then
    log_error "Failed to stage changes"
    exit 1
fi

if ! git commit -m "$COMMIT_MSG"; then
    log_error "Failed to commit (pre-commit hooks may have failed)"
    exit 1
fi
log_success "Changes committed"

# Step 5: Push to remote
log_info "Step 5/8: Pushing to remote..."
if ! git push -u origin "$BRANCH_NAME"; then
    log_error "Failed to push to remote"
    exit 1
fi
log_success "Branch pushed to remote"

# Step 6: Create PR
log_info "Step 6/8: Creating PR..."
PR_OUTPUT=$($HOME/.dotfiles/.claude/scripts/stack pr "$BRANCH_NAME" 2>&1)
PR_ID=$(echo "$PR_OUTPUT" | grep -o 'PR #[0-9]*' | sed 's/PR #//' | head -1)
PR_URL=$(echo "$PR_OUTPUT" | grep -o 'URL: .*' | sed 's/URL: //' | head -1)

if [[ -z "$PR_ID" ]]; then
    log_error "Failed to create PR"
    echo "$PR_OUTPUT"
    exit 1
fi
log_success "PR #$PR_ID created: $PR_URL"

# Step 7: Auto-approve PR
log_info "Step 7/8: Auto-approving PR..."
if ! az repos pr set-vote --id "$PR_ID" --vote approve --organization "https://dev.azure.com/bofaz" > /dev/null 2>&1; then
    log_error "Failed to approve PR (you may need to approve manually)"
    log_info "PR URL: $PR_URL"
    exit 1
fi
log_success "PR approved"

# Step 7: Merge PR
log_info "Step 7/8: Merging PR..."
if ! az repos pr update --id "$PR_ID" --status completed --organization "https://dev.azure.com/bofaz" > /dev/null 2>&1; then
    log_error "Failed to merge PR (may need manual intervention)"
    log_info "PR URL: $PR_URL"
    exit 1
fi

# Wait for merge to complete
log_info "Waiting for merge to complete..."
sleep 3

# Verify merge succeeded
MERGE_STATUS=$(az repos pr show --id "$PR_ID" --organization "https://dev.azure.com/bofaz" --output json 2>/dev/null | jq -r '.mergeStatus // "unknown"')
if [[ "$MERGE_STATUS" != "succeeded" ]]; then
    log_error "Merge did not succeed. Status: $MERGE_STATUS"
    log_info "PR URL: $PR_URL"
    exit 1
fi
log_success "PR merged successfully"

# Step 8: Return to original directory and update current branch
log_info "Step 8/8: Cleaning up and updating branches..."

# Return to original directory
cd "$ORIGINAL_DIR" || {
    log_error "Failed to return to original directory"
    exit 1
}

# Fetch latest changes from remote
git fetch origin "$BASE_BRANCH" > /dev/null 2>&1

# Update current branch if specified
if [[ -n "$CURRENT_BRANCH" ]]; then
    log_info "Updating branch '$CURRENT_BRANCH' with merged changes..."

    # Check if we're on the current branch already
    ACTIVE_BRANCH=$(git branch --show-current)

    if [[ "$ACTIVE_BRANCH" == "$CURRENT_BRANCH" ]]; then
        # We're already on the branch to update

        # Check for uncommitted changes
        STASHED=false
        if ! git diff --quiet || ! git diff --cached --quiet; then
            log_warning "Uncommitted changes detected, stashing..."
            git stash push -m "stack-auto-merge: temporary stash before update" > /dev/null 2>&1
            STASHED=true
        fi

        # Rebase on updated base branch
        if git rebase "origin/$BASE_BRANCH" > /dev/null 2>&1; then
            log_success "Branch '$CURRENT_BRANCH' updated with merged changes"

            # Restore stashed changes if any
            if [[ "$STASHED" == true ]]; then
                if git stash pop > /dev/null 2>&1; then
                    log_success "Restored uncommitted changes"
                else
                    log_warning "Could not restore stashed changes automatically (conflicts?)"
                    log_info "Run 'git stash pop' manually to restore your changes"
                fi
            fi
        else
            log_warning "Rebase failed (you may have conflicts to resolve)"
            git rebase --abort > /dev/null 2>&1 || true

            # Restore stashed changes even if rebase failed
            if [[ "$STASHED" == true ]]; then
                git stash pop > /dev/null 2>&1 || true
            fi
        fi
    else
        log_warning "Not currently on branch '$CURRENT_BRANCH'"
        log_info "Switch to '$CURRENT_BRANCH' and run 'git rebase origin/$BASE_BRANCH' to update"
    fi
fi

# Clean up worktree
log_info "Cleaning up worktree..."
if git worktree remove "$WORKTREE_PATH" --force > /dev/null 2>&1; then
    log_success "Worktree cleaned up: $WORKTREE_PATH"
else
    log_warning "Could not remove worktree automatically: $WORKTREE_PATH"
    log_info "Remove manually with: git worktree remove $WORKTREE_PATH --force"
fi

# Final summary
log_info "=========================================="
log_success "✅ All steps completed successfully!"
log_info "=========================================="
log_info "PR #$PR_ID merged to $BASE_BRANCH"
log_info "URL: $PR_URL"
[[ -n "$CURRENT_BRANCH" ]] && log_info "Branch '$CURRENT_BRANCH' updated"
log_info "=========================================="
