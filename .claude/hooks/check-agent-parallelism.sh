#!/usr/bin/env bash
# PreToolUse hook — fires before every Agent tool call.
# Warns when the prompt suggests multiple independent sub-tasks that should run in parallel
# via TaskCreate instead of a single serial Agent call.
#
# Exemptions: Explore/Plan subagents (read-only), background agents (already parallel)

input=$(cat)
prompt=$(echo "$input" | jq -r '.tool_input.prompt // ""' 2>/dev/null)
subagent_type=$(echo "$input" | jq -r '.tool_input.subagent_type // ""' 2>/dev/null)
run_bg=$(echo "$input" | jq -r '.tool_input.run_in_background // false' 2>/dev/null)

# Exempt read-only and background agents — they ARE the parallel primitive
if [[ "$subagent_type" == "Explore" || "$subagent_type" == "Plan" || "$run_bg" == "true" ]]; then
  exit 0
fi

# Only flag when 3+ enumerated items suggest a list of independent tasks
NUMBERED_ITEMS=$(echo "$prompt" | grep -cE '^\s*[0-9]+\.\s' || true)
BULLET_ITEMS=$(echo "$prompt" | grep -cE '^\s*[-•]\s+[A-Z]' || true)

if [[ "$NUMBERED_ITEMS" -ge 3 || "$BULLET_ITEMS" -ge 3 ]]; then
  count=$(echo "$prompt" | grep -oiE '([0-9]+) (files?|modules?|services?|items?)' | head -1)

  echo "BLOCKED: This Agent call appears to involve multiple independent sub-tasks${count:+ ($count)}." >&2
  echo "Use TaskCreate for parallel execution instead." >&2
  echo "If tasks are truly sequential or dependent, rephrase your prompt to make that explicit." >&2
  exit 2
fi

exit 0
