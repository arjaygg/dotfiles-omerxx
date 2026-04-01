#!/usr/bin/env bash
# prompt-library-score.sh — Update a prompt's score in the database.
# Usage: prompt-library-score.sh <id> <delta>
#   prompt-library-score.sh abc12345 +3
#   prompt-library-score.sh abc12345 -1
# Also supports: prompt-library-score.sh --recent <delta>
#   Scores the most recently captured prompt.

set -euo pipefail

DB_FILE="$HOME/.local/share/prompt-library/prompts.db"
[[ -f "$DB_FILE" ]] || { echo "Database not found: $DB_FILE" >&2; exit 1; }

if [[ "${1:-}" == "--recent" ]]; then
    delta="${2:?Usage: prompt-library-score.sh --recent <delta>}"
    id=$(sqlite3 "$DB_FILE" "SELECT id FROM prompts WHERE deleted=0 ORDER BY timestamp DESC LIMIT 1")
    [[ -z "$id" ]] && { echo "No prompts found" >&2; exit 1; }
else
    id="${1:?Usage: prompt-library-score.sh <id> <delta>}"
    delta="${2:?Usage: prompt-library-score.sh <id> <delta>}"
fi

# Validate delta is a number (with optional +/- prefix)
[[ "$delta" =~ ^[+-]?[0-9]+$ ]] || { echo "Invalid delta: $delta" >&2; exit 1; }

sqlite3 "$DB_FILE" "UPDATE prompts SET score = score + ($delta) WHERE id = '$id';"
new_score=$(sqlite3 "$DB_FILE" "SELECT score FROM prompts WHERE id = '$id';")
echo "Prompt $id score updated to $new_score (delta: $delta)"
