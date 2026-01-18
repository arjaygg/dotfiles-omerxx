#!/usr/bin/env bash

# charcoal-compat.sh - Charcoal CLI compatibility layer for PR stacking
# Provides detection, fallback logic, and metadata sync between Charcoal and native scripts
#
# Charcoal (gt) is an open-source tool for managing stacked PRs:
# https://github.com/danerwilliams/charcoal
#
# This library enables hybrid workflows:
# - Use Charcoal for branch operations when available (better UX)
# - Fall back to native scripts when Charcoal is not installed
# - Keep metadata in sync for Azure DevOps compatibility

# Source validation library for common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/validation.sh" ]; then
    source "$SCRIPT_DIR/validation.sh"
fi

# ============================================================================
# Detection Functions
# ============================================================================

# Check if Charcoal CLI is installed
# Returns: 0 if installed, 1 if not
charcoal_available() {
    command -v gt &> /dev/null
}

# Check if Charcoal is initialized in current repo
# Returns: 0 if initialized, 1 if not
charcoal_initialized() {
    if ! charcoal_available; then
        return 1
    fi

    local git_dir
    # Use --git-common-dir to work in both main repo and worktrees
    git_dir=$(git rev-parse --git-common-dir 2>/dev/null || git rev-parse --git-dir 2>/dev/null)

    # Check for Graphite's config file (Charcoal/Graphite stores metadata in .git/)
    # Note: Graphite is the new name for Charcoal, uses .graphite_repo_config
    if [ -f "$git_dir/.graphite_repo_config" ]; then
        return 0
    fi

    return 1
}

# Get Charcoal version if installed
# Returns: Version string or empty
charcoal_version() {
    if charcoal_available; then
        gt --version 2>/dev/null | head -1
    fi
}

# Get parent branch for a given branch
# Args: $1 - branch name (default: current branch)
# Returns: parent branch name or empty
charcoal_get_parent() {
    local branch=${1:-$(git branch --show-current)}

    if ! charcoal_initialized; then
        return 1
    fi

    # Use gt branch info to get parent
    # Output format: "Parent: <branch-name>"
    gt branch info "$branch" 2>/dev/null | grep "^Parent:" | sed 's/^Parent: //' | tr -d ' ' || true
}

# Get child branches for a given branch
# Args: $1 - branch name (default: current branch)
# Returns: space-separated list of child branch names
charcoal_get_children() {
    local branch=${1:-$(git branch --show-current)}

    if ! charcoal_initialized; then
        return 1
    fi

    # Use gt log short to parse the tree and find children
    # Look for branches that have this branch as parent
    local all_branches
    all_branches=$(git branch --format='%(refname:short)')

    local children=""
    while IFS= read -r child_candidate; do
        if [ -z "$child_candidate" ]; then
            continue
        fi

        local parent
        parent=$(charcoal_get_parent "$child_candidate" 2>/dev/null)

        if [ "$parent" = "$branch" ]; then
            children="$children $child_candidate"
        fi
    done <<< "$all_branches"

    echo "$children" | xargs
}

# ============================================================================
# Charcoal Command Wrappers
# ============================================================================

# Initialize Charcoal in the current repository
# Args: $1 - trunk branch (default: main)
# Returns: 0 on success, 1 on failure
charcoal_init() {
    local trunk=${1:-main}

    if ! charcoal_available; then
        print_error "Charcoal is not installed"
        print_info "Install with: brew install danerwilliams/tap/charcoal"
        return 1
    fi

    if charcoal_initialized; then
        print_info "Charcoal already initialized"
        return 0
    fi

    print_info "Initializing Charcoal with trunk: $trunk"
    gt repo init --trunk "$trunk"
}

# Create a new branch using Charcoal
# Args: $1 - branch name
# Returns: 0 on success, 1 on failure
charcoal_create_branch() {
    local branch_name=$1

    if [ -z "$branch_name" ]; then
        print_error "Branch name required"
        return 1
    fi

    if ! charcoal_initialized; then
        print_error "Charcoal not initialized. Run: ./scripts/stack init"
        return 1
    fi

    gt branch create "$branch_name"
}

# Navigate to parent branch
# Returns: 0 on success, 1 on failure
charcoal_up() {
    if ! charcoal_initialized; then
        print_error "Charcoal not initialized"
        return 1
    fi

    gt up
}

# Navigate to child branch
# Args: $1 - child index (optional, defaults to first child)
# Returns: 0 on success, 1 on failure
charcoal_down() {
    local child_index=${1:-0}

    if ! charcoal_initialized; then
        print_error "Charcoal not initialized"
        return 1
    fi

    gt down "$child_index"
}

# Restack all branches (rebase stack)
# Returns: 0 on success, 1 on failure
charcoal_restack() {
    if ! charcoal_initialized; then
        print_error "Charcoal not initialized"
        return 1
    fi

    gt restack
}

# Show Charcoal stack status
# Returns: 0 on success, 1 on failure
charcoal_stack_status() {
    if ! charcoal_initialized; then
        return 1
    fi

    gt log short
}

# ============================================================================
# Metadata Sync Functions
# ============================================================================
# NOTE: Legacy sync functions removed. We now use Charcoal exclusively.
# The pr-stack-info file is no longer maintained or used.

# ============================================================================
# Fallback Logic
# ============================================================================

# Execute a command with Charcoal if available, otherwise use fallback
# Args: $1 - command type (create, up, down, restack, status)
#       $@ - additional arguments
# Returns: result of command execution
charcoal_or_fallback() {
    local cmd_type=$1
    shift

    case "$cmd_type" in
        create)
            if charcoal_initialized; then
                charcoal_create_branch "$@"
            else
                return 1  # Signal to use native script
            fi
            ;;
        up)
            if charcoal_initialized; then
                charcoal_up "$@"
            else
                print_error "Navigation requires Charcoal. Install with: brew install danerwilliams/tap/charcoal"
                return 1
            fi
            ;;
        down)
            if charcoal_initialized; then
                charcoal_down "$@"
            else
                print_error "Navigation requires Charcoal. Install with: brew install danerwilliams/tap/charcoal"
                return 1
            fi
            ;;
        restack)
            if charcoal_initialized; then
                charcoal_restack "$@"
            else
                print_info "Charcoal not available, using native update-stack.sh"
                return 1  # Signal to use native script
            fi
            ;;
        status)
            if charcoal_initialized; then
                charcoal_stack_status "$@"
            fi
            # Always return success - native status can supplement
            return 0
            ;;
        *)
            print_error "Unknown command type: $cmd_type"
            return 1
            ;;
    esac
}

# ============================================================================
# Export Functions
# ============================================================================

export -f charcoal_available 2>/dev/null || true
export -f charcoal_initialized 2>/dev/null || true
export -f charcoal_version 2>/dev/null || true
export -f charcoal_get_parent 2>/dev/null || true
export -f charcoal_get_children 2>/dev/null || true
export -f charcoal_init 2>/dev/null || true
export -f charcoal_create_branch 2>/dev/null || true
export -f charcoal_up 2>/dev/null || true
export -f charcoal_down 2>/dev/null || true
export -f charcoal_restack 2>/dev/null || true
export -f charcoal_stack_status 2>/dev/null || true
export -f charcoal_or_fallback 2>/dev/null || true
