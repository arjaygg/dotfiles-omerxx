#!/usr/bin/env bash
# PreToolUse hook — fires before Edit and Write tool calls.
# Blocks edits to files outside the current plan step's declared scope.
#
# Requires: plans/plan-state.json with expected_files[] for the current step.
# Written by the agent when advancing to a new step.
#
# NOTE: plan-state.json is agent-writable, making this a strong soft enforcer
# (visible intent violation detector) rather than a cryptographic lock.
# The agent can modify the file to add files in scope — this is documented
# behavior and tracked in plans/2026-03-30-plan-enforcement-rfc.md.

# Claude Code passes tool input via stdin as JSON:
# { "tool_name": "Edit", "tool_input": { "file_path": "...", ... } }
input=$(cat)

FILE=$(echo "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$FILE" ] && exit 0

STATE=$(cat plans/plan-state.json 2>/dev/null) || exit 0
EXPECTED=$(echo "$STATE" | jq -r '.expected_files[]' 2>/dev/null)
STEP=$(echo "$STATE" | jq -r '.step_title // "unknown step"')

[ -z "$EXPECTED" ] && exit 0

if ! echo "$EXPECTED" | grep -qF "$FILE"; then
  _expected_list=$(echo "$EXPECTED" | tr '\n' ' ')
  python3 -c "import json,sys; print(json.dumps({'decision':'block','reason':sys.argv[1]}))" \
    "BLOCKED: '$FILE' is not in scope for current step: '$STEP'. Expected files: $_expected_list. To add a file to scope: update plans/plan-state.json expected_files[]"
  exit 0
fi

exit 0
