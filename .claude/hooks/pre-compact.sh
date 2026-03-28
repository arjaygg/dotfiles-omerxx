#!/usr/bin/env bash
# PreCompact hook: inject enriched session state before compaction
# Reads: stdin payload (transcript_path, trigger), git state, artifact files, transcript topics

set -euo pipefail

CWD=$(pwd)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

# --- Parse stdin payload ---
HOOK_PAYLOAD=$(cat)
TRANSCRIPT_PATH=$(echo "$HOOK_PAYLOAD" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('transcript_path', ''))
except:
    print('')
" 2>/dev/null || echo "")
TRIGGER=$(echo "$HOOK_PAYLOAD" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('trigger', ''))
except:
    print('')
" 2>/dev/null || echo "")

# More topics on auto-compact (user had no warning)
TOPIC_COUNT=5
[[ "$TRIGGER" == "auto" ]] && TOPIC_COUNT=10

# --- Git state ---
GIT_BRANCH=$(git -C "$CWD" branch --show-current 2>/dev/null || echo "")
GIT_STATE=$(git -C "$CWD" status --short 2>/dev/null | head -10 | tr '\n' '; ' | sed 's/; $//')

# --- Active plan ---
PLAN_FILE=""
PLAN_SUMMARY=""
if [[ -d "$CWD/plans" ]] && ls "$CWD/plans/"*.md 1>/dev/null 2>&1; then
    # Prefer active-context.md if present, else most-recently modified plan
    if [[ -f "$CWD/plans/active-context.md" ]]; then
        PLAN_FILE="$CWD/plans/active-context.md"
    else
        PLAN_FILE=$(ls -t "$CWD/plans/"*.md 2>/dev/null \
            | grep -v -E '(active-context|decisions|progress|session-handoff)\.md$' \
            | head -1)
    fi
elif [[ -d "$CWD/docs/plans" ]] && ls "$CWD/docs/plans/"*.md 1>/dev/null 2>&1; then
    PLAN_FILE=$(ls -t "$CWD/docs/plans/"*.md 2>/dev/null | head -1)
fi
if [[ -n "$PLAN_FILE" ]] && [[ "$PLAN_FILE" != "$CWD/plans/active-context.md" ]]; then
    PLAN_TITLE=$(grep -m1 '^#' "$PLAN_FILE" 2>/dev/null | sed 's/^#* *//' || echo "")
    PLAN_SUMMARY="${PLAN_FILE##$CWD/}"
    [[ -n "$PLAN_TITLE" ]] && PLAN_SUMMARY="${PLAN_FILE##$CWD/} — $PLAN_TITLE"
fi

# --- Artifact files ---
ACTIVE_CTX=""
[[ -f "$CWD/plans/active-context.md" ]] && ACTIVE_CTX=$(head -30 "$CWD/plans/active-context.md")

DECISIONS=""
[[ -f "$CWD/plans/decisions.md" ]] && DECISIONS=$(tail -20 "$CWD/plans/decisions.md")

PROGRESS=""
[[ -f "$CWD/plans/progress.md" ]] && PROGRESS=$(cat "$CWD/plans/progress.md")

# --- Recent topics from transcript ---
TOPICS=""
if [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]]; then
    TOPICS=$(python3 - "$TRANSCRIPT_PATH" "$TOPIC_COUNT" <<'PYEOF'
import sys, json

path = sys.argv[1]
n = int(sys.argv[2])

try:
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    # Only look at last 200 lines for performance
    lines = lines[-200:]
    topics = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Transcript entries have type/role fields
        role = obj.get('role', '') or obj.get('type', '')
        if role not in ('human', 'user'):
            continue
        content = obj.get('content', '')
        if isinstance(content, list):
            # Extract text from content blocks
            parts = [c.get('text', '') for c in content if isinstance(c, dict) and c.get('type') == 'text']
            content = ' '.join(parts)
        if not isinstance(content, str):
            content = str(content)
        content = content.strip()
        # Skip very short messages (e.g., "ok", "yes")
        if len(content) < 10:
            continue
        # Truncate to first line, max 120 chars
        first_line = content.split('\n')[0][:120]
        topics.append(first_line)
    # Last n unique-ish topics
    seen = set()
    unique = []
    for t in reversed(topics):
        key = t[:60]
        if key not in seen:
            seen.add(key)
            unique.append(t)
        if len(unique) >= n:
            break
    unique.reverse()
    for t in unique:
        print(f'  • {t}')
except Exception as e:
    pass
PYEOF
    )
fi

# --- Recently edited files ---
# Prefer session-start timestamp (written by session-init.sh at SessionStart).
# This accurately tracks files touched THIS session, not since the last git op.
# Falls back to git index if the timestamp file is absent (e.g., older sessions).
SESSION_START_FILE="/tmp/.claude-session-start-$(id -u)"
REFERENCE_FILE=""
if [[ -f "$SESSION_START_FILE" ]]; then
    REFERENCE_FILE="$SESSION_START_FILE"
elif [[ -f "$CWD/.git/index" ]]; then
    REFERENCE_FILE="$CWD/.git/index"
elif [[ -f "$CWD/.git" ]]; then
    # git worktree: .git is a file pointing to the actual gitdir
    GITDIR=$(git -C "$CWD" rev-parse --git-dir 2>/dev/null || echo "")
    [[ -n "$GITDIR" ]] && [[ -f "$GITDIR/index" ]] && REFERENCE_FILE="$GITDIR/index"
fi

RECENT_FILES=""
if [[ -n "$REFERENCE_FILE" ]]; then
    RECENT_FILES=$(find "$CWD" -newer "$REFERENCE_FILE" -type f \
        ! -path '*/.git/*' \
        ! -path '*/node_modules/*' \
        ! -path '*/target/*' \
        2>/dev/null | head -20 | sed "s|$CWD/||" | tr '\n' ', ' | sed 's/,$//')
fi

# --- Build checkpoint ---
python3 - \
    "$PLAN_SUMMARY" \
    "$RECENT_FILES" \
    "$TIMESTAMP" \
    "$CWD" \
    "$TRIGGER" \
    "$GIT_BRANCH" \
    "$GIT_STATE" \
    "$ACTIVE_CTX" \
    "$DECISIONS" \
    "$PROGRESS" \
    "$TOPICS" \
    <<'PYEOF'
import sys, json

(plan, recent, timestamp, cwd, trigger,
 git_branch, git_state, active_ctx, decisions, progress, topics) = sys.argv[1:12]

trigger_label = trigger if trigger else "unknown"

lines = [
    f'[PRE-COMPACT CHECKPOINT — {timestamp}]  [trigger: {trigger_label}]',
    f'Working directory: {cwd}  |  Branch: {git_branch}' if git_branch else f'Working directory: {cwd}',
]

if git_state:
    lines.append(f'Git state: {git_state}')

if active_ctx:
    lines.append('')
    lines.append('Active context:')
    lines.append(active_ctx)

if topics:
    lines.append('')
    lines.append('Recent conversation topics:')
    lines.append(topics)

if plan:
    lines.append('')
    lines.append(f'Active plan: {plan}')

if decisions:
    lines.append('')
    lines.append('Recent decisions:')
    lines.append(decisions)

if progress:
    lines.append('')
    lines.append('Task state:')
    lines.append(progress)

if recent:
    lines.append('')
    lines.append(f'Recently edited files: {recent}')

lines.append('')
lines.append('Retain state from plans/, docs/plans/, and docs/adr/.')
lines.append('Context is about to be compacted. Resume from this state after compaction.')

print(json.dumps({'type': 'text', 'text': chr(10).join(lines)}))
PYEOF

exit 0
