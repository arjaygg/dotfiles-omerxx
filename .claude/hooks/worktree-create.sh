#!/usr/bin/env bash
# worktree-create.sh — WorktreeCreate hook for Claude Code
#
# Redirects Claude Code's worktree creation to the project's .trees/ convention
# instead of the default .claude/worktrees/ location.
#
# Called by:
#   - `claude --worktree <name>` CLI flag (works today)
#   - EnterWorktree tool (pending bug fix: anthropics/claude-code#36205)
#
# Input:  JSON on stdin — { "name": "<slug>", "cwd": "<project-root>", ... }
# Output: Absolute path to the worktree on stdout
#         All informational messages go to stderr

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_SCRIPT="$SCRIPT_DIR/../scripts/stack"
LIB_DIR="$SCRIPT_DIR/../scripts/pr-stack/lib"

# ── JSON parsing ─────────────────────────────────────────────────────────────
# Prefer jq, fall back to python3, then a minimal grep/sed fallback.
parse_json_field() {
    local json="$1"
    local field="$2"

    if command -v jq &>/dev/null; then
        echo "$json" | jq -r ".$field // empty"
    elif command -v python3 &>/dev/null; then
        echo "$json" | python3 -c "
import json, sys
d = json.load(sys.stdin)
v = d.get('$field', '')
if v is not None:
    print(v)
"
    else
        # Basic grep/sed fallback — handles simple string values only
        echo "$json" | grep -o "\"$field\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
            | sed 's/.*"[^"]*"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/'
    fi
}

INPUT="$(cat)"
NAME="$(parse_json_field "$INPUT" "name")"
CWD="$(parse_json_field "$INPUT" "cwd")"

if [ -z "$NAME" ]; then
    echo "worktree-create.sh: missing 'name' in hook payload" >&2
    exit 1
fi

if [ -z "$CWD" ]; then
    CWD="$(pwd)"
fi

# ── Name sanitization (mirrors create-stack.sh logic) ────────────────────────
# Strip standard branch type prefixes, lowercase, spaces→hyphens, strip
# special chars, collapse hyphens, trim leading/trailing hyphens.
sanitize_name() {
    local raw="$1"
    echo "$raw" \
        | sed -E 's#^(feature|feat|bugfix|fix|hotfix|release|chore)/##' \
        | tr '[:upper:]' '[:lower:]' \
        | sed -E 's/[ _]/-/g' \
        | sed -E 's/[^a-z0-9.-]//g' \
        | sed -E 's/-+/-/g' \
        | sed -E 's/^-|-$//g'
}

# Derive a branch name: preserve recognized prefixes, otherwise add feature/
derive_branch_name() {
    local raw="$1"
    if echo "$raw" | grep -qE '^(feature|feat|bugfix|fix|hotfix|release|chore)/'; then
        echo "$raw"
    else
        echo "feature/$raw"
    fi
}

SANITIZED="$(sanitize_name "$NAME")"
BRANCH_NAME="$(derive_branch_name "$NAME")"
WORKTREE_PATH="$CWD/.trees/$SANITIZED"

echo "worktree-create.sh: name='$NAME' → sanitized='$SANITIZED' branch='$BRANCH_NAME'" >&2
echo "worktree-create.sh: target worktree path: $WORKTREE_PATH" >&2

# ── Reuse existing worktree if already created by stack create ────────────────
if [ -d "$WORKTREE_PATH" ]; then
    echo "worktree-create.sh: reusing existing worktree at $WORKTREE_PATH" >&2
    echo "$WORKTREE_PATH"
    exit 0
fi

# ── Ensure we're in a git repo ───────────────────────────────────────────────
if ! git -C "$CWD" rev-parse --git-dir &>/dev/null; then
    echo "worktree-create.sh: $CWD is not a git repository" >&2
    exit 1
fi

# ── Determine trunk branch ───────────────────────────────────────────────────
TRUNK="$(git -C "$CWD" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null \
    | sed 's@^refs/remotes/origin/@@' || true)"
if [ -z "$TRUNK" ]; then
    if git -C "$CWD" rev-parse --verify main &>/dev/null; then
        TRUNK="main"
    else
        TRUNK="master"
    fi
fi

# ── Check if branch already exists ───────────────────────────────────────────
BRANCH_EXISTS=false
if git -C "$CWD" rev-parse --verify "$BRANCH_NAME" &>/dev/null; then
    BRANCH_EXISTS=true
fi

# ── Check if branch is already checked out in another worktree ───────────────
if [ "$BRANCH_EXISTS" = true ]; then
    EXISTING_WT="$(git -C "$CWD" worktree list --porcelain \
        | awk -v branch="$BRANCH_NAME" '
            /^worktree / { path=$2 }
            /^branch / {
                if ($2 == "refs/heads/" branch) { print path; exit }
            }')"
    if [ -n "$EXISTING_WT" ]; then
        echo "worktree-create.sh: branch '$BRANCH_NAME' already checked out at $EXISTING_WT" >&2
        echo "$EXISTING_WT"
        exit 0
    fi
fi

# ── Ensure .trees/ exists ────────────────────────────────────────────────────
mkdir -p "$CWD/.trees"

# ── Add .trees/ to .gitignore if missing ─────────────────────────────────────
if ! grep -q "^\.trees/" "$CWD/.gitignore" 2>/dev/null; then
    echo ".trees/" >> "$CWD/.gitignore"
    echo "worktree-create.sh: added .trees/ to .gitignore" >&2
fi

# ── Create the worktree ───────────────────────────────────────────────────────
if [ "$BRANCH_EXISTS" = true ]; then
    echo "worktree-create.sh: creating worktree for existing branch '$BRANCH_NAME'" >&2
    git -C "$CWD" worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
else
    echo "worktree-create.sh: creating new branch '$BRANCH_NAME' from '$TRUNK'" >&2
    git -C "$CWD" worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" "$TRUNK"
fi

# ── Track in Charcoal if available ───────────────────────────────────────────
if command -v gt &>/dev/null; then
    PARENT_BRANCH="$TRUNK"
    gt -C "$CWD" branch track "$BRANCH_NAME" --parent "$PARENT_BRANCH" 2>/dev/null \
        && echo "worktree-create.sh: tracked '$BRANCH_NAME' in Charcoal (parent: $PARENT_BRANCH)" >&2 \
        || echo "worktree-create.sh: Charcoal tracking skipped (already tracked or gt error)" >&2
fi

# ── Copy configs using worktree-charcoal.sh helpers ──────────────────────────
if [ -f "$LIB_DIR/validation.sh" ] && [ -f "$LIB_DIR/worktree-charcoal.sh" ]; then
    # shellcheck disable=SC1090
    source "$LIB_DIR/validation.sh"
    # shellcheck disable=SC1090
    source "$LIB_DIR/worktree-charcoal.sh"
    (cd "$CWD" && copy_worktree_configs "$WORKTREE_PATH") 2>&1 \
        | sed 's/^/worktree-create.sh: /' >&2 || true
fi

echo "worktree-create.sh: done — $WORKTREE_PATH" >&2
echo "$WORKTREE_PATH"
