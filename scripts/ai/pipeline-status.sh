#!/usr/bin/env bash
# Read-only agentic git lifecycle signal aggregator (plan: plans/2026-07-25-agentic-git-pipeline.md, D1/D4/D1b).
# Zero network calls: only reads local git refs/worktrees, atomic-status.sh's output, and
# plans/ci-status.md (written elsewhere by ci-watch). Never runs `git fetch`/`gh`/etc.
# Always exits 0 — the signal is communicated via stdout, never via exit code.
#
# Output (default): one line, `signal=<value> reason="<one-line reason>"`
# Output (--json):  one line, {"signal":"<value>","reason":"<one-line reason>"}
#
# Signals (first match wins, most-locally-actionable first):
#   split_needed | commit_due | pr_due | ci_pending | merge_due | sync_due | cleanup_due | none
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ATOMIC_STATUS="$SCRIPT_DIR/atomic-status.sh"

JSON_MODE=0
for arg in "$@"; do
    case "$arg" in
        --json) JSON_MODE=1 ;;
    esac
done

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    printf '%s' "$s"
}

emit() {
    local signal="$1" reason="$2"
    if [[ "$JSON_MODE" -eq 1 ]]; then
        printf '{"signal":"%s","reason":"%s"}\n' "$signal" "$(json_escape "$reason")"
    else
        printf 'signal=%s reason="%s"\n' "$signal" "$(json_escape "$reason")"
    fi
    exit 0
}

resolve_main_branch() {
    local b
    for b in main master; do
        if git show-ref --verify --quiet "refs/heads/$b" || git show-ref --verify --quiet "refs/remotes/origin/$b"; then
            echo "$b"
            return 0
        fi
    done
    local sym
    sym=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || echo "")
    echo "${sym#origin/}"
}

find_worktree_for_branch() {
    local branch="$1"
    git worktree list --porcelain 2>/dev/null | awk -v b="refs/heads/$branch" '
        /^worktree /{wt=substr($0,10)}
        /^branch /{if ($2==b) print wt}
    '
}

squash_merged() {
    local branch="$1" base="$2"
    local mb branch_id
    mb=$(git merge-base "$branch" "$base" 2>/dev/null || echo "")
    [[ -z "$mb" ]] && return 1
    branch_id=$(git diff "$mb" "$branch" 2>/dev/null | git patch-id --stable 2>/dev/null | awk '{print $1}')
    [[ -z "$branch_id" ]] && return 1
    local c
    for c in $(git log "$base" --format=%H -n 100 2>/dev/null); do
        local c_id
        c_id=$(git diff "${c}^" "$c" 2>/dev/null | git patch-id --stable 2>/dev/null | awk '{print $1}')
        [[ -n "$c_id" && "$c_id" == "$branch_id" ]] && return 0
    done
    return 1
}

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -z "$REPO_ROOT" ]]; then
    emit "none" "not inside a git repository"
fi

CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
HEAD_SHA=$(git rev-parse HEAD 2>/dev/null || echo "")

if [[ -z "$CURRENT_BRANCH" ]]; then
    emit "none" "detached HEAD; no pipeline signal applicable"
fi

MAIN_BRANCH=$(resolve_main_branch)

# --- Main lane: sync + cleanup ---
if [[ -n "$MAIN_BRANCH" && "$CURRENT_BRANCH" == "$MAIN_BRANCH" ]]; then
    if git rev-parse --verify -q "origin/${MAIN_BRANCH}" >/dev/null 2>&1; then
        ORIGIN_SHA=$(git rev-parse "origin/${MAIN_BRANCH}")
        if [[ "$ORIGIN_SHA" != "$HEAD_SHA" ]] && git merge-base --is-ancestor HEAD "origin/${MAIN_BRANCH}" 2>/dev/null; then
            BEHIND=$(git rev-list --count "HEAD..origin/${MAIN_BRANCH}" 2>/dev/null || echo 0)
            emit "sync_due" "local ${MAIN_BRANCH} is behind origin/${MAIN_BRANCH} by ${BEHIND} commit(s); fast-forward sync"
        fi
    fi

    while IFS= read -r branch; do
        [[ -z "$branch" || "$branch" == "$MAIN_BRANCH" ]] && continue
        MERGED=0
        if git merge-base --is-ancestor "refs/heads/$branch" "$MAIN_BRANCH" 2>/dev/null; then
            MERGED=1
        elif squash_merged "refs/heads/$branch" "$MAIN_BRANCH"; then
            MERGED=1
        fi
        if [[ "$MERGED" -eq 1 ]]; then
            WT=$(find_worktree_for_branch "$branch")
            if [[ -n "$WT" ]]; then
                emit "cleanup_due" "branch '${branch}' is merged into ${MAIN_BRANCH} and still has a linked worktree at ${WT}; run stack-clean"
            else
                emit "cleanup_due" "branch '${branch}' is merged into ${MAIN_BRANCH}; delete the local branch"
            fi
        fi
    done < <(git for-each-ref --format='%(refname:short)' refs/heads/)

    emit "none" "${MAIN_BRANCH} is in sync with origin/${MAIN_BRANCH}; no cleanup candidates"
fi

# --- Feature-branch lane ---
ATOMIC_JSON=$("$ATOMIC_STATUS" --json)
ATOMIC_STATE=$(jq -r '.state' <<<"$ATOMIC_JSON")

case "$ATOMIC_STATE" in
    blocked)
        SUBS=$(jq -r '.subsystem_count' <<<"$ATOMIC_JSON")
        emit "split_needed" "staged changes span ${SUBS} subsystems (mixed concerns); split before committing"
        ;;
    overgrown)
        FILES=$(jq -r '.staged_files' <<<"$ATOMIC_JSON")
        LINES=$(jq -r '.diff_lines' <<<"$ATOMIC_JSON")
        emit "split_needed" "staged changeset is oversized (${FILES} files, ${LINES} diff lines); split before committing"
        ;;
    ready_to_commit)
        FILES=$(jq -r '.staged_files' <<<"$ATOMIC_JSON")
        emit "commit_due" "${FILES} staged file(s) ready to commit"
        ;;
esac

# How many commits does this branch carry beyond its base (main)? Zero means
# there is genuinely nothing for the pipeline to act on yet, regardless of push state.
if [[ -n "$MAIN_BRANCH" ]] && git rev-parse --verify -q "origin/${MAIN_BRANCH}" >/dev/null 2>&1; then
    BASE_REF="origin/${MAIN_BRANCH}"
elif [[ -n "$MAIN_BRANCH" ]] && git show-ref --verify --quiet "refs/heads/${MAIN_BRANCH}"; then
    BASE_REF="$MAIN_BRANCH"
else
    BASE_REF=""
fi

if [[ -n "$BASE_REF" ]]; then
    AHEAD_OF_BASE=$(git rev-list --count "${BASE_REF}..HEAD" 2>/dev/null || echo 0)
else
    AHEAD_OF_BASE=$(git rev-list --count HEAD 2>/dev/null || echo 0)
fi

if [[ "$AHEAD_OF_BASE" -eq 0 ]]; then
    emit "none" "no commits ahead of ${BASE_REF:-base}; nothing due"
fi

UPSTREAM=$(git rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2>/dev/null || echo "")
if [[ -n "$UPSTREAM" ]]; then
    UNPUSHED=$(git rev-list --count "${UPSTREAM}..HEAD" 2>/dev/null || echo 0)
else
    UNPUSHED="$AHEAD_OF_BASE"
fi

if [[ "$UNPUSHED" -gt 0 ]]; then
    emit "pr_due" "branch has ${UNPUSHED} commit(s) ahead of ${UPSTREAM:-no upstream}; push and open/update a PR"
fi

CI_FILE="$REPO_ROOT/plans/ci-status.md"
if [[ ! -f "$CI_FILE" ]]; then
    emit "pr_due" "branch is pushed but no ci-status.md recorded yet; open/verify PR and start ci-watch"
fi

CI_BRANCH=$(grep -m1 '^\*\*PR:\*\*' "$CI_FILE" 2>/dev/null | sed -E 's/.*— *//' | xargs 2>/dev/null || echo "")
CI_SHA=$(grep -m1 '^\*\*SHA:\*\*' "$CI_FILE" 2>/dev/null | sed -E 's/^\*\*SHA:\*\* *//' | xargs 2>/dev/null || echo "")
CI_STATUS=$(grep '^\*\*Status:\*\*' "$CI_FILE" 2>/dev/null | tail -1 | sed -E 's/^\*\*Status:\*\* *//' | xargs 2>/dev/null || echo "")

if [[ "$CI_BRANCH" != "$CURRENT_BRANCH" ]] || { [[ -n "$CI_SHA" ]] && [[ "$CI_SHA" != "$HEAD_SHA" ]]; }; then
    emit "ci_pending" "plans/ci-status.md does not match current branch/commit (stale or mismatched); treating CI as unknown"
fi

case "$CI_STATUS" in
    SUCCESS*)
        emit "merge_due" "CI succeeded for ${CURRENT_BRANCH}@${HEAD_SHA:0:8}; ready to merge"
        ;;
    FAILED*|TIMEOUT*)
        emit "ci_pending" "CI ${CI_STATUS} for current commit; resolve before merging"
        ;;
    *)
        emit "ci_pending" "CI still running (${CI_STATUS:-unknown}) for current commit"
        ;;
esac
