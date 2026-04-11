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

# --- pctx server health (advisory, non-blocking) ---
PCTX_STATUS="ok"
PCTX_MISSING=""
if [[ -r "$HOME/.config/pctx/pctx.json" ]]; then
    PCTX_MISSING=$(python3 -c "
import json
try:
    with open('$HOME/.config/pctx/pctx.json') as f:
        d = json.load(f)
    raw = d.get('servers', [])
    if isinstance(raw, list):
        names = {s.get('name','') for s in raw if isinstance(s, dict)}
    else:
        names = set(raw.keys())
    required = ['serena', 'exa', 'markitdown', 'lean-ctx']
    missing = [s for s in required if s not in names]
    print(','.join(missing))
except:
    pass
" 2>/dev/null || echo "")
    [[ -n "$PCTX_MISSING" ]] && PCTX_STATUS="missing: $PCTX_MISSING"
else
    PCTX_STATUS="pctx.json not found"
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

# --- Pending session handoff ---
HANDOFF_NOTICE=""
if [[ -f "$CWD/plans/session-handoff.md" ]]; then
    HANDOFF_NOTICE="HANDOFF: plans/session-handoff.md exists — read it to restore prior session context, then delete it."
fi

# --- Emit context injection ---
python3 - "$DATE" "$GIT_BRANCH" "$GIT_DIRTY" "$PCTX_STATUS" "$STACK_WARNING" "$HANDOFF_NOTICE" "$CWD" <<'PYEOF'
import sys, json

date, branch, dirty_count, pctx_status, stack_warning, handoff_notice, cwd = sys.argv[1:8]

lines = [f"[SESSION START — {date}]"]

if branch:
    dirty_label = f"  ({dirty_count} uncommitted file(s))" if dirty_count != "0" else ""
    lines.append(f"Branch: {branch}{dirty_label}")

if stack_warning:
    lines.append(stack_warning)

if pctx_status != "ok":
    lines.append(f"pctx advisory: {pctx_status}")

if handoff_notice:
    lines.append(handoff_notice)

# Only emit if there's something actionable to surface
if len(lines) > 1:
    print(json.dumps({"type": "text", "text": "\n".join(lines)}))
PYEOF

exit 0
