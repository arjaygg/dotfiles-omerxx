#!/usr/bin/env bash

# create-pr.sh - Create a Pull Request on GitHub
# Usage: ./create-pr.sh <source-branch> [target-branch] [title] [--draft]

set -euo pipefail

# Load libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/validation.sh"
source "$SCRIPT_DIR/lib/pr-title.sh"
source "$SCRIPT_DIR/lib/charcoal-compat.sh"
source "$SCRIPT_DIR/lib/gh-account.sh"

# Functions
print_usage() {
    echo -e "${BLUE}Usage:${NC}"
    echo "  ./create-pr.sh <source-branch> [target-branch] [title] [--draft]"
    echo ""
    echo -e "${BLUE}Arguments:${NC}"
    echo "  source-branch      Branch to create PR from (required)"
    echo "  target-branch      Branch to merge into (default: main)"
    echo "  title              PR title (optional, will prompt if not provided)"
    echo "  --draft            Create as draft PR (optional)"
    echo ""
    echo -e "${BLUE}Examples:${NC}"
    echo "  ./create-pr.sh feature/new-api"
    echo "  ./create-pr.sh feature/new-api main 'Add new API endpoint'"
    echo "  ./create-pr.sh feature/ui feature/api 'Add UI for new API' --draft"
}

# Validate arguments
if [ $# -lt 1 ]; then
    print_error "Missing required argument: source-branch"
    print_usage
    exit 1
fi

SOURCE_BRANCH=$1
# Determine default branch (trunk)
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")

# Target branch:
# - If explicitly provided, use it.
# - Otherwise, prefer Charcoal parent (stacked PRs), falling back to trunk.
TARGET_BRANCH="${2:-}"
if [ -z "$TARGET_BRANCH" ]; then
    if type charcoal_initialized >/dev/null 2>&1 && charcoal_initialized; then
        TARGET_BRANCH="$(charcoal_get_parent "$SOURCE_BRANCH" 2>/dev/null || true)"
    fi
    TARGET_BRANCH="${TARGET_BRANCH:-$DEFAULT_BRANCH}"
fi
TITLE="${3:-}"
DRAFT=false
NO_PUSH=false

# Check lifecycle-safe flags without changing positional branch/title semantics.
for arg in "$@"; do
    case "$arg" in
        --draft) DRAFT=true ;;
        --no-push) NO_PUSH=true ;;
    esac
done

lifecycle_error() {
    local status="$1"
    local reason="$2"
    python3 - "$status" "$reason" <<'PY_ERROR' >&2
import json, sys
print(json.dumps({"lifecycle_pr_error": {
    "exit_status": int(sys.argv[1]), "reason": sys.argv[2][:300],
}}, separators=(",", ":")))
PY_ERROR
}

if [ "$NO_PUSH" = true ]; then
    EXPECTED_ACTOR="${LIFECYCLE_EXPECTED_ACTOR:-}"
    EXPECTED_REPOSITORY="${LIFECYCLE_EXPECTED_REPOSITORY:-}"
    EXPECTED_SHA="${LIFECYCLE_EXPECTED_SHA:-}"
    EXPECTED_URL="${LIFECYCLE_EXPECTED_URL:-}"
    EXPECTED_PUSH_URL="${LIFECYCLE_EXPECTED_PUSH_URL:-}"
    if [ -z "${GH_TOKEN:-}" ] || [ -z "$EXPECTED_ACTOR" ] \
        || [ -z "$EXPECTED_REPOSITORY" ] || [ -z "$EXPECTED_SHA" ] \
        || [ -z "$EXPECTED_URL" ] || [ -z "$EXPECTED_PUSH_URL" ]; then
        lifecycle_error 2 "lifecycle PR credential or pinned identity is missing"
        exit 2
    fi
    FETCH_URLS="$(git remote get-url --all origin 2>/dev/null || true)"
    PUSH_URLS="$(git remote get-url --push --all origin 2>/dev/null || true)"
    if [ "$FETCH_URLS" != "$EXPECTED_URL" ] || [ "$PUSH_URLS" != "$EXPECTED_PUSH_URL" ]; then
        lifecycle_error 2 "origin URL no longer matches the pinned lifecycle contract"
        exit 2
    fi
    TOKEN_ACTOR="$(gh api --hostname github.com /user --jq .login 2>/dev/null || true)"
    TOKEN_REPOSITORY="$(gh repo view --repo "$EXPECTED_REPOSITORY" --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)"
    LOCAL_SHA="$(git rev-parse --verify "$SOURCE_BRANCH^{commit}" 2>/dev/null || true)"
    if [ "$TOKEN_ACTOR" != "$EXPECTED_ACTOR" ] \
        || [ "$TOKEN_REPOSITORY" != "$EXPECTED_REPOSITORY" ] \
        || [ "$LOCAL_SHA" != "$EXPECTED_SHA" ]; then
        lifecycle_error 2 "GitHub actor, repository, or exact SHA does not match the pinned lifecycle contract"
        exit 2
    fi
fi

# Only interactive push mode needs to register Git's credential helper. The
# lifecycle --no-push path must not mutate Git configuration or push again.
if [ "$NO_PUSH" = false ]; then
    gh_setup_git
fi

# Validate prerequisites
print_info "Detected GitHub repository"
validate_github_pr_create_prerequisites "$SOURCE_BRANCH" "$TARGET_BRANCH" || exit 1

# Require Charcoal for PR stack workflows (single source of truth for relationships)
if ! charcoal_available; then
    print_error "Charcoal CLI (gt) is required but not installed"
    print_info "Install with: brew install danerwilliams/tap/charcoal"
    exit 1
fi

if ! charcoal_initialized; then
    print_error "Charcoal is not initialized in this repository"
    print_info "Initialize with: ~/.claude/scripts/stack init"
    exit 1
fi

# Validate PR target is correct for stacked PRs (non-blocking warning)
validate_pr_target "$SOURCE_BRANCH" "$TARGET_BRANCH" || exit 1

# Get repository root (already at root from validation)
REPO_ROOT=$(git rev-parse --show-toplevel)

# Build commit list for PR description.
#
# Prefer commits that are on SOURCE_BRANCH but not on TARGET_BRANCH.
# If branches are missing/upstream refs are unusual, fall back gracefully.
COMMITS="$(git log --oneline "${TARGET_BRANCH}..${SOURCE_BRANCH}" 2>/dev/null || true)"
if [ -z "$COMMITS" ]; then
    COMMITS="$(git log -1 --oneline "${SOURCE_BRANCH}" 2>/dev/null || true)"
fi
if [ -z "$COMMITS" ]; then
    COMMITS="(no commits found)"
fi

# Title: if not provided, auto-generate a conventional title from the branch.
if [ -z "${TITLE:-}" ]; then
    TITLE="$(suggest_pr_title_from_branch "$SOURCE_BRANCH")"
    print_info "No PR title provided. Using generated title: $TITLE"
fi

# Deterministic gate: block PR creation when title isn't Conventional Commits.
validate_conventional_pr_title_or_die "$TITLE" || exit 1

# Check if there are related stories
# Fix: Search from REPO_ROOT to find docs even if we are in a worktree
STORY_FILE=""
if [ -d "$REPO_ROOT/docs/stories" ]; then
    STORY_FILE=$(find "$REPO_ROOT/docs/stories" -name "*.story.md" 2>/dev/null | head -1) || true
fi
STORY_REF=""
if [ -n "$STORY_FILE" ]; then
    STORY_NUM=$(basename "$STORY_FILE" .story.md)
    STORY_REF="Related Story: \`$STORY_NUM\`"
fi

# Build stack chain visualization
STACK_VIZ=""
if charcoal_initialized 2>/dev/null; then
    CHAIN=$(gt log --short 2>/dev/null | awk '{printf "%s`%s`", (NR>1 ? " → " : ""), $1}' || true)
    if [ -n "$CHAIN" ]; then
        STACK_VIZ="## Stack

$CHAIN

"
    fi
fi

# Build description
DESCRIPTION="## Changes

$COMMITS

${STACK_VIZ}## Dependencies
"

# If not targeting trunk, this is a dependent (stacked) PR.
if [ "$TARGET_BRANCH" != "$DEFAULT_BRANCH" ]; then
    DESCRIPTION="$DESCRIPTION
⚠️ **This PR depends on \`$TARGET_BRANCH\` being merged first**

Base branch: \`$TARGET_BRANCH\`
"
fi

DESCRIPTION="$DESCRIPTION
$STORY_REF

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project conventions
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes (or breaking changes documented)

---
*Created via PR stacking automation*
"

# Create the PR
print_info "Creating Pull Request..."

# Interactive callers retain the historical push. The lifecycle adapter passes
# --no-push after independently proving the exact remote SHA.
if [ "$NO_PUSH" = false ]; then
    print_info "Pushing branch to origin..."
    git push -u origin "$SOURCE_BRANCH"
else
    print_info "Using pre-validated remote branch; no additional push performed."
fi

GH_ARGS=(
    pr create
    --base "$TARGET_BRANCH"
    --head "$SOURCE_BRANCH"
    --title "$TITLE"
    --body "$DESCRIPTION"
)
if [ "$NO_PUSH" = true ]; then
    GH_ARGS+=(--repo "$EXPECTED_REPOSITORY")
fi

if [ "$DRAFT" = true ]; then
    GH_ARGS+=(--draft)
fi

if [ -z "${GH_TOKEN:-}" ]; then
    GH_TOKEN="$(gh_token_for_remote)"
    export GH_TOKEN
fi
PR_CAPTURE="$(python3 - "${GH_ARGS[@]}" <<'PY_GH_CAPTURE'
import json
import os
import re
import subprocess
import sys

try:
    proc = subprocess.run(
        ["gh", *sys.argv[1:]],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    status = proc.returncode
    stdout = proc.stdout.strip()[:4096]
    diagnostic = f"{proc.stderr}\n{proc.stdout}" if status else ""
except OSError:
    status = 127
    stdout = ""
    diagnostic = "gh execution failed"
token = os.environ.get("GH_TOKEN", "")
if token:
    diagnostic = diagnostic.replace(token, "[REDACTED]")
diagnostic = re.sub(
    r"(?i)(token|authorization|password|secret)[=: ]+[^\s]+",
    r"\1=[REDACTED]",
    diagnostic,
)
diagnostic = re.sub(
    r"(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)",
    "[REDACTED]",
    diagnostic,
)
diagnostic = re.sub(r"https://[^/@\s]+@", "https://[REDACTED]@", diagnostic)
diagnostic = " ".join(diagnostic.split())
print(json.dumps({
    "exit_status": status,
    "stdout": stdout,
    "diagnostic": (diagnostic or "gh execution failed")[:300],
}, separators=(",", ":")))
PY_GH_CAPTURE
)"
EXIT_CODE="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["exit_status"])' "$PR_CAPTURE")"
PR_OUTPUT="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["stdout"], end="")' "$PR_CAPTURE")"
PR_DIAGNOSTIC="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["diagnostic"], end="")' "$PR_CAPTURE")"

if [ "$EXIT_CODE" -eq 0 ]; then
    PR_URL="$PR_OUTPUT"
    if [ "$NO_PUSH" = true ]; then
        PR_JSON="$(gh pr view "$PR_URL" --repo "$EXPECTED_REPOSITORY" \
            --json author,headRefOid,headRefName,baseRefName,state,isDraft \
            2>/dev/null || true)"
        if ! python3 - "$EXPECTED_ACTOR" "$EXPECTED_SHA" "$SOURCE_BRANCH" "$TARGET_BRANCH" "$PR_JSON" <<'PY_VERIFY'
import json, sys
try:
    value = json.loads(sys.argv[5])
    valid = (
        value.get("author", {}).get("login") == sys.argv[1]
        and value.get("headRefOid") == sys.argv[2]
        and value.get("headRefName") == sys.argv[3]
        and value.get("baseRefName") == sys.argv[4]
        and value.get("state") == "OPEN"
        and value.get("isDraft") is False
    )
except Exception:
    valid = False
raise SystemExit(0 if valid else 1)
PY_VERIFY
        then
            lifecycle_error 3 "created pull request identity did not match the pinned lifecycle contract"
            exit 3
        fi
    fi
    print_success "Pull Request created successfully!"
    echo ""
    print_info "URL: $PR_URL"
    echo ""
    echo -e "${GREEN}Next steps:${NC}"
    echo "  1. Review the PR on GitHub: $PR_URL"
    if [ "$DRAFT" = true ]; then
        echo "  2. Mark as ready for review when complete"
    else
        echo "  2. Wait for reviews and address feedback"
    fi
    echo "  3. After merge, update dependent PRs:"
    echo "     $REPO_ROOT/.claude/scripts/stack update $SOURCE_BRANCH"
else
    SAFE_REASON="$PR_DIAGNOSTIC"
    if [ "$NO_PUSH" = true ]; then
        lifecycle_error "$EXIT_CODE" "$SAFE_REASON"
    fi
    print_error "Failed to create Pull Request (exit $EXIT_CODE): $SAFE_REASON"
    exit 1
fi
