#!/usr/bin/env bash
# PreToolUse hook — fires before every Agent tool call.
# Warns when the prompt suggests multiple independent sub-tasks that should run in parallel
# via TaskCreate instead of a single serial Agent call.

input=$(cat)
prompt=$(echo "$input" | jq -r '.tool_input.prompt // ""' 2>/dev/null)

if echo "$prompt" | grep -qiE \
  'for (each|every)|all (files?|modules?|services?|items?|entries|repos?)|analyze.+,.+and|check.+,.+and|review.+,.+and|[0-9]+\.\s|•\s|-\s[A-Z]'; then

  count=$(echo "$prompt" | grep -oiE '([0-9]+) (files?|modules?|services?|items?)' | head -1)

  echo "BLOCKED: This Agent call appears to involve multiple independent sub-tasks${count:+ ($count)}." >&2
  echo "Use TaskCreate for parallel execution instead." >&2
  echo "If tasks are truly sequential or dependent, rephrase your prompt to make that explicit." >&2
  exit 2
fi

exit 0
