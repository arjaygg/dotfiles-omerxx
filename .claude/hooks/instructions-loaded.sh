#!/usr/bin/env bash
# InstructionsLoaded hook: inject dynamic runtime context once per session,
# after CLAUDE.md rules are loaded and before the first user turn.
#
# Offloads per-session static checks from UserPromptSubmit (plans-healthcheck)
# to reduce per-prompt overhead. Only fires once at session start.

set -euo pipefail

CWD=$(pwd)
DATE=$(date '+%Y-%m-%d %H:%M %Z')

# --- Git state snapshot ---
GIT_BRANCH=$(git -C "$CWD" branch --show-current 2>/dev/null || echo "")
GIT_DIRTY=$(git -C "$CWD" status --short 2>/dev/null | wc -l | tr -d ' ')

# --- direct MCP server health (advisory, non-blocking) ---
MCP_STATUS="ok"
MCP_MISSING=""
_MCP_CONFIG="$HOME/.dotfiles/.mcp.json"
if [[ -r "$_MCP_CONFIG" ]]; then
    MCP_MISSING=$(python3 -c "
import json
try:
    with open('$_MCP_CONFIG') as f:
        d = json.load(f)
    names = set(d.get('mcpServers', {}).keys())
    required = ['serena', 'lean-ctx', 'repomix', 'graphify']
    missing = [s for s in required if not any(s in n for n in names)]
    print(','.join(missing))
except:
    pass
" 2>/dev/null || echo "")
    [[ -n "$MCP_MISSING" ]] && MCP_STATUS="missing: $MCP_MISSING"
else
    MCP_STATUS="$_MCP_CONFIG not found"
fi

# --- Stack enforcement advisory ---
STACK_WARNING=""
if [[ "$GIT_BRANCH" == "main" || "$GIT_BRANCH" == "master" ]]; then
    GT_INIT=0
    [[ -f "$CWD/.git/.graphite_repo_config" ]] && GT_INIT=1
    if [[ "$GT_INIT" -eq 1 ]]; then
        STACK_WARNING="[STACK ENFORCER] You are on '$GIT_BRANCH'. Create a stacked branch before editing. Run: stack create feature/<name> $GIT_BRANCH"
    else
        STACK_WARNING="[STACK ENFORCER] You are on '$GIT_BRANCH' and Charcoal is not initialized. Run: gt repo init, then: stack create feature/<name> $GIT_BRANCH"
    fi
fi

# --- Emit context injection ---
python3 - "$DATE" "$GIT_BRANCH" "$GIT_DIRTY" "$MCP_STATUS" "$STACK_WARNING" "$CWD" <<'PYEOF'
import sys, json

date, branch, dirty_count, mcp_status, stack_warning, cwd = sys.argv[1:7]

lines = [f"[SESSION START — {date}]"]

if branch:
    dirty_label = f"  ({dirty_count} uncommitted file(s))" if dirty_count != "0" else ""
    lines.append(f"Branch: {branch}{dirty_label}")

if stack_warning:
    lines.append(stack_warning)

if mcp_status != "ok":
    lines.append(f"MCP config advisory: {mcp_status}")

# Only emit if there's something actionable to surface
if len(lines) > 1:
    print(json.dumps({"type": "text", "text": "\n".join(lines)}))
PYEOF

exit 0
