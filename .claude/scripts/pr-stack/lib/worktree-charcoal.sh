#!/usr/bin/env bash

# worktree-charcoal.sh - Charcoal integration for worktree workflows
# Enables full Charcoal capabilities while working across multiple worktrees

# Prevent multiple sourcing
if [ -n "${_WORKTREE_CHARCOAL_SOURCED:-}" ]; then
    return 0
fi
_WORKTREE_CHARCOAL_SOURCED=1

# Source dependencies only if not already loaded
if ! type print_info &>/dev/null; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "$SCRIPT_DIR/validation.sh"
fi

if ! type charcoal_initialized &>/dev/null; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "$SCRIPT_DIR/charcoal-compat.sh"
fi

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
        print_error "Charcoal not initialized. Run: ./scripts/stack init" >&2
        return 1
    fi
    
    local current_branch
    current_branch=$(git branch --show-current)

    # Get parent branch from Charcoal using helper function
    local parent_branch
    parent_branch=$(charcoal_get_parent "$current_branch")

    if [ -z "$parent_branch" ]; then
        print_error "No parent branch found for $current_branch" >&2
        return 1
    fi
    
    # Check if parent has a worktree
    local parent_worktree
    parent_worktree=$(get_worktree_path "$parent_branch")
    
    if [ -n "$parent_worktree" ]; then
        # IMPORTANT: Keep stdout clean for `eval $(stack up)`
        print_info "Navigating to worktree: $parent_worktree" >&2
        echo "cd $parent_worktree"
        # Note: Can't actually cd from a script, so we output the command
        # User should use: eval $(wt gt up)
    else
        # No worktree, use regular Charcoal navigation
        if is_in_worktree; then
            print_warning "Parent branch $parent_branch has no worktree" >&2
            print_info "Options:" >&2
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
        print_error "Charcoal not initialized. Run: ./scripts/stack init" >&2
        return 1
    fi
    
    local current_branch
    current_branch=$(git branch --show-current)

    # Get child branches from Charcoal using helper function
    local children_array
    children_array=($(charcoal_get_children "$current_branch"))

    if [ ${#children_array[@]} -eq 0 ]; then
        print_error "No child branches found for $current_branch" >&2
        return 1
    fi

    if [ "$child_index" -ge "${#children_array[@]}" ]; then
        print_error "No child branch found at index $child_index" >&2
        return 1
    fi

    local child_branch="${children_array[$child_index]}"
    
    # Check if child has a worktree
    local child_worktree
    child_worktree=$(get_worktree_path "$child_branch")
    
    if [ -n "$child_worktree" ]; then
        # IMPORTANT: Keep stdout clean for `eval $(stack down)`
        print_info "Navigating to worktree: $child_worktree" >&2
        echo "cd $child_worktree"
        # Note: User should use: eval $(wt gt down)
    else
        # No worktree, use regular Charcoal navigation
        if is_in_worktree; then
            print_warning "Child branch $child_branch has no worktree" >&2
            print_info "Options:" >&2
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
# Automatically handles uncommitted changes:
#   - Staged changes → auto-commit with WIP message
#   - Unstaged changes → auto-stash during rebase
#   - Untracked files → ignored (won't interfere)
wt_charcoal_restack() {
    if ! charcoal_initialized; then
        print_error "Charcoal not initialized. Run: ./scripts/stack init"
        return 1
    fi

    local main_repo
    main_repo=$(get_main_repo_path)

    local current_dir
    current_dir=$(pwd)

    # Detect uncommitted changes in current location
    local has_staged_changes=false
    local has_unstaged_changes=false
    local current_branch

    # Check for staged changes
    if ! git diff --cached --quiet 2>/dev/null; then
        has_staged_changes=true
    fi

    # Check for unstaged changes
    if ! git diff --quiet 2>/dev/null; then
        has_unstaged_changes=true
    fi

    # Handle uncommitted changes automatically
    if [ "$has_staged_changes" = true ]; then
        print_info "Detected staged changes - creating auto-commit..."
        current_branch=$(git branch --show-current)
        git commit -m "WIP: auto-commit before restack on $current_branch

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
        print_success "Auto-commit created"
    elif [ "$has_unstaged_changes" = true ]; then
        print_info "Detected unstaged changes - will use auto-stash..."
    fi

    # Determine where to run restack from
    local restack_location="$main_repo"

    # If current directory is a worktree, restack from here instead
    if is_in_worktree; then
        restack_location="$current_dir"
        print_info "Running restack from current worktree..."
    else
        print_info "Restacking in main repo..."
    fi

    # Run restack with manual stash for unstaged changes
    local restack_result
    local stashed=false
    (
        cd "$restack_location"

        # Manually stash unstaged changes before restack
        if [ "$has_unstaged_changes" = true ] && [ "$has_staged_changes" = false ]; then
            print_info "Stashing unstaged changes..."
            git stash push -m "Auto-stash before restack at $(date +%Y-%m-%d\ %H:%M:%S)"
            stashed=true
        fi

        # Sync trunk from remote before restacking
        print_info "Syncing trunk from remote..."
        local trunk_branch
        trunk_branch="$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo 'main')"
        if git worktree list --porcelain 2>/dev/null | grep -q "branch refs/heads/$trunk_branch"; then
            # trunk is checked out in another worktree — fetch and update the ref directly
            print_info "Trunk is checked out in another worktree; using git fetch to sync..."
            git fetch origin "$trunk_branch:$trunk_branch" --update-head-ok
        else
            gt repo sync --no-interactive
        fi

        # Run the restack
        gt stack restack
        restack_result=$?

        # Restore stashed changes if we stashed them
        if [ "$stashed" = true ] && [ $restack_result -eq 0 ]; then
            print_info "Restoring stashed changes..."
            git stash pop
        fi

        return $restack_result
    )

    if [ $? -eq 0 ]; then
        print_success "Stack rebased successfully"

        # Sync worktrees
        print_info "Syncing worktrees..."
        sync_all_worktrees
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

    # CRITICAL: If we're already in a worktree, we must create the new worktree
    # from the main repo root, not nested inside the current worktree.
    if is_in_worktree; then
        local main_repo
        main_repo=$(get_main_repo_path)
        print_info "Detected worktree context - creating from main repo at: $main_repo"
        cd "$main_repo"
    fi

    # Sanitize branch name for directory
    local description
    description=$(echo "$branch" | sed -E 's/^(feature|feat|bugfix|fix|hotfix|release|chore)\///')
    description=$(echo "$description" | tr '[:upper:]' '[:lower:]' | sed -E 's/[ _]/-/g' | sed -E 's/[^a-z0-9.-]//g' | sed -E 's/-+/-/g' | sed -E 's/^-|-$//g')

    local worktree_path=".trees/$description"

    print_info "Creating worktree for existing branch: $branch"
    print_info "Location: $worktree_path"

    # Ensure .trees exists (in main repo root)
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

    # Strip project-level permissions from copied .claude/settings.json
    # Global ~/.claude/settings.json has the correct broad permissions + deny list.
    # Project-level permissions cause prompting in worktrees when they contain
    # narrow allow-lists that don't cover all tool patterns.
    local wt_settings="$worktree_path/.claude/settings.json"
    if [ -f "$wt_settings" ] && command -v python3 &>/dev/null; then
        python3 -c "
import json, sys
with open('$wt_settings') as f:
    d = json.load(f)
if 'permissions' in d:
    del d['permissions']
    with open('$wt_settings', 'w') as f:
        json.dump(d, f, indent=2)
        f.write('\n')
    print('Stripped permissions from .claude/settings.json', file=sys.stderr)
" 2>&1 | while read -r line; do print_info "$line"; done || true
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
