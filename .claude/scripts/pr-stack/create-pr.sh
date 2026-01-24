#!/usr/bin/env bash

# create-pr.sh - Create a Pull Request in Azure DevOps
# Usage: ./create-pr.sh <source-branch> [target-branch] [title] [--draft]

set -e

# Load validation library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/validation.sh"
source "$SCRIPT_DIR/lib/charcoal-compat.sh"

# Azure DevOps Configuration
# Try to get from git config, default to hardcoded values
ORGANIZATION=$(git config --get azure.organization || echo "https://dev.azure.com/bofaz")
PROJECT=$(git config --get azure.project || echo "Axos-Universal-Core")
REMOTE_URL="$(git remote get-url origin 2>/dev/null || true)"
REPOSITORY="$(echo "$REMOTE_URL" | sed -e 's/.*[\/:]\([^\/]*\)\.git/\1/' -e 's/.*[\/:]\([^\/]*\)$/\1/')"
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
# Determine default branch (trunk)
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")

# Target branch:
# - If explicitly provided, use it.
# - Otherwise, prefer Charcoal parent (stacked PRs), falling back to trunk.
TARGET_BRANCH="${2:-}"
if [ -z "$TARGET_BRANCH" ]; then
    if type charcoal_initialized >/dev/null 2>&1 && charcoal_initialized; then
        TARGET_BRANCH="$(charcoal_get_parent "$SOURCE_BRANCH" 2>/dev/null || true)"
    fi
    TARGET_BRANCH="${TARGET_BRANCH:-$DEFAULT_BRANCH}"
fi
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

# Require Charcoal for PR stack workflows (single source of truth for relationships)
if ! charcoal_available; then
    print_error "Charcoal CLI (gt) is required but not installed"
    print_info "Install with: brew install danerwilliams/tap/charcoal"
    exit 1
fi

if ! charcoal_initialized; then
    print_error "Charcoal is not initialized in this repository"
    print_info "Initialize with: ~/.claude/scripts/stack init"
    exit 1
fi

# Validate PR target is correct for stacked PRs (non-blocking warning)
validate_pr_target "$SOURCE_BRANCH" "$TARGET_BRANCH" || exit 1

# Get repository root (already at root from validation)
REPO_ROOT=$(git rev-parse --show-toplevel)

# Build commit list for PR description.
#
# Prefer commits that are on SOURCE_BRANCH but not on TARGET_BRANCH.
# If branches are missing/upstream refs are unusual, fall back gracefully.
COMMITS="$(git log --oneline "${TARGET_BRANCH}..${SOURCE_BRANCH}" 2>/dev/null || true)"
if [ -z "$COMMITS" ]; then
    COMMITS="$(git log -1 --oneline "${SOURCE_BRANCH}" 2>/dev/null || true)"
fi
if [ -z "$COMMITS" ]; then
    COMMITS="(no commits found)"
fi

# Title: if not provided, auto-generate (non-interactive safe).
if [ -z "${TITLE:-}" ]; then
    # If interactive, prompt; otherwise default.
    if [ -t 0 ]; then
        read -p "Enter PR title (default: ${SOURCE_BRANCH}): " TITLE
    fi
    TITLE=${TITLE:-$SOURCE_BRANCH}
fi

# Check if there are related stories
# Fix: Search from REPO_ROOT to find docs even if we are in a worktree
STORY_FILE=$(find "$REPO_ROOT/docs/stories" -name "*.story.md" 2>/dev/null | head -1)
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

# If not targeting trunk, this is a dependent (stacked) PR.
if [ "$TARGET_BRANCH" != "$DEFAULT_BRANCH" ]; then
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

AZ_ARGS=(
    repos pr create
    --repository "$REPOSITORY"
    --organization "$ORGANIZATION"
    --project "$PROJECT"
    --source-branch "$SOURCE_BRANCH"
    --target-branch "$TARGET_BRANCH"
    --title "$TITLE"
    --description "$DESCRIPTION"
)

if [ "$DRAFT" = true ]; then
    AZ_ARGS+=(--draft true)
fi

# Execute command (avoid eval; allow multi-line description safely)
PR_OUTPUT="$(az "${AZ_ARGS[@]}" 2>&1)"

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
