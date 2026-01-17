#!/usr/bin/env bash

# validation.sh - Shared validation functions for PR stacking scripts
# This library provides common validation logic used across all PR stacking scripts
# Source this file in other scripts: source "$(dirname "$0")/lib/validation.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_error() {
    echo -e "${RED}ERROR:${NC} $1" >&2
}

print_success() {
    echo -e "${GREEN}SUCCESS:${NC} $1"
}

print_info() {
    echo -e "${BLUE}INFO:${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

# ============================================================================
# Core Validation Functions
# ============================================================================

# Validate we're in a git repository
# Returns: 0 if valid, 1 if not
validate_git_repository() {
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not in a git repository"
        return 1
    fi
    return 0
}

# Validate branch name format
# Args: $1 - branch name
# Returns: 0 if valid, 1 if not
validate_branch_name() {
    local branch_name=$1

    if [ -z "$branch_name" ]; then
        print_error "Branch name cannot be empty"
        return 1
    fi

    if [[ ! $branch_name =~ ^[a-zA-Z0-9/_-]+$ ]]; then
        print_error "Invalid branch name: $branch_name"
        print_info "Branch names should only contain letters, numbers, slashes, hyphens, and underscores"
        return 1
    fi

    return 0
}

# Validate that a branch exists (local or remote)
# Args: $1 - branch name
# Returns: 0 if exists, 1 if not
validate_branch_exists() {
    local branch_name=$1

    if [ -z "$branch_name" ]; then
        print_error "Branch name cannot be empty"
        return 1
    fi

    if ! git rev-parse --verify "$branch_name" > /dev/null 2>&1; then
        print_error "Branch '$branch_name' does not exist"
        print_info "Available branches:"
        git branch -a | head -10
        return 1
    fi

    return 0
}

# Validate that a branch does NOT exist
# Args: $1 - branch name
# Returns: 0 if doesn't exist (valid), 1 if exists
validate_branch_not_exists() {
    local branch_name=$1

    if [ -z "$branch_name" ]; then
        print_error "Branch name cannot be empty"
        return 1
    fi

    if git rev-parse --verify "$branch_name" > /dev/null 2>&1; then
        print_error "Branch '$branch_name' already exists"
        print_info "Use a different name or delete the existing branch first"
        return 1
    fi

    return 0
}

# Validate that a remote branch exists
# Args: $1 - branch name, $2 - remote (default: origin)
# Returns: 0 if exists, 1 if not
validate_remote_branch_exists() {
    local branch_name=$1
    local remote=${2:-origin}

    if [ -z "$branch_name" ]; then
        print_error "Branch name cannot be empty"
        return 1
    fi

    if ! git ls-remote --exit-code --heads "$remote" "$branch_name" > /dev/null 2>&1; then
        print_warning "Branch '$branch_name' does not exist on remote '$remote'"
        return 1
    fi

    return 0
}

# Validate Azure CLI is installed
# Returns: 0 if installed, 1 if not
validate_azure_cli() {
    if ! command -v az &> /dev/null; then
        print_error "Azure CLI is not installed"
        print_info "Install it from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        return 1
    fi

    # Check if Azure DevOps extension is installed
    if ! az extension list 2>/dev/null | grep -q "azure-devops"; then
        print_warning "Azure DevOps extension not found"
        print_info "Installing Azure DevOps extension..."
        if az extension add --name azure-devops 2>/dev/null; then
            print_success "Azure DevOps extension installed"
        else
            print_error "Failed to install Azure DevOps extension"
            return 1
        fi
    fi

    return 0
}

# ============================================================================
# Stack-Specific Validation Functions
# ============================================================================

# Check if PR stacking is detected (opt-in detection)
# Returns: 0 if stacking is active, 1 if not
is_stacking_active() {
    local repo_root=$(git rev-parse --show-toplevel 2>/dev/null)
    # NOTE: Worktree-safe path resolution (in worktrees, .git is not a directory)
    local stack_info_file
    stack_info_file="$(git rev-parse --git-path pr-stack-info 2>/dev/null)"

    if [ -f "$stack_info_file" ] && [ -s "$stack_info_file" ]; then
        return 0
    fi

    return 1
}

# Validate stack info file exists
# Returns: 0 if exists, 1 if not
validate_stack_info_exists() {
    # NOTE: Worktree-safe path resolution (in worktrees, .git is not a directory)
    local stack_info_file
    stack_info_file="$(git rev-parse --git-path pr-stack-info 2>/dev/null)"

    if [ ! -f "$stack_info_file" ]; then
        print_error "No stack information found"
        print_info "Run: scripts/pr-stack/create-stack.sh to create stacked branches"
        return 1
    fi

    return 0
}

# Get the base branch for a given branch from stack info
# Args: $1 - branch name
# Returns: Echoes base branch name, or empty if not found
get_stack_base_branch() {
    local branch_name=$1
    # NOTE: Worktree-safe path resolution (in worktrees, .git is not a directory)
    local stack_info_file
    stack_info_file="$(git rev-parse --git-path pr-stack-info 2>/dev/null)"

    if [ ! -f "$stack_info_file" ]; then
        return 1
    fi

    local base_branch=""
    while IFS=: read -r branch target timestamp; do
        if [ "$branch" == "$branch_name" ]; then
            base_branch=$target
            break
        fi
    done < "$stack_info_file"

    echo "$base_branch"
}

# Validate that a branch is in sync with its base
# Args: $1 - branch name
# Returns: 0 if in sync or not stacking, 1 if out of sync
validate_stack_integrity() {
    local branch_name=$1

    if [ -z "$branch_name" ]; then
        print_error "Branch name cannot be empty"
        return 1
    fi

    # Only validate if stacking is active
    if ! is_stacking_active; then
        return 0
    fi

    local expected_base=$(get_stack_base_branch "$branch_name")

    if [ -z "$expected_base" ]; then
        # Branch not in stack, skip validation
        return 0
    fi

    # Validate base branch exists
    if ! validate_branch_exists "$expected_base" 2>/dev/null; then
        print_warning "Base branch '$expected_base' no longer exists"
        print_info "You may need to update the stack: scripts/pr-stack/update-stack.sh"
        return 1
    fi

    # Check if branch is ancestor of base
    if ! git merge-base --is-ancestor "$expected_base" "$branch_name" 2>/dev/null; then
        print_warning "Branch '$branch_name' is not in sync with base '$expected_base'"
        print_info "Consider running: git rebase $expected_base"
        print_info "Or update the stack: scripts/pr-stack/update-stack.sh"
        return 1
    fi

    return 0
}

# Validate PR target branch is correct for stacked PRs
# Args: $1 - source branch, $2 - target branch
# Returns: 0 if valid, 1 if potentially incorrect
validate_pr_target() {
    local source_branch=$1
    local target_branch=$2

    if [ -z "$source_branch" ] || [ -z "$target_branch" ]; then
        print_error "Source and target branches are required"
        return 1
    fi

    # Only validate if stacking is active
    if ! is_stacking_active; then
        return 0
    fi

    local expected_target=$(get_stack_base_branch "$source_branch")

    if [ -z "$expected_target" ]; then
        # Not a stacked branch, any target is fine
        return 0
    fi

    if [ "$target_branch" != "$expected_target" ]; then
        print_warning "PR target may be incorrect"
        print_info "Expected target: $expected_target"
        print_info "Provided target: $target_branch"
        print_info ""
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "PR creation cancelled"
            return 1
        fi
    fi

    return 0
}

# ============================================================================
# Helper Functions
# ============================================================================

# Get repository root directory
# Returns: Echoes absolute path to repo root
get_repo_root() {
    git rev-parse --show-toplevel 2>/dev/null
}

# Check if current directory is repository root
# Returns: 0 if at root, 1 if not
is_at_repo_root() {
    local current_dir=$(pwd)
    local repo_root=$(get_repo_root)

    if [ "$current_dir" == "$repo_root" ]; then
        return 0
    fi

    return 1
}

# Ensure we're at repository root (cd if needed)
# Returns: 0 if successful, 1 if not in repo
ensure_repo_root() {
    if ! validate_git_repository; then
        return 1
    fi

    local repo_root=$(get_repo_root)
    cd "$repo_root"
    return 0
}

# Check if there are uncommitted changes
# Returns: 0 if clean, 1 if dirty
is_working_directory_clean() {
    if [ -n "$(git status --porcelain)" ]; then
        return 1
    fi
    return 0
}

# Validate no uncommitted changes (warning only)
# Returns: Always 0 (non-blocking)
warn_if_dirty_working_directory() {
    if ! is_working_directory_clean; then
        print_warning "You have uncommitted changes"
        print_info "Consider committing or stashing before proceeding"
        echo ""
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Operation cancelled"
            return 1
        fi
    fi
    return 0
}

# ============================================================================
# Compound Validation Functions
# ============================================================================

# Validate common prerequisites for all scripts
# Returns: 0 if all valid, 1 if any fail
validate_common_prerequisites() {
    validate_git_repository || return 1
    ensure_repo_root || return 1
    return 0
}

# Validate prerequisites for creating a stacked branch
# Args: $1 - new branch name, $2 - base branch name
# Returns: 0 if all valid, 1 if any fail
validate_stack_create_prerequisites() {
    local new_branch=$1
    local base_branch=$2

    validate_common_prerequisites || return 1
    validate_branch_name "$new_branch" || return 1
    validate_branch_not_exists "$new_branch" || return 1
    validate_branch_exists "$base_branch" || return 1

    return 0
}

# Validate prerequisites for creating a PR
# Args: $1 - source branch, $2 - target branch
# Returns: 0 if all valid, 1 if any fail
validate_pr_create_prerequisites() {
    local source_branch=$1
    local target_branch=$2

    validate_common_prerequisites || return 1
    validate_azure_cli || return 1
    validate_branch_exists "$source_branch" || return 1
    validate_branch_exists "$target_branch" || return 1

    # Optional: warn about stack integrity (non-blocking)
    validate_stack_integrity "$source_branch" || true

    return 0
}

# Validate prerequisites for updating stack
# Returns: 0 if all valid, 1 if any fail
validate_stack_update_prerequisites() {
    validate_common_prerequisites || return 1
    validate_stack_info_exists || return 1

    return 0
}

# ============================================================================
# Export Functions (for bash < 4.2 compatibility)
# ============================================================================

# Make functions available to scripts that source this file
export -f print_error 2>/dev/null || true
export -f print_success 2>/dev/null || true
export -f print_info 2>/dev/null || true
export -f print_warning 2>/dev/null || true
export -f validate_git_repository 2>/dev/null || true
export -f validate_branch_name 2>/dev/null || true
export -f validate_branch_exists 2>/dev/null || true
export -f validate_branch_not_exists 2>/dev/null || true
export -f validate_remote_branch_exists 2>/dev/null || true
export -f validate_azure_cli 2>/dev/null || true
export -f is_stacking_active 2>/dev/null || true
export -f validate_stack_info_exists 2>/dev/null || true
export -f get_stack_base_branch 2>/dev/null || true
export -f validate_stack_integrity 2>/dev/null || true
export -f validate_pr_target 2>/dev/null || true
export -f get_repo_root 2>/dev/null || true
export -f is_at_repo_root 2>/dev/null || true
export -f ensure_repo_root 2>/dev/null || true
export -f is_working_directory_clean 2>/dev/null || true
export -f warn_if_dirty_working_directory 2>/dev/null || true
export -f validate_common_prerequisites 2>/dev/null || true
export -f validate_stack_create_prerequisites 2>/dev/null || true
export -f validate_pr_create_prerequisites 2>/dev/null || true
export -f validate_stack_update_prerequisites 2>/dev/null || true
