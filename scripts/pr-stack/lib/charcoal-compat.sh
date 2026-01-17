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

    local repo_root
    repo_root=$(git rev-parse --show-toplevel 2>/dev/null)

    # Check for .gt directory (Charcoal's metadata)
    if [ -d "$repo_root/.gt" ]; then
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

    gt stack
}

# ============================================================================
# Metadata Sync Functions
# ============================================================================

# Sync Charcoal metadata to our .git/pr-stack-info format
# This ensures Azure DevOps scripts can still read stack information
# Returns: 0 on success, 1 on failure
sync_charcoal_to_native() {
    if ! charcoal_initialized; then
        return 1
    fi

    local repo_root
    repo_root=$(git rev-parse --show-toplevel 2>/dev/null)
    local stack_info_file="$repo_root/.git/pr-stack-info"

    # Get Charcoal's view of the stack
    local stack_json
    stack_json=$(gt stack --json 2>/dev/null)

    if [ -z "$stack_json" ]; then
        print_warning "Could not get Charcoal stack information"
        return 1
    fi

    # Parse Charcoal JSON and convert to our format
    # Format: branch:base:timestamp
    local temp_file="${stack_info_file}.tmp"

    # Use jq if available, otherwise fall back to basic parsing
    if command -v jq &> /dev/null; then
        echo "$stack_json" | jq -r '
            .branches[]? |
            select(.parent != null) |
            "\(.name):\(.parent):\(now | floor)"
        ' > "$temp_file" 2>/dev/null
    else
        # Basic fallback - parse gt stack output
        gt stack 2>/dev/null | grep -E '^\s*(├|└)' | while read -r line; do
            local branch
            branch=$(echo "$line" | sed 's/.*[├└]── //' | awk '{print $1}')
            if [ -n "$branch" ]; then
                local parent
                parent=$(git rev-parse --abbrev-ref "${branch}@{upstream}" 2>/dev/null | sed 's/origin\///')
                if [ -z "$parent" ]; then
                    parent="main"
                fi
                echo "${branch}:${parent}:$(date +%s)"
            fi
        done > "$temp_file"
    fi

    # Only update if we got data
    if [ -s "$temp_file" ]; then
        mv "$temp_file" "$stack_info_file"
        print_success "Synced Charcoal metadata to native format"
        return 0
    else
        rm -f "$temp_file"
        return 1
    fi
}

# Sync native .git/pr-stack-info to Charcoal
# This imports existing stacks into Charcoal
# Returns: 0 on success, 1 on failure
sync_native_to_charcoal() {
    if ! charcoal_available; then
        print_error "Charcoal not installed"
        return 1
    fi

    local repo_root
    repo_root=$(git rev-parse --show-toplevel 2>/dev/null)
    local stack_info_file="$repo_root/.git/pr-stack-info"

    if [ ! -f "$stack_info_file" ]; then
        print_info "No native stack info to import"
        return 0
    fi

    # Initialize Charcoal if needed
    if ! charcoal_initialized; then
        charcoal_init
    fi

    print_info "Importing existing stack to Charcoal..."

    # Read native format and track branches in Charcoal
    local imported=0
    while IFS=: read -r branch parent timestamp; do
        if [ -n "$branch" ] && [ -n "$parent" ]; then
            # Check if branch exists
            if git rev-parse --verify "$branch" > /dev/null 2>&1; then
                # Track branch in Charcoal
                if gt branch track "$branch" --parent "$parent" 2>/dev/null; then
                    print_info "Tracked: $branch -> $parent"
                    imported=$((imported + 1))
                fi
            fi
        fi
    done < "$stack_info_file"

    if [ $imported -gt 0 ]; then
        print_success "Imported $imported branch(es) to Charcoal"
    fi

    return 0
}

# Add a branch to both Charcoal and native metadata
# Args: $1 - branch name, $2 - parent branch
# Returns: 0 on success
sync_add_branch() {
    local branch=$1
    local parent=$2

    if [ -z "$branch" ] || [ -z "$parent" ]; then
        return 1
    fi

    local repo_root
    repo_root=$(git rev-parse --show-toplevel 2>/dev/null)
    local stack_info_file="$repo_root/.git/pr-stack-info"

    # Add to native format
    echo "${branch}:${parent}:$(date +%s)" >> "$stack_info_file"

    # Add to Charcoal if available
    if charcoal_initialized; then
        gt branch track "$branch" --parent "$parent" 2>/dev/null || true
    fi
}

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
export -f charcoal_init 2>/dev/null || true
export -f charcoal_create_branch 2>/dev/null || true
export -f charcoal_up 2>/dev/null || true
export -f charcoal_down 2>/dev/null || true
export -f charcoal_restack 2>/dev/null || true
export -f charcoal_stack_status 2>/dev/null || true
export -f sync_charcoal_to_native 2>/dev/null || true
export -f sync_native_to_charcoal 2>/dev/null || true
export -f sync_add_branch 2>/dev/null || true
export -f charcoal_or_fallback 2>/dev/null || true
