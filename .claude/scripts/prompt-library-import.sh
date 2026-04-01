#!/usr/bin/env bash
# prompt-library-import.sh — Bootstrap prompt library from Claude Code transcripts.
# Scans ~/.claude/projects/ for session JSONL files, extracts user prompts,
# and inserts them into the SQLite database. Idempotent (safe to re-run).
#
# Usage: prompt-library-import.sh [--dry-run]

set -euo pipefail

DB_DIR="$HOME/.local/share/prompt-library"
DB_FILE="$DB_DIR/prompts.db"
DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

mkdir -p "$DB_DIR"

# ── Initialize SQLite schema ────────────────────────────────────────────────
sqlite3 "$DB_FILE" <<'SQL'
CREATE TABLE IF NOT EXISTS prompts (
  id TEXT PRIMARY KEY,
  timestamp TEXT NOT NULL,
  prompt TEXT NOT NULL,
  session_id TEXT,
  project TEXT,
  branch TEXT,
  repo_root TEXT,
  word_count INTEGER,
  score INTEGER DEFAULT 0,
  reuse_count INTEGER DEFAULT 0,
  starred INTEGER DEFAULT 0,
  promoted INTEGER DEFAULT 0,
  deleted INTEGER DEFAULT 0,
  tags TEXT DEFAULT '[]',
  llm_rating REAL DEFAULT 0,
  embedding BLOB
);
CREATE INDEX IF NOT EXISTS idx_prompts_score ON prompts(score DESC);
CREATE INDEX IF NOT EXISTS idx_prompts_timestamp ON prompts(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_prompts_promoted ON prompts(promoted);
SQL

PROJECTS_DIR="$HOME/.claude/projects"
[[ -d "$PROJECTS_DIR" ]] || { echo "No projects directory found at $PROJECTS_DIR"; exit 0; }

imported=0
skipped=0
dupes=0

# Secret patterns to filter out (case-insensitive grep -E)
SECRET_RE='(api[_-]?key|bearer |token=|password|secret|aws_|ssh-rsa|-----BEGIN)'

# ── Process each main session JSONL (skip subagents/) ───────────────────────
while IFS= read -r jsonl_file; do
    # Extract project name from directory encoding: -Users-axos-agallentes-git-myproject → myproject
    project_dir=$(basename "$(dirname "$jsonl_file")")
    project_name=$(echo "$project_dir" | sed 's/.*-git-//' | sed 's/.*--//')

    session_id=$(basename "$jsonl_file" .jsonl)

    # Process each user message line
    while IFS= read -r line; do
        # Extract fields from the JSON line
        msg_type=$(echo "$line" | jq -r '.type // ""' 2>/dev/null)
        [[ "$msg_type" == "user" ]] || continue

        is_meta=$(echo "$line" | jq -r '.isMeta // false' 2>/dev/null)
        [[ "$is_meta" == "true" ]] && continue

        timestamp=$(echo "$line" | jq -r '.timestamp // ""' 2>/dev/null)
        branch=$(echo "$line" | jq -r '.gitBranch // ""' 2>/dev/null)
        cwd=$(echo "$line" | jq -r '.cwd // ""' 2>/dev/null)

        # Extract text content (handles both string and array content)
        prompt=$(echo "$line" | jq -r '
            .message.content |
            if type == "string" then .
            elif type == "array" then
                [.[] | select(.type == "text") | .text] | join("\n")
            else ""
            end
        ' 2>/dev/null)

        # Skip empty prompts
        [[ -z "$prompt" ]] && continue

        # Skip slash commands
        [[ "$prompt" =~ ^/ ]] && continue
        echo "$prompt" | grep -q '<command-name>/' && continue

        # Skip system-reminder-only messages
        echo "$prompt" | grep -q '<system-reminder>' && {
            clean=$(echo "$prompt" | sed 's/<system-reminder>.*<\/system-reminder>//g' | tr -d '[:space:]')
            [[ -z "$clean" ]] && continue
        }

        # Strip system-reminder tags for the stored prompt
        prompt=$(echo "$prompt" | sed 's/<system-reminder>.*<\/system-reminder>//g' | sed '/^$/d')
        [[ -z "$prompt" ]] && continue

        # Word count filter (≥8 words)
        wc=$(echo "$prompt" | wc -w | tr -d ' ')
        [[ "$wc" -lt 8 ]] && { ((skipped++)) || true; continue; }

        # Secret filter
        echo "$prompt" | grep -qiE "$SECRET_RE" && { ((skipped++)) || true; continue; }

        # Generate deterministic ID
        id=$(printf '%s%s' "$timestamp" "$prompt" | shasum -a 256 | cut -c1-8)

        if $DRY_RUN; then
            echo "[DRY] id=$id wc=$wc project=$project_name prompt=$(echo "$prompt" | cut -c1-80)..."
            ((imported++)) || true
            continue
        fi

        # Insert (ignore duplicates via OR IGNORE on PRIMARY KEY)
        sqlite3 "$DB_FILE" "INSERT OR IGNORE INTO prompts (id, timestamp, prompt, session_id, project, branch, repo_root, word_count)
            VALUES ('$id', '$timestamp', $(echo "$prompt" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))"), '$session_id', '$project_name', '$branch', '$cwd', $wc);" 2>/dev/null && {
            ((imported++)) || true
        } || {
            ((dupes++)) || true
        }

    done < "$jsonl_file"

done < <(find "$PROJECTS_DIR" -maxdepth 2 -name "*.jsonl" ! -path "*/subagents/*" 2>/dev/null)

echo "Import complete: $imported imported, $skipped filtered, $dupes duplicates"
echo "Database: $DB_FILE"
$DRY_RUN || echo "Total prompts: $(sqlite3 "$DB_FILE" "SELECT count(*) FROM prompts")"
