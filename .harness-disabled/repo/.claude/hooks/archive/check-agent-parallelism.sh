#!/usr/bin/env bash
# PreToolUse hook — fires before every Agent tool call.
# Warns when the prompt suggests multiple independent sub-tasks that should run in parallel
# via TaskCreate instead of a single serial Agent call.
#
# Exemptions: any named subagent_type (already purpose-scoped) and background agents

input=$(cat)
prompt=$(echo "$input" | jq -r '.tool_input.prompt // ""' 2>/dev/null)
subagent_type=$(echo "$input" | jq -r '.tool_input.subagent_type // ""' 2>/dev/null)
run_bg=$(echo "$input" | jq -r '.tool_input.run_in_background // false' 2>/dev/null)

# Exempt background agents and any named subagent type.
# Named types (Explore, Plan, claude-code-guide, bmad-bmm-code-review, etc.) are already
# purpose-scoped — they're single-task by definition. Only scrutinize untyped general-purpose calls.
if [[ -n "$subagent_type" || "$run_bg" == "true" ]]; then
  exit 0
fi

# Only flag when 3+ enumerated items suggest a list of independent tasks.
# Require items to look like independent actions (verb at start or "Create/Update/Delete/Add/Remove/Run/Build" patterns)
# This filters out instruction lists (steps within one task) vs. independent parallel tasks.
NUMBERED_ITEMS=$(echo "$prompt" | grep -cE '^\s*[0-9]+\.\s+(Create|Update|Delete|Add|Remove|Run|Build|Generate|Write|Fetch|Deploy|Migrate|Rename|Move|Copy)\b' || true)
BULLET_ITEMS=$(echo "$prompt" | grep -cE '^\s*[-•]\s+(Create|Update|Delete|Add|Remove|Run|Build|Generate|Write|Fetch|Deploy|Migrate|Rename|Move|Copy)\b' || true)

if [[ "$NUMBERED_ITEMS" -ge 3 || "$BULLET_ITEMS" -ge 3 ]]; then
  count=$(echo "$prompt" | grep -oiE '([0-9]+) (files?|modules?|services?|items?)' | head -1)
  _reason="HINT: This Agent call appears to involve multiple independent sub-tasks${count:+ ($count)}. Consider using TaskCreate for parallel execution instead. Proceeding — but if tasks are independent, parallel agents would be faster."
  python3 -c "import json,sys; print(json.dumps({'decision':'warn','reason':sys.argv[1]}))" "$_reason"
fi

exit 0
