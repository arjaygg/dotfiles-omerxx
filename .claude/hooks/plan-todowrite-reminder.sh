#!/usr/bin/env bash
# UserPromptSubmit hook — advisory nudge for TodoWrite usage.
#
# Fires in two cases:
#   1. Active plan present → remind to convert steps to TodoWrite before executing
#   2. No plan but prompt implies multi-step work → remind to create a TodoWrite list

emit_context() {
  python3 -c 'import json,sys; m=sys.stdin.read().strip(); print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":m}}))'
}

input=$(cat)
prompt=$(echo "$input" | jq -r '.prompt // ""' 2>/dev/null)

PLAN=$(grep "^plan:" plans/active-context.md 2>/dev/null | awk '{print $2}')

# Case 1: active plan present — nudge on execution-start keywords
if [ -n "$PLAN" ]; then
  if echo "$prompt" | grep -qiE "(let'?s|start|begin|continue|proceed|implement|execute|do step|run plan|work on|pick up|resume)"; then
    STEP=$(grep "^step:" plans/active-context.md 2>/dev/null | awk '{print $2}')
    cat <<EOF | emit_context
PLAN CONTEXT: Active plan → $PLAN${STEP:+ (step $STEP)}
Before executing: use TodoWrite to convert plan steps into an ordered task list.
Do not begin Step N+1 until Step N's Accepts criteria are met.
Do NOT use TaskCreate — that spawns background agents, not a checklist.
EOF
  fi
  exit 0
fi

# Case 2: no active plan — nudge if prompt implies multi-step work
# Patterns: explicit sequencing, multi-file operations, implementation tasks
MULTI_STEP=0

# Explicit step/sequence language
echo "$prompt" | grep -qiE "(first.{1,40}then|step [0-9]|part [0-9]|and (also|then) |, then |followed by)" && MULTI_STEP=1

# Implementation scope with breadth indicator
echo "$prompt" | grep -qiE "(implement|build|create|add|refactor|migrate|update|fix|write|generate).{1,60}(all|each|every|multiple|across|throughout|and |,)" && MULTI_STEP=1

if [ "$MULTI_STEP" -eq 1 ]; then
  cat <<'EOF' | emit_context
MULTI-STEP TASK DETECTED: Use TodoWrite to track steps before starting.
Mark each item in_progress → completed as you go.
Do NOT stop until all TodoWrite items are completed.
Do NOT use TaskCreate — that spawns background agents, not a checklist.
EOF
fi

exit 0
