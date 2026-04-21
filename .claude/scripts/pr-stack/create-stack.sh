#!/usr/bin/env bash

# create-stack.sh - Create a new branch in the PR stack
# Usage: ./create-stack.sh <new-branch-name> [base-branch] [commit-message]
# Always creates a linked worktree under <main-repo>/.trees/ (never nested under another worktree).

set -e

# Load libraries
_CREATE_STACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_CREATE_STACK_DIR/lib/validation.sh"
source "$_CREATE_STACK_DIR/lib/charcoal-compat.sh"
source "$_CREATE_STACK_DIR/lib/worktree-charcoal.sh"

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
}

# Parse arguments
NEW_BRANCH=""
BASE_BRANCH=""
COMMIT_MESSAGE=""
POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            POSITIONAL_ARGS+=("$1")
            shift
            ;;
    esac
done

# Restore positional arguments
set -- "${POSITIONAL_ARGS[@]}"

# Validate arguments
if [ $# -lt 1 ]; then
    print_error "Missing required argument: new-branch-name"
    print_usage
    exit 1
fi

# Determine default branch
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")

NEW_BRANCH=$1
# Default base: current branch if on a stacked branch, otherwise trunk
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
if [ -n "$CURRENT_BRANCH" ] && [ "$CURRENT_BRANCH" != "$DEFAULT_BRANCH" ]; then
    BASE_BRANCH=${2:-$CURRENT_BRANCH}
else
    BASE_BRANCH=${2:-$DEFAULT_BRANCH}
fi
COMMIT_MESSAGE=$3

# Validate prerequisites using library functions
validate_stack_create_prerequisites "$NEW_BRANCH" "$BASE_BRANCH" || exit 1

# Require Charcoal: this toolchain is Charcoal-first and does not use local tracking files.
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

# Linked worktrees must be created from the main checkout root (parent of .trees/),
# not from inside another worktree — even though validation cd's to show-toplevel.
REPO_ROOT="$(resolve_main_repo_root)"
cd "$REPO_ROOT"

print_info "Creating new branch: $NEW_BRANCH"
print_info "Based on: $BASE_BRANCH"
print_info "Repository root: $REPO_ROOT"

# Fetch latest changes
print_info "Fetching latest changes..."
if git remote get-url origin >/dev/null 2>&1; then
    git fetch origin
else
    print_warning "No 'origin' remote configured; skipping fetch"
fi

# Check if base branch is up to date with remote
BASE_BEHIND=$(git rev-list --count "$BASE_BRANCH..origin/$BASE_BRANCH" 2>/dev/null || echo "0")
if [ "$BASE_BEHIND" -gt 0 ]; then
    print_warning "Local $BASE_BRANCH is $BASE_BEHIND commit(s) behind origin/$BASE_BRANCH"
    print_info "Auto-updating base branch ref for worktree creation..."
    if git remote get-url origin >/dev/null 2>&1; then
        git fetch origin "$BASE_BRANCH:$BASE_BRANCH" 2>/dev/null || print_warning "Could not fast-forward $BASE_BRANCH without checkout."
    else
        print_warning "No 'origin' remote configured; cannot fast-forward $BASE_BRANCH"
    fi
fi

# Worktree creation (always); paths are relative to REPO_ROOT

# Sanitize directory name (remove type prefix if standard, replace slashes)
# E.g. feature/foo -> foo
DESCRIPTION=$(echo "$NEW_BRANCH" | sed -E 's/^(feature|feat|bugfix|fix|hotfix|release|chore)\///')
DESCRIPTION=$(echo "$DESCRIPTION" | tr '[:upper:]' '[:lower:]' | sed -E 's/[ _]/-/g' | sed -E 's/[^a-z0-9.-]//g' | sed -E 's/-+/-/g' | sed -E 's/^-|-$//g')

WORKTREE_PATH=".trees/$DESCRIPTION"

print_info "Creating worktree at $WORKTREE_PATH..."

mkdir -p .trees

if [ -d "$WORKTREE_PATH" ]; then
    print_error "Directory $WORKTREE_PATH already exists"
    exit 1
fi

if ! grep -q "^.trees/" .gitignore 2>/dev/null; then
    echo ".trees/" >> .gitignore
    print_info "Added .trees/ to .gitignore"
fi

if git worktree add -b "$NEW_BRANCH" "$WORKTREE_PATH" "$BASE_BRANCH"; then
    WORKTREE_ABS_PATH="$(cd "$WORKTREE_PATH" && pwd)"
        
    print_info "Setting up worktree configuration..."

    if [ -f .env ] && git check-ignore -q .env 2>/dev/null; then
        cp .env "$WORKTREE_PATH/.env"
        print_info "Copied .env (gitignored)"
    fi

    for dir in ".vscode" ".claude" ".serena" ".cursor"; do
        if [ -d "$dir" ]; then
            if ! git ls-tree -d HEAD "$dir" >/dev/null 2>&1; then
                cp -r "$dir" "$WORKTREE_PATH/$dir"
                print_info "Copied $dir (untracked)"
            else
                if [ "$dir" == ".serena" ] && [ -d ".serena/cache" ]; then
                    mkdir -p "$WORKTREE_PATH/.serena"
                    cp -r ".serena/cache" "$WORKTREE_PATH/.serena/cache" 2>/dev/null || true
                    print_info "Copied .serena/cache"
                fi
            fi
        fi
    done

    if [ -f .mcp.json ]; then
        sed "s|\"--project\", \"[^\"]*\"|\"--project\", \"$WORKTREE_ABS_PATH\"|g" .mcp.json > "$WORKTREE_PATH/.mcp.json"
        print_info "Copied and updated .mcp.json"
    fi

    if [ -f .cursor/mcp.json ]; then
        mkdir -p "$WORKTREE_PATH/.cursor"
        sed "s|\"--project\", \"[^\"]*\"|\"--project\", \"$WORKTREE_ABS_PATH\"|g" .cursor/mcp.json > "$WORKTREE_PATH/.cursor/mcp.json"
        print_info "Copied and updated .cursor/mcp.json"
    fi

    if [ -n "$COMMIT_MESSAGE" ]; then
        print_info "Creating initial commit in worktree..."
        mkdir -p "$WORKTREE_PATH/.branch-info"
        cat > "$WORKTREE_PATH/.branch-info/$NEW_BRANCH.md" << EOF
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
        (cd "$WORKTREE_PATH" && git add ".branch-info/$NEW_BRANCH.md" && git commit -m "$COMMIT_MESSAGE")
        print_success "Initial commit created in worktree"
    fi

    echo ""
    echo -e "${GREEN}✅ Created worktree: $WORKTREE_PATH${NC}"
    echo -e "📂 Path: $WORKTREE_ABS_PATH"
    echo -e "🌿 Branch: $NEW_BRANCH (Base: $BASE_BRANCH)"
    echo -e "ℹ️  Note: Tracked directories (.vscode, etc.) are automatically checked out."
    echo ""
    echo -e "${GREEN}To navigate to worktree:${NC}"
    echo "  cd $WORKTREE_PATH"
    echo ""
    echo -e "${GREEN}Next steps:${NC}"
    echo "  1. Make your changes"
    echo "  2. Push: git push -u origin $NEW_BRANCH"
else
    print_error "Failed to create worktree"
    exit 1
fi

echo ""

# Track in Charcoal (single source of truth for stack relationships)
print_info "Tracking branch in Charcoal..."
gt branch track "$NEW_BRANCH" --parent "$BASE_BRANCH"

print_success "Stack updated. Run './scripts/stack status' to see your PR stack"
