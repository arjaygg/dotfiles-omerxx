#!/usr/bin/env bash
# UserPromptSubmit hook — Captures prompts to the prompt library SQLite DB.
# Filters: <8 words, slash commands, secret patterns, system-only messages.
# Runs insert in background for zero latency. Always exits 0 (advisory).

input=$(cat)
prompt=$(echo "$input" | jq -r '.prompt // ""' 2>/dev/null)

# Quick exit for empty or short prompts
[[ -z "$prompt" ]] && exit 0
[[ "$prompt" =~ ^/ ]] && exit 0

# Strip system-reminder tags
prompt=$(echo "$prompt" | sed 's/<system-reminder>.*<\/system-reminder>//g' | sed '/^$/d')
[[ -z "$prompt" ]] && exit 0

# Word count check (≥8)
wc=$(echo "$prompt" | wc -w | tr -d ' ')
[[ "$wc" -lt 8 ]] && exit 0

# Secret pattern filter
echo "$prompt" | grep -qiE '(api[_-]?key|bearer |token=|password|secret|aws_|ssh-rsa|-----BEGIN)' && exit 0

# Background insert to avoid latency
(
    DB_DIR="$HOME/.local/share/prompt-library"
    DB_FILE="$DB_DIR/prompts.db"
    [[ -f "$DB_FILE" ]] || exit 0

    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    session_id=$(echo "$input" | jq -r '.session_id // ""' 2>/dev/null)
    project=$(basename "$(pwd)")
    branch=$(git branch --show-current 2>/dev/null || echo "")
    repo_root=$(pwd)
    id=$(printf '%s%s' "$timestamp" "$prompt" | shasum -a 256 | cut -c1-8)

    escaped_prompt=$(echo "$prompt" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")

    sqlite3 "$DB_FILE" "INSERT OR IGNORE INTO prompts (id, timestamp, prompt, session_id, project, branch, repo_root, word_count)
        VALUES ('$id', '$timestamp', $escaped_prompt, '$session_id', '$project', '$branch', '$repo_root', $wc);" 2>/dev/null
) &

exit 0
