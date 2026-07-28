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
# Resolve via the common git dir, not --show-toplevel: when this script runs
# from inside the worktree being cleaned, --show-toplevel returns that
# worktree's own root, producing a bogus nested .trees/<name>/.trees/<name>
# path and silently skipping worktree removal.
REPO_ROOT=$(cd "$(git rev-parse --git-common-dir 2>/dev/null || echo .git)/.." && pwd)

# Ask git which worktree has this branch checked out rather than rebuilding the
# path from the branch name. WINDOW_NAME strips a fixed prefix list
# (feature|feat|bugfix|fix|hotfix|release|chore) while `stack create` sanitizes
# by removing the slash, so any other prefix — docs/, test/, perf/, ci/ — yielded
# `.trees/docs/<name>`, which never exists. Worktree removal was then skipped
# silently and the branch was still checked out when the delete ran.
WORKTREE_PATH=""
_wt=""
while IFS= read -r _line; do
    case "$_line" in
        "worktree "*) _wt="${_line#worktree }" ;;
        "branch refs/heads/"*)
            if [ "${_line#branch refs/heads/}" = "$BRANCH" ]; then
                WORKTREE_PATH="$_wt"
                break
            fi
            ;;
    esac
done < <(git worktree list --porcelain 2>/dev/null)

# Fall back to the derived path for a directory git no longer tracks as a worktree.
if [ -z "$WORKTREE_PATH" ]; then
    WORKTREE_PATH="$REPO_ROOT/.trees/$WINDOW_NAME"
fi

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

    # If we were running from inside the worktree just removed, our cwd is now
    # gone, and every subsequent git call would fail with "fatal: Unable to
    # read current working directory" — silently skipping branch deletion.
    if [ ! -d "$PWD" ]; then
        cd "$REPO_ROOT"
    fi
fi

# 3. Delete local branch (switch away first if on it)
CURRENT=$(git branch --show-current 2>/dev/null || true)
if [ "$CURRENT" = "$BRANCH" ]; then
    git checkout "$DEFAULT_BRANCH" 2>/dev/null || git checkout main 2>/dev/null || true
fi

# `git branch -d` only accepts a branch whose tip is an ancestor of the default
# branch. `gh pr merge --rebase` and `--squash` both rewrite the commits, so a
# fully-shipped branch is never an ancestor and -d always refuses — which made
# every rebase-merged branch look unmerged and silently skipped the delete.
# Two rebase/squash-aware fallbacks before giving up:
#   1. git cherry — every commit has an equivalent patch upstream (rebase; also
#      survives the default branch advancing afterwards)
#   2. identical trees — the content matches exactly (squash, while the default
#      branch has not yet moved past the merge)
branch_content_landed() {
    local branch="$1" base="$2"
    git rev-parse --verify --quiet "$base" >/dev/null 2>&1 || return 1
    if [ -z "$(git cherry "$base" "$branch" 2>/dev/null | grep '^+')" ]; then
        return 0
    fi
    git diff --quiet "$branch" "$base" 2>/dev/null
}

# `git branch -D` still fails when the branch is checked out in a worktree, and
# this script runs under `set -e` with an ERR trap — an unguarded call turns a
# recoverable condition into "HOOK CRASH". Report what git said and let the run
# finish; the caller can rerun after removing the worktree.
force_delete_branch() {
    local reason="$1" err
    if err=$(git branch -D "$BRANCH" 2>&1); then
        print_info "Deleted local branch: $BRANCH ($reason)"
    else
        print_warning "Could not delete $BRANCH ($reason): ${err%%$'\n'*}"
    fi
}

if git branch --list "$BRANCH" | grep -q "$BRANCH"; then
    if git branch -d "$BRANCH" 2>/dev/null; then
        print_info "Deleted local branch: $BRANCH"
    elif [ "$FORCE" = true ]; then
        force_delete_branch "forced"
    elif branch_content_landed "$BRANCH" "$DEFAULT_BRANCH"; then
        force_delete_branch "rebase/squash-merged into $DEFAULT_BRANCH"
    else
        print_warning "Branch not fully merged; use --force to delete anyway"
    fi
fi

print_success "Cleaned: $BRANCH"
