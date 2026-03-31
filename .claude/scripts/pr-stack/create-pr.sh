#!/usr/bin/env bash

# create-pr.sh - Create a Pull Request on GitHub
# Usage: ./create-pr.sh <source-branch> [target-branch] [title] [--draft]

set -e

# Load validation library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/validation.sh"
source "$SCRIPT_DIR/lib/charcoal-compat.sh"

REMOTE_URL="$(git remote get-url origin 2>/dev/null || true)"

# Ensure gh credential helper is active (prevents credential.helper= override from blocking push)
gh auth setup-git 2>/dev/null || true

# Detect which GH account to use based on remote org
# Personal repos live under arjaygg; everything else uses the enterprise account
_detect_gh_account() {
    local org
    org=$(echo "$REMOTE_URL" | sed 's|.*github\.com[/:]||;s|/.*||')
    if [ "$org" = "arjaygg" ]; then
        echo "arjaygg"
    else
        echo "Arjay-Gallentes_axosEnt"
    fi
}

_ensure_gh_account() {
    local target_account
    target_account="$(_detect_gh_account)"
    local active_account
    active_account=$(gh api user --jq '.login' 2>/dev/null || echo "")
    if [ -n "$active_account" ] && [ "$active_account" != "$target_account" ]; then
        gh auth switch --user "$target_account" > /dev/null 2>&1 || true
    fi
}

_ensure_gh_account

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

# Validate prerequisites
print_info "Detected GitHub repository"
validate_github_pr_create_prerequisites "$SOURCE_BRANCH" "$TARGET_BRANCH" || exit 1

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

# Push the branch first (gh pr create requires it)
print_info "Pushing branch to origin..."
git push -u origin "$SOURCE_BRANCH"

GH_ARGS=(
    pr create
    --base "$TARGET_BRANCH"
    --head "$SOURCE_BRANCH"
    --title "$TITLE"
    --body "$DESCRIPTION"
)

if [ "$DRAFT" = true ]; then
    GH_ARGS+=(--draft)
fi

PR_OUTPUT="$(gh "${GH_ARGS[@]}" 2>&1)"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    print_success "Pull Request created successfully!"
    PR_URL="$PR_OUTPUT"
    echo ""
    print_info "URL: $PR_URL"
    echo ""
    echo -e "${GREEN}Next steps:${NC}"
    echo "  1. Review the PR on GitHub: $PR_URL"
    if [ "$DRAFT" = true ]; then
        echo "  2. Mark as ready for review when complete"
    else
        echo "  2. Wait for reviews and address feedback"
    fi
    echo "  3. After merge, update dependent PRs:"
    echo "     $STACK_SCRIPT_DIR/stack update $SOURCE_BRANCH"
else
    print_error "Failed to create Pull Request"
    echo "$PR_OUTPUT"
    exit 1
fi
