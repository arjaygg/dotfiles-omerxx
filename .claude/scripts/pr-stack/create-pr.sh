#!/usr/bin/env bash

# create-pr.sh - Create a Pull Request in Azure DevOps
# Usage: ./create-pr.sh <source-branch> [target-branch] [title] [--draft]

set -e

# Load validation library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/validation.sh"

# Azure DevOps Configuration
# Try to get from git config, default to hardcoded values
ORGANIZATION=$(git config --get azure.organization || echo "https://dev.azure.com/bofaz")
PROJECT=$(git config --get azure.project || echo "Axos-Universal-Core")
REPOSITORY=$(git remote get-url origin | sed -e 's/.*[\/:]\([^\/]*\)\.git/\1/' -e 's/.*[\/:]\([^\/]*\)$/\1/')
if [ -z "$REPOSITORY" ]; then
    print_warning "Could not detect repository name from git remote. Defaulting to current directory name."
    REPOSITORY=$(basename "$PWD")
fi

# Functions
print_usage() {
    echo -e "${BLUE}Usage:${NC}"
    echo "  ./create-pr.sh <source-branch> [target-branch] [title] [--draft]"
    echo ""
    echo -e "${BLUE}Arguments:${NC}"
    echo "  source-branch      Branch to create PR from (required)"
    echo "  target-branch      Branch to merge into (default: main)"
    echo "  title              PR title (optional, will prompt if not provided)"
    echo "  --draft            Create as draft PR (optional)"
    echo ""
    echo -e "${BLUE}Examples:${NC}"
    echo "  ./create-pr.sh feature/new-api"
    echo "  ./create-pr.sh feature/new-api main 'Add new API endpoint'"
    echo "  ./create-pr.sh feature/ui feature/api 'Add UI for new API' --draft"
}

# Validate arguments
if [ $# -lt 1 ]; then
    print_error "Missing required argument: source-branch"
    print_usage
    exit 1
fi

SOURCE_BRANCH=$1
# Determine default branch
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
TARGET_BRANCH=${2:-$DEFAULT_BRANCH}
TITLE=$3
DRAFT=false

# Check for --draft flag
for arg in "$@"; do
    if [ "$arg" == "--draft" ]; then
        DRAFT=true
    fi
done

# Validate prerequisites using library functions
validate_pr_create_prerequisites "$SOURCE_BRANCH" "$TARGET_BRANCH" || exit 1

# Validate PR target is correct for stacked PRs (non-blocking warning)
validate_pr_target "$SOURCE_BRANCH" "$TARGET_BRANCH" || exit 1

# Get repository root (already at root from validation)
REPO_ROOT=$(get_repo_root)

# Ensure source branch is pushed
print_info "Checking if $SOURCE_BRANCH is pushed to remote..."
if ! git ls-remote --exit-code --heads origin "$SOURCE_BRANCH" > /dev/null 2>&1; then
    print_warning "Branch $SOURCE_BRANCH is not pushed to remote"
    read -p "Push $SOURCE_BRANCH now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git push -u origin "$SOURCE_BRANCH"
        print_success "Branch pushed successfully"
    else
        print_error "Cannot create PR without pushing branch"
        exit 1
    fi
fi

# Get title if not provided
if [ -z "$TITLE" ]; then
    # Try to get from latest commit
    LATEST_COMMIT=$(git log -1 --pretty=%B "$SOURCE_BRANCH")
    echo -e "${BLUE}Suggested title from latest commit:${NC}"
    echo "$LATEST_COMMIT"
    echo ""
    read -p "Use this title? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        TITLE="$LATEST_COMMIT"
    else
        read -p "Enter PR title: " TITLE
    fi
fi

# Generate PR description
print_info "Generating PR description..."

# Get commit messages between source and target
COMMITS=$(git log --pretty=format:"- %s" "$TARGET_BRANCH..$SOURCE_BRANCH")

# Check if there are related stories
STORY_FILE=$(find docs/stories -name "*.story.md" 2>/dev/null | head -1)
STORY_REF=""
if [ -n "$STORY_FILE" ]; then
    STORY_NUM=$(basename "$STORY_FILE" .story.md)
    STORY_REF="Related Story: \`$STORY_NUM\`"
fi

# Build description
DESCRIPTION="## Changes

$COMMITS

## Dependencies
"

# Check if this PR depends on another
# NOTE: Worktree-safe path resolution (in worktrees, .git is not a directory)
STACK_INFO_FILE="$(git rev-parse --git-path pr-stack-info)"
if [ -f "$STACK_INFO_FILE" ] && [ "$TARGET_BRANCH" != "main" ]; then
    DESCRIPTION="$DESCRIPTION
⚠️ **This PR depends on \`$TARGET_BRANCH\` being merged first**

Base branch: \`$TARGET_BRANCH\`
"
fi

DESCRIPTION="$DESCRIPTION
$STORY_REF

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project conventions
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes (or breaking changes documented)

---
*Created via PR stacking automation*
"

# Create the PR
print_info "Creating Pull Request..."

# Build az command
AZ_CMD="az repos pr create \
    --repository \"$REPOSITORY\" \
    --organization \"$ORGANIZATION\" \
    --project \"$PROJECT\" \
    --source-branch \"$SOURCE_BRANCH\" \
    --target-branch \"$TARGET_BRANCH\" \
    --title \"$TITLE\" \
    --description \"$DESCRIPTION\""

if [ "$DRAFT" = true ]; then
    AZ_CMD="$AZ_CMD --draft true"
fi

# Execute command
PR_OUTPUT=$(eval $AZ_CMD 2>&1)

if [ $? -eq 0 ]; then
    print_success "Pull Request created successfully!"

    # Extract PR ID and URL
    PR_ID=$(echo "$PR_OUTPUT" | grep -o '"pullRequestId": [0-9]*' | grep -o '[0-9]*')

    # Build a human-friendly PR URL for the web UI.
    #
    # IMPORTANT: Do not grep the first `"url"` from PR_OUTPUT. The JSON contains many `url` fields
    # (e.g., createdBy.url) and the first one is often an identity API endpoint, not the PR page.
    PR_URL=""

    # Prefer deriving from the repository's web URL (most reliable across host formats).
    REPO_WEB_URL="$(az repos pr show \
        --id "$PR_ID" \
        --organization "$ORGANIZATION" \
        --query "repository.webUrl" \
        -o tsv 2>/dev/null || true)"
    if [ -n "$REPO_WEB_URL" ]; then
        PR_URL="${REPO_WEB_URL%/}/pullrequest/$PR_ID"
    else
        # Fallback: construct using the configured org/project/repo (dev.azure.com format).
        PR_URL="${ORGANIZATION%/}/${PROJECT}/_git/${REPOSITORY}/pullrequest/${PR_ID}"
    fi

    echo ""
    print_info "PR #$PR_ID created"
    print_info "URL: $PR_URL"
    echo ""

    # Store PR info for tracking
    PR_CREATED_FILE="$(git rev-parse --git-path pr-created)"
    mkdir -p "$(dirname "$PR_CREATED_FILE")"
    echo "$SOURCE_BRANCH:$TARGET_BRANCH:$PR_ID:$(date +%s)" >> "$PR_CREATED_FILE"

    # Show next steps
    echo -e "${GREEN}Next steps:${NC}"
    echo "  1. Review the PR in Azure DevOps: $PR_URL"
    if [ "$DRAFT" = true ]; then
        echo "  2. Mark as ready for review when complete"
    else
        echo "  2. Wait for reviews and address feedback"
    fi
    echo "  3. After merge, update dependent PRs:"
    echo "     ./scripts/pr-stack/update-stack.sh $SOURCE_BRANCH"
else
    print_error "Failed to create Pull Request"
    echo "$PR_OUTPUT"
    exit 1
fi
