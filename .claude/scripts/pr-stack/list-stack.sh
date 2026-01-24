#!/usr/bin/env bash

# list-stack.sh - List all branches in the current PR stack
# Usage: ./list-stack.sh [--verbose] [--charcoal-only]

set -e

# Load libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/charcoal-compat.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

VERBOSE=false
CHARCOAL_ONLY=false
SHOW_CI=false

# Check for flags
for arg in "$@"; do
    if [ "$arg" == "--verbose" ] || [ "$arg" == "-v" ]; then
        VERBOSE=true
    elif [ "$arg" == "--charcoal-only" ] || [ "$arg" == "-c" ]; then
        CHARCOAL_ONLY=true
    elif [ "$arg" == "--ci" ] || [ "$arg" == "--builds" ]; then
        SHOW_CI=true
    fi
done

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}ERROR:${NC} Not in a git repository"
    exit 1
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                     PR STACK STATUS                        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Determine trunk branch
DEFAULT_BRANCH="$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")"

# Require Charcoal for stack relationships (no local tracking fallback)
if ! charcoal_available; then
    echo -e "${RED}ERROR:${NC} Charcoal (gt) is required"
    echo "Install: brew install danerwilliams/tap/charcoal"
    exit 1
fi

if ! charcoal_initialized; then
    echo -e "${RED}ERROR:${NC} Charcoal is not initialized in this repository"
    echo "Run: ~/.claude/scripts/stack init"
    exit 1
fi

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

# Function to get PR status from Azure DevOps (no local tracking)
# Prints: "→ ACTIVE (PR #123)" or "→ NO PR"
get_pr_status() {
    local branch=$1

    if ! command -v az &> /dev/null; then
        echo -e "→ ${YELLOW}NO PR${NC}"
        return
    fi

    local pr_id=""
    pr_id="$(az repos pr list \
        --organization "https://dev.azure.com/bofaz" \
        --status active \
        --source-branch "refs/heads/$branch" \
        --query "[0].pullRequestId" -o tsv 2>/dev/null || true)"

    if [ -z "$pr_id" ] || [ "$pr_id" = "null" ]; then
        echo -e "→ ${YELLOW}NO PR${NC}"
        return
    fi

    echo -e "→ ${YELLOW}ACTIVE${NC} ${CYAN}(PR #$pr_id)${NC}"
}

# Function to get CI/CD build status for a branch
get_build_status() {
    local branch=$1

    if [ "$SHOW_CI" != "true" ]; then
        echo ""
        return
    fi

    # Try to get build status (requires Azure CLI)
    if command -v az &> /dev/null; then
        local status
        status=$(az pipelines build list \
            --organization "https://dev.azure.com/bofaz" \
            --branch "$branch" \
            --top 1 \
            --query "[0].result" -o tsv 2>/dev/null || echo "unknown")

        case "$status" in
            succeeded)
                echo -e " ${GREEN}✓ Build${NC}"
                ;;
            failed)
                echo -e " ${RED}✗ Build${NC}"
                ;;
            canceled)
                echo -e " ${YELLOW}⊘ Build${NC}"
                ;;
            partiallySucceeded)
                echo -e " ${YELLOW}⚠ Build${NC}"
                ;;
            inProgress|notStarted)
                echo -e " ${CYAN}⟳ Build${NC}"
                ;;
            ""|null|unknown)
                echo ""
                ;;
            *)
                echo ""
                ;;
        esac
    else
        echo ""
    fi
}

declare -A BRANCH_TO_TARGET

# Build stack relationships from Charcoal (single source of truth)
while IFS= read -r branch; do
    [ -n "$branch" ] || continue
    parent="$(charcoal_get_parent "$branch" 2>/dev/null || true)"
    if [ -n "$parent" ]; then
        BRANCH_TO_TARGET["$branch"]="$parent"
    fi
done < <(git branch --format='%(refname:short)')

if [ ${#BRANCH_TO_TARGET[@]} -eq 0 ]; then
    echo -e "${YELLOW}No branches are tracked in Charcoal yet.${NC}"
    echo ""
    echo "Create your first stacked branch with:"
    echo "  ./scripts/stack create feature/my-feature $DEFAULT_BRANCH --worktree"
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

    local target="${BRANCH_TO_TARGET[$branch]}"
    local commits_ahead=$(get_commits_ahead "$branch" "$target")
    local pr_status
    pr_status=$(get_pr_status "$branch")

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

    echo -n -e " $pr_status"

    # Add build status if CI flag is set
    local build_status
    build_status=$(get_build_status "$branch")
    if [ -n "$build_status" ]; then
        echo -n -e "$build_status"
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

# Find root branches (those that target trunk or whose parent isn't tracked)
ROOT_BRANCHES=()
for branch in "${!BRANCH_TO_TARGET[@]}"; do
    target="${BRANCH_TO_TARGET[$branch]}"
    if [ "$target" == "$DEFAULT_BRANCH" ] || [ -z "${BRANCH_TO_TARGET[$target]}" ]; then
        ROOT_BRANCHES+=("$branch")
    fi
done

# Sort roots by name for stable output
IFS=$'\n' ROOT_BRANCHES=($(sort <<<"${ROOT_BRANCHES[*]}"))
unset IFS

# Print the tree
echo -e "${CYAN}${DEFAULT_BRANCH}${NC}"

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

echo -e "${BLUE}Summary:${NC}"
echo "  Total branches in stack: $TOTAL_BRANCHES"

echo ""
echo -e "${BLUE}Commands:${NC}"
echo "  Create branch: ./scripts/stack create <branch> [base]"
echo "  Create PR:     ./scripts/stack pr <branch> [target]"
echo "  Update stack:  ./scripts/stack update [merged-branch]"
echo "  View status:   ./scripts/stack status"
echo ""
echo -e "${CYAN}Charcoal Commands:${NC}"
echo "  Navigate up:   ./scripts/stack up"
echo "  Navigate down: ./scripts/stack down"
echo "  Restack:       ./scripts/stack restack"
