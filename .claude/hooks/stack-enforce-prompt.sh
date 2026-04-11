#!/usr/bin/env bash
# UserPromptSubmit hook: Intelligent stack enforcement with per-prompt advisory
# Fires ONCE per session on first prompt when on main/master.
# Derives a branch name suggestion from the prompt text.
#
# Output: [STACK ENFORCER] banner with personalized branch name
# Side effect: Creates /tmp/.claude-stack-advised-<uid>-<session-id> flag to suppress repeat messages

set -euo pipefail
trap 'exit 0' ERR

# CRITICAL: Consume stdin to prevent buffering issues (UserPromptSubmit requirement)
INPUT=$(cat 2>/dev/null || echo "{}")

# --- Extract from hook JSON payload ---
PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""' 2>/dev/null || echo "")
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""' 2>/dev/null || echo "")

# Bail if no prompt (shouldn't happen, but defensive)
[[ -z "$PROMPT" ]] && exit 0

# --- Git state ---
BRANCH=$(git branch --show-current 2>/dev/null || echo "")

# Only enforce on main/master
if [[ "$BRANCH" != "main" && "$BRANCH" != "master" ]]; then
    exit 0
fi

# --- Per-session flag to fire only ONCE ---
if [[ -z "$SESSION_ID" ]]; then
    SESSION_ID=$(date '+%s')  # Fallback to timestamp
fi
FLAG_FILE="/tmp/.claude-stack-advised-$(id -u)-${SESSION_ID}"

# If flag exists, suppress message (already warned this session)
if [[ -f "$FLAG_FILE" ]]; then
    exit 0
fi

# --- Derive branch name from prompt (client-side, no LLM) ---
derive_branch_name() {
    local text="$1"

    # Lowercase, remove non-alphanumeric, collapse spaces
    text=$(echo "$text" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9 ]/ /g' | tr -s ' ')

    # Take first 10 words
    local words=$(echo "$text" | awk '{for(i=1;i<=10;i++) printf $i" "}' | sed 's/ $//')

    # Remove stop words (common words that don't help naming)
    local stop_words="a an and the is are was were be been being have has had do does did will would could should may might must can in on at to for by with from of that this which who what when where why how i me my we our you your he him his she it its don be is and or not the"

    local filtered=""
    for word in $words; do
        if ! echo " $stop_words " | grep -qF " $word "; then
            filtered="$filtered $word"
        fi
    done

    # Slugify: spaces to hyphens, remove duplicates, trim
    local slug=$(echo "$filtered" | sed 's/^ //; s/ $//' | tr ' ' '-' | sed 's/-\+/-/g; s/^-//; s/-$//')

    # Cap at 40 chars
    echo "$slug" | cut -c1-40
}

DERIVED=$(derive_branch_name "$PROMPT")

# Fallback if derivation produced nothing
if [[ -z "$DERIVED" ]]; then
    DERIVED="task"
fi

# --- Write hint file so pre-tool-gate-v2.sh can reference it ---
HINT_FILE="/tmp/.claude-stack-hint-$(id -u)-${SESSION_ID}"
echo "$DERIVED" > "$HINT_FILE" 2>/dev/null || true

# --- Emit advisory banner ---
cat <<EOF
[STACK ENFORCER] You are on '$BRANCH'. Stack a branch before editing.
  Your task looks like: $DERIVED
  Suggested: stack create feature/$DERIVED $BRANCH
  This creates a worktree at .trees/$DERIVED/ — edit there instead.
  (This message fires once per session — next prompt will be clean.)

EOF

# --- Set flag to suppress on subsequent prompts ---
touch "$FLAG_FILE" 2>/dev/null || true

exit 0
