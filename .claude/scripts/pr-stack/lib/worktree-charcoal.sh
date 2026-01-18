#!/usr/bin/env bash

# worktree-charcoal.sh - Charcoal integration for worktree workflows
# Enables full Charcoal capabilities while working across multiple worktrees

# Source dependencies
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/validation.sh"
source "$SCRIPT_DIR/charcoal-compat.sh"

# ============================================================================
# Worktree Detection
# ============================================================================

# Check if current directory is a worktree
# Returns: 0 if in worktree, 1 if in main repo
is_in_worktree() {
    local git_dir
    git_dir=$(git rev-parse --git-dir 2>/dev/null)
    
    # Worktrees have .git as a file, not a directory
    if [ -f "$(git rev-parse --show-toplevel)/.git" ]; then
        return 0
    fi
    
    return 1
}

# Get the main repo path from a worktree
# Returns: Path to main repo
get_main_repo_path() {
    local git_common_dir
    git_common_dir=$(git rev-parse --git-common-dir 2>/dev/null)
    
    if [ -n "$git_common_dir" ]; then
        # Remove /.git from the end
        echo "${git_common_dir%/.git}"
    else
        git rev-parse --show-toplevel
    fi
}

# Get worktree path for a given branch
# Args: $1 - branch name
# Returns: Path to worktree or empty if not in worktree
get_worktree_path() {
    local branch=$1
    local main_repo
    main_repo=$(get_main_repo_path)
    
    # List all worktrees and find the one with this branch
    git worktree list --porcelain | awk -v branch="$branch" '
        /^worktree / { path=$2 }
        /^branch / { 
            if ($2 == "refs/heads/" branch) {
                print path
                exit
            }
        }
    '
}

# ============================================================================
# Worktree-Aware Charcoal Commands
# ============================================================================

# Navigate up in stack (worktree-aware)
# If parent branch has a worktree, cd there; otherwise checkout in current location
wt_charcoal_up() {
    if ! charcoal_initialized; then
        print_error "Charcoal not initialized. Run: ./scripts/stack init"
        return 1
    fi
    
    local current_branch
    current_branch=$(git branch --show-current)

    # Get parent branch from Charcoal using helper function
    local parent_branch
    parent_branch=$(charcoal_get_parent "$current_branch")

    if [ -z "$parent_branch" ]; then
        print_error "No parent branch found for $current_branch"
        return 1
    fi
    
    # Check if parent has a worktree
    local parent_worktree
    parent_worktree=$(get_worktree_path "$parent_branch")
    
    if [ -n "$parent_worktree" ]; then
        print_info "Navigating to worktree: $parent_worktree"
        echo "cd $parent_worktree"
        # Note: Can't actually cd from a script, so we output the command
        # User should use: eval $(wt gt up)
    else
        # No worktree, use regular Charcoal navigation
        if is_in_worktree; then
            print_warning "Parent branch $parent_branch has no worktree"
            print_info "Options:"
            echo "  1. Create worktree: ./scripts/stack worktree-add $parent_branch"
            echo "  2. Navigate in main repo: (cd $(get_main_repo_path) && gt up)"
            return 1
        else
            gt up
        fi
    fi
}

# Navigate down in stack (worktree-aware)
# Args: $1 - child index (optional)
wt_charcoal_down() {
    local child_index=${1:-0}
    
    if ! charcoal_initialized; then
        print_error "Charcoal not initialized. Run: ./scripts/stack init"
        return 1
    fi
    
    local current_branch
    current_branch=$(git branch --show-current)

    # Get child branches from Charcoal using helper function
    local children_array
    children_array=($(charcoal_get_children "$current_branch"))

    if [ ${#children_array[@]} -eq 0 ]; then
        print_error "No child branches found for $current_branch"
        return 1
    fi

    if [ "$child_index" -ge "${#children_array[@]}" ]; then
        print_error "No child branch found at index $child_index"
        return 1
    fi

    local child_branch="${children_array[$child_index]}"
    
    # Check if child has a worktree
    local child_worktree
    child_worktree=$(get_worktree_path "$child_branch")
    
    if [ -n "$child_worktree" ]; then
        print_info "Navigating to worktree: $child_worktree"
        echo "cd $child_worktree"
        # Note: User should use: eval $(wt gt down)
    else
        # No worktree, use regular Charcoal navigation
        if is_in_worktree; then
            print_warning "Child branch $child_branch has no worktree"
            print_info "Options:"
            echo "  1. Create worktree: ./scripts/stack worktree-add $child_branch"
            echo "  2. Navigate in main repo: (cd $(get_main_repo_path) && gt down $child_index)"
            return 1
        else
            gt down "$child_index"
        fi
    fi
}

# Restack from current location (worktree-aware)
# Runs gt restack in main repo, then syncs all worktrees
wt_charcoal_restack() {
    if ! charcoal_initialized; then
        print_error "Charcoal not initialized. Run: ./scripts/stack init"
        return 1
    fi
    
    local main_repo
    main_repo=$(get_main_repo_path)
    
    local current_dir
    current_dir=$(pwd)
    
    print_info "Restacking in main repo..."
    
    # Run restack in main repo
    (
        cd "$main_repo"
        gt restack
    )
    
    if [ $? -eq 0 ]; then
        print_success "Stack rebased successfully"
        
        # Sync worktrees
        print_info "Syncing worktrees..."
        sync_all_worktrees
        
        # Sync metadata
        sync_charcoal_to_native
    else
        print_error "Restack failed"
        return 1
    fi
}

# Sync all worktrees after a restack
# Fetches latest changes in each worktree
sync_all_worktrees() {
    local main_repo
    main_repo=$(get_main_repo_path)
    
    # Get all worktree paths
    git worktree list --porcelain | grep '^worktree ' | cut -d' ' -f2 | while read -r wt_path; do
        if [ "$wt_path" != "$main_repo" ]; then
            local wt_branch
            wt_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null)
            
            if [ -n "$wt_branch" ]; then
                print_info "Syncing worktree: $wt_path ($wt_branch)"
                
                # Fetch and reset to match the rebased branch
                (
                    cd "$wt_path"
                    git fetch origin "$wt_branch" 2>/dev/null || true
                    
                    # Check if branch was rebased
                    local behind
                    behind=$(git rev-list --count HEAD..@{upstream} 2>/dev/null || echo "0")
                    
                    if [ "$behind" -gt 0 ]; then
                        print_warning "Worktree $wt_path is behind by $behind commits"
                        echo "  Run: cd $wt_path && git pull --rebase"
                    fi
                )
            fi
        fi
    done
}

# ============================================================================
# Worktree Management Commands
# ============================================================================

# Add a worktree for an existing branch
# Args: $1 - branch name
wt_add_for_branch() {
    local branch=$1
    
    if [ -z "$branch" ]; then
        print_error "Branch name required"
        return 1
    fi
    
    # Check if branch exists
    if ! git rev-parse --verify "$branch" > /dev/null 2>&1; then
        print_error "Branch $branch does not exist"
        return 1
    fi
    
    # Check if branch already has a worktree
    local existing_wt
    existing_wt=$(get_worktree_path "$branch")
    
    if [ -n "$existing_wt" ]; then
        print_warning "Branch $branch already has a worktree at: $existing_wt"
        return 1
    fi
    
    # Sanitize branch name for directory
    local description
    description=$(echo "$branch" | sed -E 's/^(feature|feat|bugfix|fix|hotfix|release|chore)\///')
    description=$(echo "$description" | tr '[:upper:]' '[:lower:]' | sed -E 's/[ _]/-/g' | sed -E 's/[^a-z0-9.-]//g' | sed -E 's/-+/-/g' | sed -E 's/^-|-$//g')
    
    local worktree_path=".trees/$description"
    
    print_info "Creating worktree for existing branch: $branch"
    print_info "Location: $worktree_path"
    
    # Ensure .trees exists
    mkdir -p .trees
    
    # Create worktree (branch already exists, so just add it)
    if git worktree add "$worktree_path" "$branch"; then
        print_success "Worktree created at: $worktree_path"
        
        # Copy configs
        copy_worktree_configs "$worktree_path"
        
        echo ""
        echo -e "${GREEN}To navigate:${NC}"
        echo "  cd $worktree_path"
        
        return 0
    else
        print_error "Failed to create worktree"
        return 1
    fi
}

# Copy IDE and tool configs to worktree
# Args: $1 - worktree path
copy_worktree_configs() {
    local worktree_path=$1
    local worktree_abs_path
    worktree_abs_path="$(cd "$worktree_path" && pwd)"
    
    print_info "Copying configurations..."
    
    # Copy .env if gitignored
    if [ -f .env ] && git check-ignore -q .env 2>/dev/null; then
        cp .env "$worktree_path/.env"
        print_info "Copied .env"
    fi
    
    # Copy untracked IDE directories
    for dir in ".vscode" ".claude" ".serena" ".cursor"; do
        if [ -d "$dir" ] && ! git ls-tree -d HEAD "$dir" >/dev/null 2>&1; then
            cp -r "$dir" "$worktree_path/$dir"
            print_info "Copied $dir"
        fi
    done
    
    # Copy and update MCP configs
    if [ -f .mcp.json ]; then
        sed "s|\"--project\", \"[^\"]*\"|\"--project\", \"$worktree_abs_path\"|g" .mcp.json > "$worktree_path/.mcp.json"
        print_info "Copied .mcp.json"
    fi
    
    if [ -f .cursor/mcp.json ]; then
        mkdir -p "$worktree_path/.cursor"
        sed "s|\"--project\", \"[^\"]*\"|\"--project\", \"$worktree_abs_path\"|g" .cursor/mcp.json > "$worktree_path/.cursor/mcp.json"
        print_info "Copied .cursor/mcp.json"
    fi
}

# Show stack with worktree information
wt_stack_status() {
    if ! charcoal_initialized; then
        print_error "Charcoal not initialized. Run: ./scripts/stack init"
        return 1
    fi
    
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║              STACK STATUS (with Worktrees)                 ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Get Charcoal stack (using gt log short for visual representation)
    local stack_output
    stack_output=$(gt log short 2>/dev/null)
    
    # Enhance with worktree information
    echo "$stack_output" | while IFS= read -r line; do
        # Extract branch name from line
        local branch
        branch=$(echo "$line" | sed -E 's/.*[├└│]── ([^ ]+).*/\1/')
        
        # Check if this branch has a worktree
        if [ -n "$branch" ] && [[ "$branch" =~ ^[a-zA-Z] ]]; then
            local wt_path
            wt_path=$(get_worktree_path "$branch")
            
            if [ -n "$wt_path" ]; then
                echo -e "$line ${CYAN}[WT: $wt_path]${NC}"
            else
                echo "$line"
            fi
        else
            echo "$line"
        fi
    done
}

# ============================================================================
# Export Functions
# ============================================================================

export -f is_in_worktree 2>/dev/null || true
export -f get_main_repo_path 2>/dev/null || true
export -f get_worktree_path 2>/dev/null || true
export -f wt_charcoal_up 2>/dev/null || true
export -f wt_charcoal_down 2>/dev/null || true
export -f wt_charcoal_restack 2>/dev/null || true
export -f sync_all_worktrees 2>/dev/null || true
export -f wt_add_for_branch 2>/dev/null || true
export -f copy_worktree_configs 2>/dev/null || true
export -f wt_stack_status 2>/dev/null || true
