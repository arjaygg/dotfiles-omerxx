#!/usr/bin/env bash
# UserPromptSubmit hook: warn when branch has drifted far from origin/main
# or accumulated WIP iterative commits that should be squashed.
# Advisory only — exits 0 always. Never blocks prompt submission.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/hook-metrics.sh" 2>/dev/null || true

HOOK_NAME="drift-guard"
SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"

LEVEL=$(hook_enforcement_level "$HOOK_NAME" 2>/dev/null || echo "warn")
[[ "$LEVEL" == "off" ]] && exit 0

git rev-parse --is-inside-work-tree &>/dev/null 2>&1 || exit 0

CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
[[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" || -z "$CURRENT_BRANCH" ]] && exit 0

if git rev-parse --verify origin/main &>/dev/null 2>&1; then
    BASE_REF="origin/main"
elif git rev-parse --verify origin/master &>/dev/null 2>&1; then
    BASE_REF="origin/master"
else
    exit 0
fi

DRIFT=$(git rev-list --count "${BASE_REF}..HEAD" 2>/dev/null || echo 0)
WIP_COUNT=$(git log --format="%s" "${BASE_REF}..HEAD" 2>/dev/null \
    | grep -cE '(autoresearch|iter-[0-9]|checkpoint|^wip|^WIP)' || true)
WIP_COUNT=${WIP_COUNT:-0}

if [[ "$DRIFT" -le 20 && "$WIP_COUNT" -lt 5 ]]; then
    hook_metric "$HOOK_NAME" "" 0 "$SESSION_ID" 2>/dev/null || true
    exit 0
fi

if [[ "$DRIFT" -gt 50 ]]; then
    echo "[DRIFT ALERT] Branch is ${DRIFT} commits ahead of ${BASE_REF} — high rebase risk."
    echo "  Action: Run /sync-base soon to reduce conflict surface."
elif [[ "$DRIFT" -gt 20 ]]; then
    echo "[DRIFT WARN] Branch is ${DRIFT} commits ahead of ${BASE_REF}."
    echo "  Consider /sync-base to stay close to the base."
fi

if [[ "$WIP_COUNT" -ge 5 ]]; then
    echo "[WIP COMMITS] ${WIP_COUNT} iterative/WIP commits detected (autoresearch/iter-N/checkpoint/wip)."
    echo "  These make rebase painful — run /squash-wip to consolidate before syncing."
fi

hook_metric "$HOOK_NAME" "" 0 "$SESSION_ID" 2>/dev/null || true
exit 0
