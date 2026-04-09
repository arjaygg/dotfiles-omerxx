#!/bin/bash
# Monitor CI/CD build completion and report results (MS Teams integration)
# Fires after: git push, merge to main, or tag creation
# Spawns background SubAgent to poll GitHub Actions until build succeeds/fails
# Reports to MS Teams on CRITICAL/HIGH failures; silent log on MEDIUM

set -o pipefail

# A. Parse hook input from stdin (PostToolUse delivery format)
HOOK_INPUT=$(cat -)   # drain stdin fully — required even on early exit
TOOL_NAME=$(printf '%s' "$HOOK_INPUT" | jq -r '.tool_name // ""')
COMMAND=$(printf '%s' "$HOOK_INPUT" | jq -r '.tool_input.command // ""')

# Only monitor on Bash tool use
[[ "$TOOL_NAME" != "Bash" ]] && exit 0

# B. Robust push/tag detection (replaces fragile regex)
is_push=false; is_tag=false
[[ "$COMMAND" =~ ^git[[:space:]]+push([[:space:]]|$) ]] && is_push=true
[[ "$COMMAND" =~ ^git[[:space:]]+tag([[:space:]]|$) ]]  && is_tag=true
[[ "$is_push" == false && "$is_tag" == false ]] && exit 0

# C. Ref extraction via git state (not command string parsing)
REPO=/Users/axos-agallentes/git/auc-conversion
PUSHED_TAG=$(git -C "$REPO" describe --tags --abbrev=0 HEAD 2>/dev/null || echo "")
PUSHED_SHA=$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo "")
PUSHED_REF="${PUSHED_TAG:-HEAD}"

# D. Structured context to agent (JSON file, not string interpolation)
CONTEXT_FILE=$(mktemp /tmp/cicd-monitor-XXXXXX.json)
jq -n \
  --arg ref  "$PUSHED_REF" \
  --arg sha  "$PUSHED_SHA" \
  --arg repo "axos-financial/auc-conversion" \
  --arg ts   "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{ref:$ref,sha:$sha,repo:$repo,triggered_at:$ts}' > "$CONTEXT_FILE"

# Spawn background SubAgent (non-blocking)
# E. Polling cap: 18 min (36 × 30s retries) — builds take 8-12 min
(
  cd /Users/axos-agallentes/git/auc-conversion || exit 1

  # Background SubAgent with custom role
  claude \
    --project /Users/axos-agallentes/git/auc-conversion \
    --name "cicd-monitor-${PUSHED_REF}" \
    --silent \
    "You are a CI/CD monitor for financial services. Your task:

1. Poll GitHub Actions API for auc-conversion repo
   - Ref: $(jq -r '.ref' "$CONTEXT_FILE")
   - SHA: $(jq -r '.sha' "$CONTEXT_FILE")
   - Max 36 retries (18 minutes total), 30-second intervals
   - Stop when status is 'completed'

2. Classify failure severity:
   - CRITICAL: secrets detected (TruffleHog), CVE (Trivy HIGH/CRITICAL)
   - HIGH: test failure, build error, govulncheck dependency CVE
   - MEDIUM: performance/cache issues, lint warnings, flaky tests

3. Take actions based on severity:

   CRITICAL:
     → Store findings in memory (cicd-monitor/critical-builds.md)
     → SendMessage(to=\"cicd-audit\", event_type=\"failure_detected\", severity=\"CRITICAL\")
     → TaskCreate(subject=\"Human review: {ref}\", agent=\"cicd-review\")
     → DO NOT auto-retry

   HIGH:
     → Store findings in memory (cicd-monitor/high-failures.md)
     → SendMessage(to=\"cicd-audit\", event_type=\"failure_detected\", severity=\"HIGH\")
     → TaskCreate(subject=\"Retry run {ref}\", agent=\"cicd-auto-retry\")
     → Pass run_id and failed_jobs to auto-retry agent

   MEDIUM:
     → Silent: log to memory only (cicd-monitor/build-logs.md)
     → SendMessage(to=\"cicd-audit\", event_type=\"build_warning\", severity=\"MEDIUM\")
     → Do NOT notify Teams (reduce noise)

4. Use tools:
   - \`gh run list --branch $(jq -r '.ref' "$CONTEXT_FILE") --limit 1 --json status,conclusion,name,url,headSha\`
   - \`gh run view <run-id> --json jobs,conclusion\`
   - Store findings in Serena memory

Report to parent when complete."
) &

disown
exit 0
