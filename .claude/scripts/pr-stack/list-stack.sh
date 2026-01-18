#!/usr/bin/env bash

# list-stack.sh - List all branches in the current PR stack
# Usage: ./list-stack.sh [--verbose] [--charcoal-only]

set -e

# Load charcoal-compat library
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/lib/charcoal-compat.sh" ]; then
    source "$SCRIPT_DIR/lib/charcoal-compat.sh"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

VERBOSE=false
CHARCOAL_ONLY=false

# Check for flags
for arg in "$@"; do
    if [ "$arg" == "--verbose" ] || [ "$arg" == "-v" ]; then
        VERBOSE=true
    elif [ "$arg" == "--charcoal-only" ] || [ "$arg" == "-c" ]; then
        CHARCOAL_ONLY=true
    fi
done

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}ERROR:${NC} Not in a git repository"
    exit 1
fi

# Robust Repo Root detection (handles worktrees correctly)
REPO_ROOT=$(git rev-parse --show-toplevel)

# Get absolute path to .git directory (works for both regular repos and worktrees)
if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    # Use --absolute-git-dir if available (Git 2.13+), fallback to resolving manually
    GIT_DIR=$(git rev-parse --absolute-git-dir 2>/dev/null || {
        rel_git_dir=$(git rev-parse --git-dir)
        cd "$rel_git_dir" && pwd
    })
else
    GIT_DIR=$(git rev-parse --git-dir)
fi

# Use absolute paths to avoid relative path issues when running from subdirectories
STACK_INFO_FILE="$GIT_DIR/pr-stack-info"
PR_CREATED_FILE="$GIT_DIR/pr-created"


echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                     PR STACK STATUS                        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Show Charcoal view if available
if type charcoal_initialized &>/dev/null && charcoal_initialized; then
    echo -e "${CYAN}Charcoal View (gt log short):${NC}"
    gt log short 2>/dev/null || echo "  (no stack tracked)"
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo ""

    # If charcoal-only flag, exit after showing Charcoal view
    if [ "$CHARCOAL_ONLY" = true ]; then
        exit 0
    fi

    echo -e "${CYAN}Azure DevOps View:${NC}"
    echo ""
fi

# Function to get PR status from Azure DevOps
get_pr_status() {
    local branch=$1
    local pr_id=$2

    if [ -z "$pr_id" ]; then
        echo "NOT CREATED"
        return
    fi

    # Try to get PR status (requires Azure CLI)
    if command -v az &> /dev/null; then
        STATUS=$(az repos pr show --id "$pr_id" \
            --organization "https://dev.azure.com/bofaz" \
            --query "status" -o tsv 2>/dev/null || echo "unknown")

        case "$STATUS" in
            active)
                echo -e "${YELLOW}ACTIVE${NC}"
                ;;
            completed)
                echo -e "${GREEN}MERGED${NC}"
                ;;
            abandoned)
                echo -e "${RED}ABANDONED${NC}"
                ;;
            *)
                echo -e "${CYAN}PR #$pr_id${NC}"
                ;;
        esac
    else
        echo -e "${CYAN}PR #$pr_id${NC}"
    fi
}

# Function to count commits ahead
get_commits_ahead() {
    local source=$1
    local target=$2

    if git rev-parse --verify "$source" > /dev/null 2>&1 && \
       git rev-parse --verify "$target" > /dev/null 2>&1; then
        git rev-list --count "$target..$source" 2>/dev/null || echo "?"
    else
        echo "?"
    fi
}

# Build a map of branches and their PRs
declare -A BRANCH_TO_PR
declare -A BRANCH_TO_TARGET
declare -A BRANCH_TO_TIME

# Read PR created file
if [ -f "$PR_CREATED_FILE" ]; then
    while IFS=: read -r branch target pr_id timestamp; do
        BRANCH_TO_PR["$branch"]=$pr_id
    done < "$PR_CREATED_FILE"
fi

# Read stack info file
if [ -f "$STACK_INFO_FILE" ]; then
    while IFS=: read -r branch target timestamp; do
        BRANCH_TO_TARGET["$branch"]=$target
        BRANCH_TO_TIME["$branch"]=$timestamp
    done < "$STACK_INFO_FILE"
else
    echo -e "${YELLOW}No stack information found${NC}"
    echo ""
    echo "Create your first stacked branch with:"
    echo "  ./scripts/pr-stack/create-stack.sh feature/my-feature main"
    exit 0
fi

# Build dependency tree
declare -A CHILDREN

for branch in "${!BRANCH_TO_TARGET[@]}"; do
    target="${BRANCH_TO_TARGET[$branch]}"
    CHILDREN["$target"]+="$branch "
done

# Function to print branch tree
print_branch_tree() {
    local branch=$1
    local prefix=$2
    local is_last=$3

    local pr_id="${BRANCH_TO_PR[$branch]}"
    local target="${BRANCH_TO_TARGET[$branch]}"
    local commits_ahead=$(get_commits_ahead "$branch" "$target")
    local pr_status=$(get_pr_status "$branch" "$pr_id")

    # Determine if branch exists locally and remotely
    local local_exists=$(git rev-parse --verify "$branch" 2>/dev/null && echo "✓" || echo "✗")
    local remote_exists=$(git ls-remote --heads origin "$branch" 2>/dev/null | grep -q "$branch" && echo "✓" || echo "✗")

    # Branch connector
    if [ "$is_last" = true ]; then
        echo -n -e "${prefix}└── "
    else
        echo -n -e "${prefix}├── "
    fi

    # Branch name
    if [ "$(git branch --show-current)" == "$branch" ]; then
        echo -n -e "${GREEN}${branch}${NC}"
    else
        echo -n -e "${CYAN}${branch}${NC}"
    fi

    # Add status indicators
    echo -n -e " [${commits_ahead} commits]"

    if [ -n "$pr_id" ]; then
        echo -n -e " → $pr_status"
    else
        echo -n -e " → ${YELLOW}NO PR${NC}"
    fi

    echo "" # newline

    # Verbose mode: show more details
    if [ "$VERBOSE" = true ]; then
        local next_prefix="$prefix"
        if [ "$is_last" = true ]; then
            next_prefix="$prefix    "
        else
            next_prefix="$prefix│   "
        fi

        echo -e "${next_prefix}    Local: $local_exists | Remote: $remote_exists"

        if [ -n "$target" ]; then
            echo -e "${next_prefix}    Base: ${target}"
        fi

        # Show latest commit
        if git rev-parse --verify "$branch" > /dev/null 2>&1; then
            local latest_commit=$(git log -1 --pretty=format:"%h - %s" "$branch" 2>/dev/null)
            echo -e "${next_prefix}    Latest: $latest_commit"
        fi

        echo ""
    fi

    # Recursively print children
    local children="${CHILDREN[$branch]}"
    if [ -n "$children" ]; then
        local child_array=($children)
        local child_count=${#child_array[@]}
        local i=0

        for child in "${child_array[@]}"; do
            i=$((i + 1))
            local child_is_last=false
            if [ $i -eq $child_count ]; then
                child_is_last=true
            fi

            local child_prefix="$prefix"
            if [ "$is_last" = true ]; then
                child_prefix="$prefix    "
            else
                child_prefix="$prefix│   "
            fi

            print_branch_tree "$child" "$child_prefix" $child_is_last
        done
    fi
}

# Find root branches (those that target main or have no dependencies in stack)
ROOT_BRANCHES=()
for branch in "${!BRANCH_TO_TARGET[@]}"; do
    target="${BRANCH_TO_TARGET[$branch]}"
    if [ "$target" == "main" ] || [ -z "${BRANCH_TO_TARGET[$target]}" ]; then
        ROOT_BRANCHES+=("$branch")
    fi
done

# Sort root branches by creation time
IFS=$'\n' ROOT_BRANCHES=($(sort -t: -k3 -n <<<"${ROOT_BRANCHES[*]}"))
unset IFS

# Print the tree
echo -e "${CYAN}main${NC}"

for branch in "${ROOT_BRANCHES[@]}"; do
    is_last=false
    if [ "$branch" == "${ROOT_BRANCHES[-1]}" ]; then
        is_last=true
    fi
    print_branch_tree "$branch" "" $is_last
done

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

# Summary statistics
TOTAL_BRANCHES=${#BRANCH_TO_TARGET[@]}
TOTAL_PRS=${#BRANCH_TO_PR[@]}
BRANCHES_WITHOUT_PR=$((TOTAL_BRANCHES - TOTAL_PRS))

echo -e "${BLUE}Summary:${NC}"
echo "  Total branches in stack: $TOTAL_BRANCHES"
echo "  PRs created: $TOTAL_PRS"
if [ $BRANCHES_WITHOUT_PR -gt 0 ]; then
    echo -e "  ${YELLOW}Branches without PRs: $BRANCHES_WITHOUT_PR${NC}"
fi

echo ""
echo -e "${BLUE}Commands:${NC}"
echo "  Create branch: ./scripts/stack create <branch> [base]"
echo "  Create PR:     ./scripts/stack pr <branch> [target]"
echo "  Update stack:  ./scripts/stack update [merged-branch]"
echo "  View status:   ./scripts/stack status"
if type charcoal_initialized &>/dev/null && charcoal_initialized; then
    echo ""
    echo -e "${CYAN}Charcoal Commands:${NC}"
    echo "  Navigate up:   ./scripts/stack up"
    echo "  Navigate down: ./scripts/stack down"
    echo "  Restack:       ./scripts/stack restack"
elif type charcoal_available &>/dev/null && ! charcoal_available; then
    echo ""
    echo -e "${YELLOW}Tip:${NC} Install Charcoal for easier navigation:"
    echo "  brew install danerwilliams/tap/charcoal"
fi
