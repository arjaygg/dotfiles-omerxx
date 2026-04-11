#!/usr/bin/env bash
# clean-stack.sh - Remove a merged/stale branch, its worktree, and tmux window
# Usage: ./clean-stack.sh [branch] [--force]
#
# If no branch is given, uses current branch. Refuses to clean trunk or a dirty worktree
# unless --force is passed.

set -euo pipefail
trap 'echo "HOOK CRASH (clean-stack.sh line $LINENO): $BASH_COMMAND"; exit 1' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/validation.sh"
source "$SCRIPT_DIR/lib/charcoal-compat.sh"

print_usage() {
    echo "Usage: clean-stack.sh [branch] [--force]"
    echo ""
    echo "  branch    Branch to clean (default: current branch)"
    echo "  --force   Remove even if worktree has uncommitted changes"
}

BRANCH=""
FORCE=false

for arg in "$@"; do
    case "$arg" in
        --force|-f) FORCE=true ;;
        --help|-h)  print_usage; exit 0 ;;
        *)          BRANCH="$arg" ;;
    esac
done

# Default to current branch
if [ -z "$BRANCH" ]; then
    BRANCH=$(git branch --show-current 2>/dev/null || true)
    [ -z "$BRANCH" ] && { print_error "Cannot determine current branch"; exit 1; }
fi

# Refuse to clean trunk
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
if [ "$BRANCH" = "$DEFAULT_BRANCH" ] || [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
    print_error "Refusing to clean trunk branch: $BRANCH"
    exit 1
fi

print_info "Cleaning branch: $BRANCH"

# 1. Close tmux window if open
WINDOW_NAME=$(echo "$BRANCH" | sed -E 's/^(feature|feat|bugfix|fix|hotfix|release|chore)\///')
if [ -n "${TMUX:-}" ]; then
    TMUX_SESSION=$(tmux display-message -p '#S' 2>/dev/null || true)
    if [ -n "$TMUX_SESSION" ]; then
        # Use tmux select-window to check if window exists (more reliable than grep -Fxq)
        if tmux select-window -t "$TMUX_SESSION:$WINDOW_NAME" 2>/dev/null; then
            # Window exists — switch away before killing
            CURRENT_WINDOW=$(tmux display-message -p '#W' 2>/dev/null || true)
            if [ "$CURRENT_WINDOW" = "$WINDOW_NAME" ]; then
                tmux select-window -t "$TMUX_SESSION:$DEFAULT_BRANCH" 2>/dev/null || \
                tmux select-window -t "$TMUX_SESSION:main" 2>/dev/null || true
            fi
            tmux kill-window -t "$TMUX_SESSION:$WINDOW_NAME" 2>/dev/null || true
            print_info "Closed tmux window: $WINDOW_NAME"
        fi
    fi
fi

# 2. Remove worktree if it exists
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
WORKTREE_PATH="$REPO_ROOT/.trees/$WINDOW_NAME"

if [ -d "$WORKTREE_PATH" ]; then
    if [ "$FORCE" = false ]; then
        DIRTY=$(git -C "$WORKTREE_PATH" status --short 2>/dev/null || true)
        if [ -n "$DIRTY" ]; then
            print_error "Worktree has uncommitted changes: $WORKTREE_PATH"
            print_info "Use --force to remove anyway"
            exit 1
        fi
    fi
    git worktree remove "$WORKTREE_PATH" 2>/dev/null || git worktree remove --force "$WORKTREE_PATH"
    print_info "Removed worktree: $WORKTREE_PATH"
fi

# 3. Delete local branch (switch away first if on it)
CURRENT=$(git branch --show-current 2>/dev/null || true)
if [ "$CURRENT" = "$BRANCH" ]; then
    git checkout "$DEFAULT_BRANCH" 2>/dev/null || git checkout main 2>/dev/null || true
fi

if git branch --list "$BRANCH" | grep -q "$BRANCH"; then
    git branch -d "$BRANCH" 2>/dev/null || {
        if [ "$FORCE" = true ]; then
            git branch -D "$BRANCH"
        else
            print_warning "Branch not fully merged; use --force to delete anyway"
        fi
    }
    print_info "Deleted local branch: $BRANCH"
fi

print_success "Cleaned: $BRANCH"
