#!/usr/bin/env bash
# PreToolUse gate: block large lock files, warn on large reads, warn on kernel edits
# Claude Code passes tool input as JSON on stdin

set -euo pipefail

INPUT=$(cat)
TOOL_NAME="${CLAUDE_TOOL_NAME:-}"

# Extract file path from tool input
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('file_path', d.get('path', d.get('command', ''))))
except:
    print('')
" 2>/dev/null || echo "")

# --- Block reads of known-large lock files ---
LOCK_FILES=("package-lock.json" "yarn.lock" "Cargo.lock" "pnpm-lock.yaml" "composer.lock" "Gemfile.lock")
for lock in "${LOCK_FILES[@]}"; do
    if [[ "$FILE_PATH" == *"$lock" ]]; then
        echo "BLOCKED: Reading $lock directly wastes tokens. Use grep/search for specific entries instead." >&2
        exit 1
    fi
done

# --- Warn (advisory) when reading files >100KB without a line bound ---
if [[ "$TOOL_NAME" == "Read" && -n "$FILE_PATH" && -f "$FILE_PATH" ]]; then
    FILE_SIZE=$(stat -f%z "$FILE_PATH" 2>/dev/null || stat -c%s "$FILE_PATH" 2>/dev/null || echo 0)
    LIMIT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('limit', ''))
except:
    print('')
" 2>/dev/null || echo "")
    if [[ "$FILE_SIZE" -gt 102400 && -z "$LIMIT" ]]; then
        echo "WARNING: $FILE_PATH is $(( FILE_SIZE / 1024 ))KB. Consider using limit/offset or grep to read only the relevant section." >&2
        exit 2
    fi
fi

# --- Warn when using Bash instead of a dedicated native tool ---
if [[ "$TOOL_NAME" == "Bash" ]]; then
    CMD=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('command', '').lstrip())
except:
    print('')
" 2>/dev/null || echo "")

    # Block: cat → use Read tool
    if [[ "$CMD" == cat\ * ]]; then
        echo "WARNING: Use the Read tool instead of 'cat'. It's token-efficient, reviewable, and supports limit/offset." >&2
        exit 2
    fi

    # Block: grep (but not git grep) → use Grep tool or Serena.searchForPattern
    if [[ "$CMD" == grep\ * || "$CMD" == grep\ -* ]] && [[ "$CMD" != *"git grep"* ]]; then
        echo "WARNING: Use the Grep tool (ripgrep-backed, gitignore-aware) or Serena.searchForPattern instead of 'grep'." >&2
        exit 2
    fi

    # Block: find . → use Glob or Serena.findFile
    if [[ "$CMD" == find\ .* || "$CMD" == find\ /* ]]; then
        echo "WARNING: Use the Glob tool or Serena.findFile instead of 'find'. They are project-aware and faster." >&2
        exit 2
    fi

    # Block: git commit on main branch
    if [[ "$CMD" == git\ commit* ]]; then
        CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
        if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
            echo "WARNING: You are about to commit directly to '$CURRENT_BRANCH'. Create a feature branch first: stack create <name> $CURRENT_BRANCH" >&2
            exit 2
        fi
    fi
fi

# --- Warn when editing kernel files mid-session ---
KERNEL_FILES=("CLAUDE.md" "RTK.md" ".claude/settings.json")
for kernel in "${KERNEL_FILES[@]}"; do
    if [[ "$FILE_PATH" == *"$kernel" && "$TOOL_NAME" == "Edit" ]]; then
        echo "WARNING: Editing $kernel mid-session invalidates the LLM prompt cache. Proceed only if necessary." >&2
        exit 2
    fi
done

exit 0
