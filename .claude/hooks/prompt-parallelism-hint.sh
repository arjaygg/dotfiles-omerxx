#!/usr/bin/env bash
# UserPromptSubmit hook — advisory nudge for parallelism (once per session).
# Detects multi-task user prompts and injects a system-reminder suggesting TaskCreate.
# Exits 0 always — advisory only, never blocks prompt submission.

# Only fire once per session to avoid repeated token overhead
HINT_FLAG="/tmp/.claude-parallelism-hint-$(id -u)"
[[ -f "$HINT_FLAG" ]] && exit 0

input=$(cat)
prompt=$(echo "$input" | jq -r '.prompt // ""' 2>/dev/null)

if echo "$prompt" | grep -qiE \
  'for (each|every)|all (files?|modules?|services?|items?|entries|repos?)|analyze.+,.+and|check.+,.+and|review.+,.+and|[0-9]+\.\s'; then

  touch "$HINT_FLAG"
  echo "PARALLELISM HINT: This prompt may involve multiple independent sub-tasks."
  echo "Prefer TaskCreate for parallel execution over a single Agent call."
  echo "Only use Agent for tasks that are truly sequential or require shared context."
fi

exit 0
