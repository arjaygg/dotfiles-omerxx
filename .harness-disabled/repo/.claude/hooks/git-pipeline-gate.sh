#!/usr/bin/env bash
# Stop hook: git pipeline lifecycle gate.
# (plan: plans/2026-07-25-agentic-git-pipeline.md, Step 3; goal: goals/2026-07-25-03-agentic-git-pipeline.md)
#
# Calls scripts/ai/pipeline-status.sh (zero-network signal aggregator) and, when a due
# signal is actionable, denies the Stop with a next-action hint -- nudging the agent to
# advance the commit -> PR -> CI -> merge -> sync -> cleanup lifecycle instead of stopping
# mid-flow. No-ops entirely unless BOTH:
#   - core.hooksPath is the dotfiles hooks path (hyper-atomic-commits.md's opt-in gate)
#   - .claude-atomic.yaml has a top-level `pipeline:` key (Step 2's stub, or Step 4's flags)
#
# Levels (hook-config.yaml key: git-pipeline-gate):
#   off   - disabled entirely (default when the key is absent)
#   warn  - emit an advisory to stderr, always allow the stop
#   block - emit a Stop-hook block decision {"decision":"block","reason":"..."}
#
# ci_pending is always advisory-only regardless of level: there is nothing actionable to
# do besides wait for a background watcher (see ai/skills/ci-watch/SKILL.md), so nagging
# a hard block on it would just be noise.
#
# Anti-loop: per (branch, stage) deny counters live in an ephemeral, session-scoped state
# file (/tmp/.claude-git-pipeline-$CLAUDE_SESSION_ID) -- NOT `stop_hook_active`, which is
# global across every registered Stop hook in the dispatch and does not identify which
# hook caused a prior block. After 2 denies for a given stage in one session, the would-be
# 3rd deny "degrades" instead: the stop is allowed, and a stderr message + macOS
# notification (osascript) fire so the signal isn't silently swallowed.
#
# Durable state (<gitdir>/pipeline-state.json, resolved via `git rev-parse --git-dir`
# so it lands in the real gitdir even from a linked worktree where .git is a file) records
# last signal/decision per branch for cross-session audit continuity -- it does not gate
# anything itself.
#
# Every decision (allow/warn/block/degrade) is appended to .claude/pipeline-log.jsonl.
set -euo pipefail
trap 'exit 0' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOK_CONFIG="$SCRIPT_DIR/hook-config.yaml"

LEVEL=$(grep "^git-pipeline-gate:" "$HOOK_CONFIG" 2>/dev/null | awk '{print $2}' | tr -d '"' | tr -d "'")
LEVEL="${LEVEL:-off}"
[ "$LEVEL" = "off" ] && exit 0

INPUT="$(cat)"

STOP_HOOK_ACTIVE=$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
[ "$STOP_HOOK_ACTIVE" = "true" ] && exit 0

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || true)
[ -z "$REPO_ROOT" ] && exit 0

HOOKS_PATH=$(git config --local core.hooksPath 2>/dev/null || true)
EXPECTED_HOOKS_PATH="$HOME/.dotfiles/git/hooks"
[ "$HOOKS_PATH" = "$EXPECTED_HOOKS_PATH" ] || exit 0

ATOMIC_YAML="$REPO_ROOT/.claude-atomic.yaml"
[ -f "$ATOMIC_YAML" ] || exit 0
grep -q "^pipeline:" "$ATOMIC_YAML" 2>/dev/null || exit 0

PIPELINE_STATUS="$DOTFILES_ROOT/scripts/ai/pipeline-status.sh"
[ -x "$PIPELINE_STATUS" ] || exit 0

STATUS_JSON=$(cd "$REPO_ROOT" && "$PIPELINE_STATUS" --json 2>/dev/null || echo '{"signal":"none","reason":"pipeline-status.sh unavailable"}')
SIGNAL=$(printf '%s' "$STATUS_JSON" | jq -r '.signal // "none"' 2>/dev/null || echo "none")
REASON=$(printf '%s' "$STATUS_JSON" | jq -r '.reason // ""' 2>/dev/null || echo "")

BRANCH=$(git branch --show-current 2>/dev/null || echo "detached")
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "")
SESSION="${CLAUDE_SESSION_ID:-nosession}"
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")

LOG_FILE="$REPO_ROOT/.claude/pipeline-log.jsonl"
GIT_DIR=$(cd "$REPO_ROOT" && git rev-parse --git-dir 2>/dev/null || echo ".git")
case "$GIT_DIR" in
    /*) : ;;
    *) GIT_DIR="$REPO_ROOT/$GIT_DIR" ;;
esac
DURABLE_STATE="$GIT_DIR/pipeline-state.json"

# Autonomy demotion markers go in the SHARED git dir, not $GIT_DIR. From a linked
# worktree `--git-dir` returns .git/worktrees/<name>, and since every non-trivial
# change in this repo is made in a worktree (stack create -> .trees/), per-worktree
# markers would mean creating a branch silently launders every demotion. Markers gate
# authorization, so they must be repo-wide.
# (pipeline-state.json above keeps using $GIT_DIR: it is audit convenience that
# "does not gate anything itself", so its per-worktree scope is harmless.)
GIT_COMMON=$(cd "$REPO_ROOT" && cd "$(git rev-parse --git-common-dir 2>/dev/null || echo .git)" && pwd 2>/dev/null || echo "$GIT_DIR")
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

log_decision() {
    jq -nc \
        --arg ts "$NOW" --arg session "$SESSION" --arg branch "$BRANCH" --arg sha "$SHA" \
        --arg signal "$SIGNAL" --arg reason "$REASON" --arg level "$LEVEL" --arg decision "$1" \
        '{ts:$ts, session:$session, branch:$branch, sha:$sha, signal:$signal, reason:$reason, level:$level, decision:$decision}' \
        >> "$LOG_FILE" 2>/dev/null || true
    jq -nc \
        --arg ts "$NOW" --arg branch "$BRANCH" --arg sha "$SHA" --arg signal "$SIGNAL" --arg decision "$1" \
        '{branch:$branch, sha:$sha, signal:$signal, decision:$decision, updated_at:$ts}' \
        > "$DURABLE_STATE" 2>/dev/null || true
}

# --- autonomy demotion writer (plan Part VIII, Step 18) ---------------------------
# Part VIII requires demotion to be mechanical: any `blocked` outcome, failed pressure
# case, Definition-of-Done miss, or `followup_review_recommended: true` drops a leg one
# tier until re-earned. This is where that stops being something an agent remembers and
# becomes a marker on disk that scripts/ai/autonomy-tier.sh reads.
#
# Feed: .claude/pipeline-log.jsonl -- the shared audit trail this hook already appends
# to, and the one ai/skills/auto-ship/SKILL.md routes its per-leg terminal statuses
# into rather than creating a second log.
#
# ATTRIBUTION IS EXPLICIT, NEVER INFERRED. A demotion is written only for an entry that
# names its own `stage`. orchestrate.js's halt payload has no stage field -- its
# `label` is a spec label, and most of its `blocked` emitters are orchestrator
# infrastructure (a worker returning null, schema-invalid retries, an intent_gap
# finding). Guessing a leg from those would demote a leg the failure never touched, so
# stage-less entries are non-demoting BY CONSTRUCTION rather than by heuristic.
#
# REFUSALS ARE NOT DEFECTS. A leg that stopped because it lacked authorization must not
# demote: otherwise an unattended run ratchets its own tier down every time it
# correctly stops to ask, and only a human-committed eval report can heal it -- so the
# leg would decay to A0 through normal, correct operation.
#
# The watermark matters. pipeline-log.jsonl is append-only, so without it a marker that
# a human removed after committing evidence would be recreated from the same old entry
# on the very next Stop. Only entries newer than the watermark are ever acted on, which
# is what makes healing permanent.
DEMOTABLE_STAGES="auto_commit auto_push auto_pr auto_ship auto_clean"
NON_DEFECT_RE='needs_confirmation|awaiting_confirmation|refus|declin|degrade|not_authorized|unauthorized|permission'

write_demotions() {
    [ -f "$LOG_FILE" ] || return 0
    command -v jq >/dev/null 2>&1 || return 0

    local wmfile="$GIT_COMMON/autonomy-demote-watermark"
    local wm=""
    if [ -f "$wmfile" ]; then
        wm=$(tr -d '\n' < "$wmfile" 2>/dev/null || printf '')
    fi

    local newest="$wm"
    local line stage ts cond marker

    while IFS= read -r line; do
        [ -n "$line" ] || continue
        stage=$(printf '%s' "$line" | jq -r 'select(.status == "blocked") | .stage // empty' 2>/dev/null || printf '')
        [ -n "$stage" ] || continue
        case " $DEMOTABLE_STAGES " in *" $stage "*) : ;; *) continue ;; esac

        ts=$(printf '%s' "$line" | jq -r '.ts // empty' 2>/dev/null || printf '')
        [ -n "$ts" ] || continue
        if [ -n "$wm" ] && ! [ "$ts" \> "$wm" ]; then continue; fi
        if [ "$ts" \> "$newest" ]; then newest="$ts"; fi

        cond=$(printf '%s' "$line" | jq -r '.condition // .reason // ""' 2>/dev/null || printf '')
        if printf '%s' "$cond" | grep -qiE "$NON_DEFECT_RE"; then continue; fi

        marker="$GIT_COMMON/autonomy-demoted-$stage"
        [ -f "$marker" ] && continue
        jq -nc --arg s "$stage" --arg t "$ts" --arg c "$cond" --arg w "$NOW" '{stage:$s, demoted_at:$w, trigger_ts:$t, condition:$c, heal:"commit a green evals/reports/<stage>.json then rm this file"}' > "$marker" 2>/dev/null || true
        echo "GIT-PIPELINE-GATE: demoted ${stage} one tier -- ${cond} (marker: ${marker})" >&2
    done < "$LOG_FILE"

    if [ -n "$newest" ]; then
        printf '%s\n' "$newest" > "$wmfile" 2>/dev/null || true
    fi
    return 0
}

# Runs before the signal branching below: a leg can be `blocked` in the log even when
# there is no due signal right now.
write_demotions || true

if [ "$SIGNAL" = "none" ]; then
    log_decision "allow"
    exit 0
fi

HINT=""
case "$SIGNAL" in
    split_needed) HINT="Split the staged changeset (see atomic-status.sh) before committing." ;;
    commit_due)   HINT="Commit staged changes with ~/.dotfiles/scripts/ai/commit.sh." ;;
    pr_due)       HINT="Push the branch and open/update a PR (stack-pr skill)." ;;
    ci_pending)   HINT="Wait for CI (bridge with /ci-watch + Monitor); never poll synchronously." ;;
    merge_due)    HINT="CI is green -- merge via stack-ship." ;;
    sync_due)     HINT="Fast-forward main from origin (stack-sync)." ;;
    cleanup_due)  HINT="Delete the merged branch / run stack-clean." ;;
esac

FULL_REASON="$REASON"
[ -n "$HINT" ] && FULL_REASON="$REASON -- next: $HINT"

if [ "$SIGNAL" = "ci_pending" ] || [ "$LEVEL" = "warn" ]; then
    echo "GIT-PIPELINE-GATE: $FULL_REASON" >&2
    log_decision "warn"
    exit 0
fi

# LEVEL == block from here on.
EPHEMERAL_STATE="/tmp/.claude-git-pipeline-${SESSION}"
STAGE_KEY="${BRANCH}:${SIGNAL}"

DENY_COUNT=0
if [ -f "$EPHEMERAL_STATE" ]; then
    DENY_COUNT=$(jq -r --arg k "$STAGE_KEY" '.[$k] // 0' "$EPHEMERAL_STATE" 2>/dev/null || echo 0)
    [[ "$DENY_COUNT" =~ ^[0-9]+$ ]] || DENY_COUNT=0
fi

if [ "$DENY_COUNT" -ge 2 ]; then
    echo "GIT-PIPELINE-GATE: degraded (2 denies already issued for '${SIGNAL}' on '${BRANCH}' this session) -- $FULL_REASON" >&2
    osascript -e "display notification \"${FULL_REASON}\" with title \"git-pipeline-gate: ${SIGNAL} (degraded)\"" >/dev/null 2>&1 || true
    log_decision "degrade"
    exit 0
fi

NEW_COUNT=$((DENY_COUNT + 1))
TMP_STATE="$(mktemp "${EPHEMERAL_STATE}.XXXXXX" 2>/dev/null || echo "${EPHEMERAL_STATE}.tmp")"
if [ -f "$EPHEMERAL_STATE" ]; then
    jq --arg k "$STAGE_KEY" --argjson v "$NEW_COUNT" '.[$k] = $v' "$EPHEMERAL_STATE" > "$TMP_STATE" 2>/dev/null \
        && mv "$TMP_STATE" "$EPHEMERAL_STATE"
else
    jq -n --arg k "$STAGE_KEY" --argjson v "$NEW_COUNT" '{($k): $v}' > "$TMP_STATE" 2>/dev/null \
        && mv "$TMP_STATE" "$EPHEMERAL_STATE"
fi

log_decision "block"
jq -nc --arg reason "$FULL_REASON" '{"decision":"block","reason":$reason}'
exit 0
