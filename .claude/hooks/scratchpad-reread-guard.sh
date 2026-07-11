#!/usr/bin/env bash
# PreToolUse guard (Read only): block re-reading a scratchpad file already
# read once this session.
#
# Why a standalone hook instead of folding into pre-tool-gate-v2.sh: that gate
# is a large consolidated file covering unrelated security/policy concerns
# (git safety, PR conventions, plan scope, session-init gating). This is a
# narrow, orthogonal bookkeeping concern — same rationale the gate's own
# header gives for leaving rtk-rewrite.sh and the lean-ctx redirect standalone
# rather than folding them in blind.
#
# Rationale: ai/rules/context-and-compaction.md documents scratchpad files as
# write-mostly — Claude Code's post-compaction rebuild can reinject recently
# read files verbatim, so a deliberate re-read of unchanged scratchpad content
# only spends budget that could hold real project files. This hook makes that
# rule mechanical instead of relying on the model remembering it.
#
# Does NOT prevent the first, legitimate read of a scratchpad file from still
# being "recent" if compaction fires shortly after — that part is timing-
# dependent and not controllable from a PreToolUse hook.

set -euo pipefail

INPUT=$(cat)

eval "$(echo "$INPUT" | jq -r '
  @sh "TOOL_NAME=\(.tool_name // "")",
  @sh "FILE_PATH=\(.tool_input.file_path // .tool_input.path // "")",
  @sh "SESSION_ID=\(.session_id // "")"
' 2>/dev/null)" 2>/dev/null || exit 0

[[ "$TOOL_NAME" == "Read" ]] || exit 0
[[ -n "$FILE_PATH" ]] || exit 0
[[ "$FILE_PATH" == */scratchpad/* ]] || exit 0

EFFECTIVE_SESSION_ID="${SESSION_ID:-${CLAUDE_SESSION_ID:-default}}"
LOG_FILE="/tmp/.claude-scratchpad-reads-$(id -u)-${EFFECTIVE_SESSION_ID}"

touch "$LOG_FILE" 2>/dev/null || exit 0

if grep -qxF "$FILE_PATH" "$LOG_FILE" 2>/dev/null; then
    REASON="[HARD-BLOCK — DO NOT RETRY] Already read this scratchpad file earlier this session: $FILE_PATH
  Scratchpad files are write-mostly (ai/rules/context-and-compaction.md) — content is
  unchanged since your last read. Re-reading it risks it riding along into post-compaction
  context for no benefit. Use Glob if you only need to confirm it exists."
    jq -cn --arg r "$REASON" \
        '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
    exit 0
fi

printf '%s\n' "$FILE_PATH" >> "$LOG_FILE" 2>/dev/null || true
exit 0
