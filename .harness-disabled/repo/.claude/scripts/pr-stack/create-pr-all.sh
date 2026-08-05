#!/usr/bin/env bash
# create-pr-all.sh - Create PRs for all unpublished branches in the stack
# Usage: ./create-pr-all.sh [--draft]
#
# Walks the Charcoal stack bottom-up and creates a GitHub PR for each branch
# that doesn't already have one open. Skips trunk and branches with existing PRs.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/validation.sh"
source "$SCRIPT_DIR/lib/charcoal-compat.sh"
source "$SCRIPT_DIR/lib/gh-account.sh"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
print_error()   { echo -e "${RED}ERROR:${NC} $1"; }
print_success() { echo -e "${GREEN}SUCCESS:${NC} $1"; }
print_info()    { echo -e "${BLUE}INFO:${NC} $1"; }
print_warning() { echo -e "${YELLOW}WARNING:${NC} $1"; }

print_usage() {
    echo -e "${BLUE}Usage:${NC}"
    echo "  ./create-pr-all.sh [--draft]"
    echo ""
    echo -e "${BLUE}Description:${NC}"
    echo "  Creates GitHub PRs for all branches in the Charcoal stack that don't"
    echo "  already have an open PR. Processes bottom-up to ensure correct base targeting."
    echo ""
    echo -e "${BLUE}Options:${NC}"
    echo "  --draft    Create all new PRs as drafts"
    echo ""
    echo -e "${BLUE}Examples:${NC}"
    echo "  ./create-pr-all.sh          # create PRs for unpublished stack branches"
    echo "  ./create-pr-all.sh --draft  # create all as draft PRs"
}

DRAFT=false
for arg in "$@"; do
    case "$arg" in
        --draft) DRAFT=true ;;
        --help|-h) print_usage; exit 0 ;;
    esac
done

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    print_error "Not in a git repository"; exit 1
fi

if ! command -v gh &>/dev/null; then
    print_error "gh CLI is not installed. Install: https://cli.github.com"; exit 1
fi

if ! charcoal_available; then
    print_error "Charcoal CLI (gt) is required. Install: brew install danerwilliams/tap/charcoal"
    exit 1
fi

if ! charcoal_initialized; then
    print_error "Charcoal not initialized. Run: stack init"
    exit 1
fi

gh_setup_git

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null \
    | sed 's@^refs/remotes/origin/@@' || echo "main")

# Build ordered list: trunk-first from `gt log --short`, then reverse for bottom-up processing.
# gt log --short outputs: trunk at top, leaves at bottom. We want to create PRs leaf→trunk
# so each PR's base already has a PR when we create the next one up the stack.
STACK_BRANCHES=()
while IFS= read -r line; do
    branch=$(echo "$line" | awk '{print $1}')
    [ -z "$branch" ] && continue
    [ "$branch" = "$DEFAULT_BRANCH" ] && continue
    STACK_BRANCHES+=("$branch")
done < <(gt log --short 2>/dev/null | tail -r 2>/dev/null || gt log --short 2>/dev/null | awk '{a[NR]=$0} END{for(i=NR;i>=1;i--) print a[i]}')

if [ ${#STACK_BRANCHES[@]} -eq 0 ]; then
    print_info "No stacked branches found. Nothing to do."
    exit 0
fi

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          CREATE ALL STACK PRs                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""
print_info "Found ${#STACK_BRANCHES[@]} branches to process"
[ "$DRAFT" = true ] && print_info "Mode: draft PRs"
echo ""

CREATED=0
SKIPPED=0
FAILED=0

declare -A PR_URLS

for branch in "${STACK_BRANCHES[@]}"; do
    # Check if PR already exists
    existing_pr=$(GH_TOKEN=$(gh_token_for_remote) gh pr view "$branch" \
        --json number,url,state -q 'select(.state == "OPEN") | "#\(.number) \(.url)"' 2>/dev/null || true)

    if [ -n "$existing_pr" ]; then
        print_info "  SKIP  $branch — PR already open: $existing_pr"
        PR_URLS["$branch"]="$existing_pr"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    parent=$(charcoal_get_parent "$branch" 2>/dev/null || true)
    parent="${parent:-$DEFAULT_BRANCH}"

    printf "  CREATE  %-40s → base: %s\n" "$branch" "$parent"

    DRAFT_FLAG=""
    [ "$DRAFT" = true ] && DRAFT_FLAG="--draft"

    if pr_url=$("$SCRIPT_DIR/create-pr.sh" "$branch" "$parent" "" $DRAFT_FLAG 2>&1 | tail -1); then
        PR_URLS["$branch"]="$pr_url"
        print_success "    Created: $pr_url"
        CREATED=$((CREATED + 1))
    else
        print_error "    Failed to create PR for $branch"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo ""
print_info "Summary: $CREATED created, $SKIPPED skipped (existing), $FAILED failed"
echo ""

if [ ${#PR_URLS[@]} -gt 0 ]; then
    echo -e "${BLUE}PR Stack:${NC}"
    for branch in "${STACK_BRANCHES[@]}"; do
        url="${PR_URLS[$branch]:-}"
        if [ -n "$url" ]; then
            printf "  %-40s %s\n" "$branch" "$url"
        fi
    done
fi

[ "$FAILED" -gt 0 ] && exit 1
exit 0
