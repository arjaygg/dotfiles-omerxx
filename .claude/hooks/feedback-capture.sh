#!/usr/bin/env bash
# Stop hook: detect unwritten memory-save annotations
#
# Failure mode: Claude says "[saves feedback memory: X]" in its response text
# but never calls Write to ~/.claude/projects/.../memory/. This hook detects
# that mismatch and injects a reminder into the next turn so Claude self-corrects.
#
# Algorithm:
#   1. Read transcript_path from stdin JSON (same pattern as pre-compact.sh)
#   2. Parse the last assistant turn from the JSONL
#   3. If text blocks contain [saves * memory:] but no Write to memory/ → emit reminder

set -euo pipefail
trap 'echo "HOOK CRASH (feedback-capture.sh line $LINENO): $BASH_COMMAND"; exit 0' ERR

# --- Read transcript path from stdin ---
HOOK_PAYLOAD=$(cat)
TRANSCRIPT_PATH=$(echo "$HOOK_PAYLOAD" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('transcript_path', ''))
except:
    print('')
" 2>/dev/null || echo "")

# Fallback: most recently modified JSONL (handles hooks that don't supply transcript_path)
if [[ -z "$TRANSCRIPT_PATH" ]] || [[ ! -f "$TRANSCRIPT_PATH" ]]; then
    TRANSCRIPT_PATH=$(ls -t "$HOME/.claude/projects/"*/*.jsonl 2>/dev/null | head -1 || echo "")
fi

[[ -z "$TRANSCRIPT_PATH" ]] || [[ ! -f "$TRANSCRIPT_PATH" ]] && exit 0

# --- Parse last assistant turn and detect mismatch ---
python3 - "$TRANSCRIPT_PATH" <<'PYEOF'
import sys, json, re

jsonl_path = sys.argv[1]

save_pattern = re.compile(
    r'\[saves?\s+(user|feedback|project|reference)\s+memory[:\]]',
    re.IGNORECASE
)
# Memory directory marker — Write calls to this path are "real" memory saves
memory_marker = '/memory/'

try:
    with open(jsonl_path, encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
except Exception:
    sys.exit(0)

# Walk backwards: collect all assistant blocks in the last turn
# Stop when we hit a real user message (not a tool_result)
last_turn_texts = []
last_turn_writes = []  # file_path values from Write tool calls
found_boundary = False

for raw in reversed(lines):
    raw = raw.strip()
    if not raw:
        continue
    try:
        obj = json.loads(raw)
    except Exception:
        continue

    msg = obj.get('message', {})
    role = msg.get('role', '')
    content = msg.get('content', [])
    if not isinstance(content, list):
        content = [content] if content else []

    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get('type', '')

        # User boundary: an actual human text message (not a tool result)
        if role == 'user' and btype == 'text':
            found_boundary = True
            break

        if role == 'assistant':
            if btype == 'text':
                last_turn_texts.append(block.get('text', ''))
            elif btype == 'tool_use' and block.get('name') == 'Write':
                fp = (block.get('input') or {}).get('file_path', '')
                last_turn_writes.append(fp)

    if found_boundary:
        break

if not last_turn_texts:
    sys.exit(0)

# Check for memory-save annotations in any text block of the last turn
full_text = '\n'.join(last_turn_texts)
matches = save_pattern.findall(full_text)
if not matches:
    sys.exit(0)

# Check if a Write to memory/ actually happened in the same turn
wrote_memory = any(memory_marker in fp for fp in last_turn_writes)
if wrote_memory:
    sys.exit(0)

# Mismatch detected: annotated a memory save but didn't write the file
types_mentioned = ', '.join(sorted(set(m.lower() for m in matches)))
print(f"[MEMORY-CAPTURE] You mentioned saving a {types_mentioned} memory in your last response "
      f"but did not call the Write tool to persist it. "
      f"Please save it now using the auto-memory instructions.")

PYEOF

exit 0
