#!/usr/bin/env bash

# create-stack.sh - Create a new branch in the PR stack
# Usage: ./create-stack.sh <new-branch-name> [base-branch] [commit-message] [--worktree]

set -e

# Load libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/validation.sh"
source "$SCRIPT_DIR/lib/charcoal-compat.sh"

# Functions
print_usage() {
    echo -e "${BLUE}Usage:${NC}"
    echo "  ./create-stack.sh <new-branch-name> [base-branch] [commit-message] [--worktree]"
    echo ""
    echo -e "${BLUE}Arguments:${NC}"
    echo "  new-branch-name    Name of the new branch to create (required)"
    echo "  base-branch        Branch to base the new branch on (default: main)"
    echo "  commit-message     Initial commit message (optional)"
    echo "  --worktree, -w     Create a git worktree for this branch"
    echo ""
    echo -e "${BLUE}Examples:${NC}"
    echo "  ./create-stack.sh feature/new-api main"
    echo "  ./create-stack.sh feature/ui feature/api --worktree"
}

# Parse arguments
NEW_BRANCH=""
BASE_BRANCH=""
COMMIT_MESSAGE=""
CREATE_WORKTREE=false
POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --worktree|-w)
            CREATE_WORKTREE=true
            shift
            ;;
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
    if [ "$CREATE_WORKTREE" = true ]; then
         print_info "Auto-updating base branch for worktree creation..."
         # We can't checkout, so we rely on fetch. 
         # If the local base branch is behind, the worktree creation from it might use the old tip.
         # However, we can use origin/$BASE_BRANCH if we want the latest.
         # For now, let's assume the user wants to branch from the local ref, 
         # but we warn them. If they wanted to update, they should have pulled.
         # OR we can try to fast-forward if possible without checkout:
         git fetch origin "$BASE_BRANCH:$BASE_BRANCH" 2>/dev/null || print_warning "Could not fast-forward $BASE_BRANCH without checkout."
    else
        read -p "Update $BASE_BRANCH from remote? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git checkout "$BASE_BRANCH"
            git pull origin "$BASE_BRANCH"
        fi
    fi
fi

if [ "$CREATE_WORKTREE" = true ]; then
    # Worktree Creation Logic
    
    # Sanitize directory name (remove type prefix if standard, replace slashes)
    # E.g. feature/foo -> foo
    # Sanitize logic:
    # 1. Remove standard prefixes
    # 2. Lowercase
    # 3. Replace spaces/underscores with hyphens
    # 4. Remove special chars
    # 5. Collapse hyphens
    
    DESCRIPTION=$(echo "$NEW_BRANCH" | sed -E 's/^(feature|feat|bugfix|fix|hotfix|release|chore)\///')
    DESCRIPTION=$(echo "$DESCRIPTION" | tr '[:upper:]' '[:lower:]' | sed -E 's/[ _]/-/g' | sed -E 's/[^a-z0-9.-]//g' | sed -E 's/-+/-/g' | sed -E 's/^-|-$//g')
    
    WORKTREE_PATH=".trees/$DESCRIPTION"
    WORKTREE_FULL_PATH="$(cd "$(dirname "$REPO_ROOT")" && pwd)/$(basename "$REPO_ROOT")/$WORKTREE_PATH"
    # Resolve relative path to absolute for sed usage later
    # Actually, we can just use $(cd $WORKTREE_PATH && pwd) after creation.
    
    print_info "Creating worktree at $WORKTREE_PATH..."
    
    # Ensure .trees exists
    mkdir -p .trees
    
    # Check if directory exists
    if [ -d "$WORKTREE_PATH" ]; then
        print_error "Directory $WORKTREE_PATH already exists"
        exit 1
    fi
    
    # Check if .trees/ is in .gitignore
    if ! grep -q "^.trees/" .gitignore 2>/dev/null; then
        echo ".trees/" >> .gitignore
        print_info "Added .trees/ to .gitignore"
    fi
    
    # Create worktree and branch
    # git worktree add -b <branch> <path> <start-point>
    if git worktree add -b "$NEW_BRANCH" "$WORKTREE_PATH" "$BASE_BRANCH"; then
        
        # Get absolute path of worktree for config updates
        WORKTREE_ABS_PATH="$(cd "$WORKTREE_PATH" && pwd)"
        
        # ==============================================================================
        # CONFIG COPYING (Strictly following .claude/agents/git-worktree.md rules)
        # ==============================================================================
        
        print_info "Setting up worktree configuration..."
        
        # 1. Copy .env if it exists and is gitignored
        if [ -f .env ] && git check-ignore -q .env 2>/dev/null; then
            cp .env "$WORKTREE_PATH/.env"
            print_info "Copied .env (gitignored)"
        fi
        
        # 2. Copy directories ONLY if they are NOT tracked by git
        # We use git ls-tree to check tracking status in HEAD
        
        for dir in ".vscode" ".claude" ".serena" ".cursor"; do
            if [ -d "$dir" ]; then
                if ! git ls-tree -d HEAD "$dir" >/dev/null 2>&1; then
                    cp -r "$dir" "$WORKTREE_PATH/$dir"
                    print_info "Copied $dir (untracked)"
                else
                    # Special case: Copy gitignored cache/memory files within tracked directories
                    # e.g. .serena/cache
                    if [ "$dir" == ".serena" ] && [ -d ".serena/cache" ]; then
                        mkdir -p "$WORKTREE_PATH/.serena"
                        cp -r ".serena/cache" "$WORKTREE_PATH/.serena/cache" 2>/dev/null || true
                        print_info "Copied .serena/cache"
                    fi
                fi
            fi
        done

        # 3. Copy MCP configs (often gitignored) with updated paths
        
        # .mcp.json
        if [ -f .mcp.json ]; then
            # Copy and update paths to point to the worktree
            # Escape quotes for sed
            sed "s|\"--project\", \"[^\"]*\"|\"--project\", \"$WORKTREE_ABS_PATH\"|g" .mcp.json > "$WORKTREE_PATH/.mcp.json"
            print_info "Copied and updated .mcp.json"
        fi
        
        # .cursor/mcp.json
        if [ -f .cursor/mcp.json ]; then
            mkdir -p "$WORKTREE_PATH/.cursor"
            sed "s|\"--project\", \"[^\"]*\"|\"--project\", \"$WORKTREE_ABS_PATH\"|g" .cursor/mcp.json > "$WORKTREE_PATH/.cursor/mcp.json"
            print_info "Copied and updated .cursor/mcp.json"
        fi

        # ==============================================================================
        
        # Setup initial commit in the worktree if requested
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
        
        # Store stack info (critical for PR stacking)
        # We do this here because the main script's stack update block runs in current dir
        # but we want to ensure it's recorded. The outer script does this too, but double checking
        # that the branch creation above didn't fail is key.
        
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

else
    # Standard Branch Creation Logic
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
fi
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
