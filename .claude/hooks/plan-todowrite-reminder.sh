#!/usr/bin/env bash
# UserPromptSubmit hook — advisory nudge.
# If active-context.md has a plan: field, remind the agent to populate
# TodoWrite from plan steps before executing on session-opening prompts.

input=$(cat)
prompt=$(echo "$input" | jq -r '.prompt // ""' 2>/dev/null)

# Resolve active plan pointer from active-context.md
PLAN=$(grep "^plan:" plans/active-context.md 2>/dev/null | awk '{print $2}')
[ -z "$PLAN" ] && exit 0

# Only nudge on session-opening / execution-start patterns
if echo "$prompt" | grep -qiE "(let'?s|start|begin|continue|proceed|implement|execute|do step|run plan|work on|pick up|resume)"; then
  STEP=$(grep "^step:" plans/active-context.md 2>/dev/null | awk '{print $2}')
  echo "PLAN CONTEXT: Active plan → $PLAN${STEP:+ (step $STEP)}"
  echo "Before executing: use TodoWrite to convert plan steps into an ordered task list."
  echo "Do not begin Step N+1 until Step N's Accepts criteria are met."
  echo "Do NOT use TaskCreate — that spawns background agents, not a checklist."
fi

exit 0
