#!/bin/bash
# Smart post-push CI watcher — event-driven, LogSage/RFM classification
# Fires on: git push (any branch)
# Uses: gh run watch (blocking — GH notifies completion, no polling loop)
# Applies RFM scoring: Recency × Frequency × Magnitude
#   Score < 4 → retry (transient)   Score ≥ 4 → escalate (systemic)

set -o pipefail

HOOK_INPUT=$(cat -)
TOOL_NAME=$(printf '%s' "$HOOK_INPUT" | jq -r '.tool_name // ""')
COMMAND=$(printf '%s' "$HOOK_INPUT" | jq -r '.tool_input.command // ""')

[[ "$TOOL_NAME" != "Bash" ]] && exit 0
[[ "$COMMAND" =~ git[[:space:]]+push ]] || exit 0

REPO=/Users/axos-agallentes/git/auc-conversion
ACTED_FILE="$REPO/.serena/memories/cicd-acted-runs.md"
GH_REPO="axos-financial/auc-conversion"

BRANCH=$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null)
[[ -z "$BRANCH" || "$BRANCH" == "HEAD" ]] && exit 0

# ─── RFM scoring ────────────────────────────────────────────────────────────
# Reads cicd-acted-runs.md to compute R, F, M for the current branch.
# Returns score via stdout (integer). Called after failure is confirmed.
rfm_score() {
  local branch="$1" failed_jobs="$2" acted_file="$3"
  local now_epoch; now_epoch=$(date -u +%s)
  local four_hours_ago=$(( now_epoch - 14400 ))
  local seven_days_ago=$(( now_epoch - 604800 ))

  # Extract timestamps of HIGH/CRITICAL failures for this branch
  local failures=()
  while IFS= read -r line; do
    # Line format: - <id> | <branch> | HIGH | ... | <ISO-ts>
    if [[ "$line" =~ ^-[[:space:]]+[0-9]+[[:space:]]+\|[[:space:]]+${branch}[[:space:]]+\|[[:space:]]+(HIGH|CRITICAL) ]]; then
      local ts; ts=$(printf '%s' "$line" | awk -F'|' '{print $NF}' | tr -d ' ')
      local epoch; epoch=$(date -jf "%Y-%m-%dT%H:%M:%SZ" "$ts" "+%s" 2>/dev/null || echo 0)
      [[ "$epoch" -gt "$seven_days_ago" ]] && failures+=("$epoch")
    fi
  done < "$acted_file" 2>/dev/null

  # R: Recency — did this branch fail in last 4 hours?
  local R=1
  for ep in "${failures[@]}"; do
    [[ "$ep" -gt "$four_hours_ago" ]] && R=2 && break
  done

  # F: Frequency — failures in last 7 days
  local count="${#failures[@]}"
  local F=1
  [[ "$count" -ge 2 && "$count" -le 3 ]] && F=2
  [[ "$count" -ge 4 && "$count" -le 5 ]] && F=3
  [[ "$count" -ge 6 ]] && F=4

  # M: Magnitude — which environments are blocked by failed jobs
  local M=1
  if echo "$failed_jobs" | grep -qiE 'deploy.?(qa|staging)'; then M=2; fi
  if echo "$failed_jobs" | grep -qiE 'deploy.?uat|deploy.?prod'; then M=3; fi

  echo $(( R * F * M ))
}

# ─── Background watcher ─────────────────────────────────────────────────────
(
  # Wait up to 90s for the triggered run to appear
  RUN_ID=""
  for _ in $(seq 1 18); do
    sleep 5
    RUN_ID=$(gh run list \
      --repo "$GH_REPO" \
      --branch "$BRANCH" \
      --limit 1 \
      --json databaseId,status \
      --jq '.[0] | select(.status != "completed") | .databaseId' 2>/dev/null)
    [[ -n "$RUN_ID" && "$RUN_ID" != "null" ]] && break
  done

  [[ -z "$RUN_ID" || "$RUN_ID" == "null" ]] && exit 0

  # Skip if already acted on this run
  grep -q "^- $RUN_ID " "$ACTED_FILE" 2>/dev/null && exit 0

  # Block until run completes — gh notifies completion, no polling loop
  gh run watch "$RUN_ID" \
    --repo "$GH_REPO" \
    --interval 15 2>/dev/null || true

  CONCLUSION=$(gh run view "$RUN_ID" \
    --repo "$GH_REPO" \
    --json conclusion \
    --jq '.conclusion' 2>/dev/null)

  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  if [[ "$CONCLUSION" == "success" ]]; then
    printf -- "- %s | %s | SUCCESS | logged (push hook) | %s\n" \
      "$RUN_ID" "$BRANCH" "$TS" >> "$ACTED_FILE"
    exit 0
  fi

  # Get failed job names for classification
  FAILED_JOBS=$(gh run view "$RUN_ID" \
    --repo "$GH_REPO" \
    --json jobs \
    --jq '[.jobs[] | select(.conclusion == "failure") | .name] | join(",")' 2>/dev/null)

  # CRITICAL: security/secrets/CVE failures — never retry, always escalate
  if echo "$FAILED_JOBS" | grep -qiE 'secret|trivy|cve|security'; then
    printf -- "- %s | %s | CRITICAL | escalated (push hook, jobs: %s) | %s\n" \
      "$RUN_ID" "$BRANCH" "$FAILED_JOBS" "$TS" >> "$ACTED_FILE"
    exit 0
  fi

  # HIGH: apply RFM to decide retry vs escalate
  SCORE=$(rfm_score "$BRANCH" "$FAILED_JOBS" "$ACTED_FILE")

  if [[ "$SCORE" -ge 4 ]]; then
    # Systemic — don't retry, escalate for human review
    printf -- "- %s | %s | HIGH | escalated (RFM=%s, push hook, jobs: %s) | %s\n" \
      "$RUN_ID" "$BRANCH" "$SCORE" "$FAILED_JOBS" "$TS" >> "$ACTED_FILE"
  else
    # Transient — safe to retry once
    if gh run rerun "$RUN_ID" --repo "$GH_REPO" 2>/dev/null; then
      printf -- "- %s | %s | HIGH | auto-retry (RFM=%s, push hook, jobs: %s) | %s\n" \
        "$RUN_ID" "$BRANCH" "$SCORE" "$FAILED_JOBS" "$TS" >> "$ACTED_FILE"
    else
      printf -- "- %s | %s | HIGH | retry-failed (RFM=%s, push hook, jobs: %s) | %s\n" \
        "$RUN_ID" "$BRANCH" "$SCORE" "$FAILED_JOBS" "$TS" >> "$ACTED_FILE"
    fi
  fi
) &
disown
exit 0
