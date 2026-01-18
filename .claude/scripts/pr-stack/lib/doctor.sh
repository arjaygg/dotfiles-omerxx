#!/usr/bin/env bash

# doctor.sh - Stack integrity checks and auto-repair
# Validates stack health and detects common issues

# Source dependencies
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/validation.sh"
source "$SCRIPT_DIR/charcoal-compat.sh"

# Issue tracking
declare -a DOCTOR_ERRORS
declare -a DOCTOR_WARNINGS
declare -a DOCTOR_FIXES

# ============================================================================
# Check Functions
# ============================================================================

# Check: Branch exists in Charcoal but not in git
check_charcoal_branch_exists() {
    if ! charcoal_initialized; then
        return 0
    fi

    # Get all local branches
    local all_branches
    all_branches=$(git branch --format='%(refname:short)')

    # Check each branch that has a parent (i.e., tracked in Charcoal)
    while IFS= read -r branch; do
        if [ -z "$branch" ]; then
            continue
        fi

        # Check if this branch has a parent in Charcoal
        local parent
        parent=$(charcoal_get_parent "$branch" 2>/dev/null)

        # If it has a parent but the branch doesn't exist, it's an error
        if [ -n "$parent" ] && ! git rev-parse --verify "$branch" &>/dev/null; then
            DOCTOR_ERRORS+=("Branch '$branch' tracked in Charcoal but doesn't exist in git")
            DOCTOR_FIXES+=("gt branch untrack $branch")
        fi
    done <<< "$all_branches"
}

# Check: Branch exists in native metadata but not in git
check_native_branch_exists() {
    local stack_info_file
    stack_info_file="$(git rev-parse --git-path pr-stack-info 2>/dev/null)"

    if [ ! -f "$stack_info_file" ]; then
        return 0
    fi

    while IFS=: read -r branch target timestamp; do
        if [ -n "$branch" ] && ! git rev-parse --verify "$branch" &>/dev/null; then
            DOCTOR_ERRORS+=("Branch '$branch' in stack-info but doesn't exist in git")
            DOCTOR_FIXES+=("Remove '$branch' from $stack_info_file")
        fi
    done < "$stack_info_file"
}

# Check: PR target doesn't match Charcoal parent
check_pr_target_mismatch() {
    if ! charcoal_initialized; then
        return 0
    fi

    local pr_created_file
    pr_created_file="$(git rev-parse --git-path pr-created 2>/dev/null)"

    if [ ! -f "$pr_created_file" ]; then
        return 0
    fi

    while IFS=: read -r branch target pr_id timestamp; do
        if [ -z "$branch" ] || [ -z "$target" ] || [ -z "$pr_id" ]; then
            continue
        fi

        # Get Charcoal parent using helper function
        local charcoal_parent
        charcoal_parent=$(charcoal_get_parent "$branch" 2>/dev/null)

        if [ -n "$charcoal_parent" ] && [ "$target" != "$charcoal_parent" ]; then
            DOCTOR_WARNINGS+=("PR #$pr_id for '$branch' targets '$target' but Charcoal parent is '$charcoal_parent'")
            DOCTOR_FIXES+=("Update PR #$pr_id target to '$charcoal_parent' or re-track branch")
        fi
    done < "$pr_created_file"
}

# Check: Worktree exists but branch deleted
check_orphan_worktrees() {
    local worktrees
    worktrees=$(git worktree list --porcelain 2>/dev/null)

    local current_path=""
    local current_branch=""

    while IFS= read -r line; do
        if [[ "$line" == worktree\ * ]]; then
            current_path="${line#worktree }"
        elif [[ "$line" == branch\ * ]]; then
            current_branch="${line#branch refs/heads/}"
        elif [[ "$line" == "" ]] && [ -n "$current_path" ]; then
            # Check if branch still exists
            if [ -n "$current_branch" ] && ! git rev-parse --verify "$current_branch" &>/dev/null; then
                DOCTOR_WARNINGS+=("Worktree at '$current_path' references deleted branch '$current_branch'")
                DOCTOR_FIXES+=("git worktree remove '$current_path' --force")
            fi
            current_path=""
            current_branch=""
        fi
    done <<< "$worktrees"
}

# Check: Branch is out of sync with parent (has conflicts hiding)
check_branch_sync() {
    local stack_info_file
    stack_info_file="$(git rev-parse --git-path pr-stack-info 2>/dev/null)"

    if [ ! -f "$stack_info_file" ]; then
        return 0
    fi

    while IFS=: read -r branch parent timestamp; do
        if [ -z "$branch" ] || [ -z "$parent" ]; then
            continue
        fi

        # Check if both branches exist
        if ! git rev-parse --verify "$branch" &>/dev/null || ! git rev-parse --verify "$parent" &>/dev/null; then
            continue
        fi

        # Check if branch contains parent
        if ! git merge-base --is-ancestor "$parent" "$branch" 2>/dev/null; then
            # Check how far behind
            local behind
            behind=$(git rev-list --count "$branch..$parent" 2>/dev/null || echo "?")

            DOCTOR_WARNINGS+=("Branch '$branch' is $behind commit(s) behind parent '$parent' - may have merge conflicts")
            DOCTOR_FIXES+=("git checkout $branch && git rebase $parent")
        fi
    done < "$stack_info_file"
}

# Check: Remote branch missing (not pushed)
check_remote_branches() {
    local stack_info_file
    stack_info_file="$(git rev-parse --git-path pr-stack-info 2>/dev/null)"

    if [ ! -f "$stack_info_file" ]; then
        return 0
    fi

    while IFS=: read -r branch parent timestamp; do
        if [ -z "$branch" ]; then
            continue
        fi

        # Check if branch exists locally
        if ! git rev-parse --verify "$branch" &>/dev/null; then
            continue
        fi

        # Check if pushed to remote
        if ! git ls-remote --exit-code --heads origin "$branch" &>/dev/null; then
            DOCTOR_WARNINGS+=("Branch '$branch' exists locally but not pushed to origin")
            DOCTOR_FIXES+=("git push -u origin $branch")
        fi
    done < "$stack_info_file"
}

# Check: Charcoal and native metadata out of sync
check_metadata_sync() {
    if ! charcoal_initialized; then
        return 0
    fi

    local stack_info_file
    stack_info_file="$(git rev-parse --git-path pr-stack-info 2>/dev/null)"

    if [ ! -f "$stack_info_file" ]; then
        return 0
    fi

    # Get branches from native
    local native_branches=()
    while IFS=: read -r branch target timestamp; do
        if [ -n "$branch" ]; then
            native_branches+=("$branch")
        fi
    done < "$stack_info_file"

    # Get branches from Charcoal (all branches with parents)
    local charcoal_branches=()
    local all_branches
    all_branches=$(git branch --format='%(refname:short)')

    while IFS= read -r branch; do
        if [ -z "$branch" ]; then
            continue
        fi

        # Check if this branch has a parent (tracked by Charcoal)
        local parent
        parent=$(charcoal_get_parent "$branch" 2>/dev/null)

        if [ -n "$parent" ]; then
            charcoal_branches+=("$branch")
        fi
    done <<< "$all_branches"

    # Check for branches in native but not Charcoal
    for branch in "${native_branches[@]}"; do
        local found=false
        for cb in "${charcoal_branches[@]}"; do
            if [ "$branch" == "$cb" ]; then
                found=true
                break
            fi
        done
        if [ "$found" == false ]; then
            DOCTOR_WARNINGS+=("Branch '$branch' in native metadata but not tracked by Charcoal")
            DOCTOR_FIXES+=("gt branch track $branch")
        fi
    done
}

# Check: PR exists but branch was force-pushed (PR may be stale)
check_pr_freshness() {
    local pr_created_file
    pr_created_file="$(git rev-parse --git-path pr-created 2>/dev/null)"

    if [ ! -f "$pr_created_file" ]; then
        return 0
    fi

    # Only do this check if we have `az` CLI
    if ! command -v az &>/dev/null; then
        return 0
    fi

    while IFS=: read -r branch target pr_id timestamp; do
        if [ -z "$pr_id" ] || [ -z "$branch" ]; then
            continue
        fi

        # Check if branch exists
        if ! git rev-parse --verify "$branch" &>/dev/null; then
            continue
        fi

        # Get local branch HEAD
        local local_head
        local_head=$(git rev-parse "$branch" 2>/dev/null)

        # Get remote branch HEAD
        local remote_head
        remote_head=$(git ls-remote origin "$branch" 2>/dev/null | awk '{print $1}')

        if [ -n "$local_head" ] && [ -n "$remote_head" ] && [ "$local_head" != "$remote_head" ]; then
            DOCTOR_WARNINGS+=("Branch '$branch' local HEAD differs from remote - PR #$pr_id may be stale")
            DOCTOR_FIXES+=("git push -f origin $branch")
        fi
    done < "$pr_created_file"
}

# ============================================================================
# Main Doctor Function
# ============================================================================

# Run all checks
run_all_checks() {
    DOCTOR_ERRORS=()
    DOCTOR_WARNINGS=()
    DOCTOR_FIXES=()

    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    STACK DOCTOR                            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Running stack integrity checks...${NC}"
    echo ""

    # Run checks
    echo -n "  Checking Charcoal branch references... "
    check_charcoal_branch_exists
    echo -e "${GREEN}done${NC}"

    echo -n "  Checking native metadata consistency... "
    check_native_branch_exists
    echo -e "${GREEN}done${NC}"

    echo -n "  Checking PR target alignment... "
    check_pr_target_mismatch
    echo -e "${GREEN}done${NC}"

    echo -n "  Checking for orphan worktrees... "
    check_orphan_worktrees
    echo -e "${GREEN}done${NC}"

    echo -n "  Checking branch sync status... "
    check_branch_sync
    echo -e "${GREEN}done${NC}"

    echo -n "  Checking remote branches... "
    check_remote_branches
    echo -e "${GREEN}done${NC}"

    echo -n "  Checking metadata synchronization... "
    check_metadata_sync
    echo -e "${GREEN}done${NC}"

    echo -n "  Checking PR freshness... "
    check_pr_freshness
    echo -e "${GREEN}done${NC}"

    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo ""

    # Report results
    local error_count=${#DOCTOR_ERRORS[@]}
    local warning_count=${#DOCTOR_WARNINGS[@]}

    if [ "$error_count" -eq 0 ] && [ "$warning_count" -eq 0 ]; then
        echo -e "${GREEN}✓ All checks passed! Stack is healthy.${NC}"
        return 0
    fi

    # Show errors
    if [ "$error_count" -gt 0 ]; then
        echo -e "${RED}Errors (${error_count}):${NC}"
        for err in "${DOCTOR_ERRORS[@]}"; do
            echo -e "  ${RED}✗${NC} $err"
        done
        echo ""
    fi

    # Show warnings
    if [ "$warning_count" -gt 0 ]; then
        echo -e "${YELLOW}Warnings (${warning_count}):${NC}"
        for warn in "${DOCTOR_WARNINGS[@]}"; do
            echo -e "  ${YELLOW}⚠${NC} $warn"
        done
        echo ""
    fi

    # Show suggested fixes
    if [ ${#DOCTOR_FIXES[@]} -gt 0 ]; then
        echo -e "${CYAN}Suggested fixes:${NC}"
        for fix in "${DOCTOR_FIXES[@]}"; do
            echo "  $fix"
        done
        echo ""
    fi

    echo -e "${BLUE}Summary:${NC} $error_count error(s), $warning_count warning(s)"

    if [ "$error_count" -gt 0 ]; then
        return 1
    fi

    return 0
}

# Run checks and optionally auto-fix
# Args: $1 - "--fix" to auto-repair
doctor_main() {
    local auto_fix=false

    if [ "$1" == "--fix" ]; then
        auto_fix=true
    fi

    run_all_checks
    local check_result=$?

    if [ "$auto_fix" == true ] && [ ${#DOCTOR_FIXES[@]} -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}Auto-fix is not yet implemented for safety.${NC}"
        echo "Please run the suggested fixes manually."
    fi

    return $check_result
}

# Export functions
export -f check_charcoal_branch_exists 2>/dev/null || true
export -f check_native_branch_exists 2>/dev/null || true
export -f check_pr_target_mismatch 2>/dev/null || true
export -f check_orphan_worktrees 2>/dev/null || true
export -f check_branch_sync 2>/dev/null || true
export -f check_remote_branches 2>/dev/null || true
export -f check_metadata_sync 2>/dev/null || true
export -f check_pr_freshness 2>/dev/null || true
export -f run_all_checks 2>/dev/null || true
export -f doctor_main 2>/dev/null || true
