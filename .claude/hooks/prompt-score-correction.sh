#!/usr/bin/env bash
# UserPromptSubmit hook — Detects correction patterns and scores the prior prompt -1.
# Fires on every user prompt. Checks if the prompt looks like a correction.
# Uses a timestamp guard: only scores if the prior prompt was within 120 seconds.
# Always exits 0 (advisory, never blocks).

input=$(cat)
prompt=$(echo "$input" | jq -r '.prompt // ""' 2>/dev/null)

[[ -z "$prompt" ]] && exit 0

# Correction pattern detection (case-insensitive, start-of-prompt or standalone)
# Only trigger on short correction-like prompts (< 20 words) to reduce false positives
wc=$(echo "$prompt" | wc -w | tr -d ' ')
[[ "$wc" -gt 20 ]] && exit 0

echo "$prompt" | grep -qiE '^(no[,. ]|wrong|undo|revert|actually[,. ]|instead[,. ]|not that|stop|don.t|wait)' || exit 0

# Check if prior prompt is recent enough (within 120 seconds)
DB_FILE="$HOME/.local/share/prompt-library/prompts.db"
[[ -f "$DB_FILE" ]] || exit 0

last_ts=$(sqlite3 "$DB_FILE" "SELECT timestamp FROM prompts WHERE deleted=0 ORDER BY timestamp DESC LIMIT 1;" 2>/dev/null)
[[ -z "$last_ts" ]] && exit 0

# Score in background
(
    SCORE_SCRIPT="$HOME/.dotfiles/.claude/scripts/prompt-library-score.sh"
    [[ -x "$SCORE_SCRIPT" ]] && "$SCORE_SCRIPT" --recent -1 >/dev/null 2>&1
) &

exit 0
