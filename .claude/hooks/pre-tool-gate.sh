#!/usr/bin/env bash
# PreToolUse gate: block large lock files, warn on large reads, warn on kernel edits
# Claude Code passes tool input as JSON on stdin:
# {"session_id":"...","tool_name":"Bash","tool_input":{"command":"...","file_path":"...",...}}

set -euo pipefail

INPUT=$(cat)

# Parse all fields in one python3 call — tool_name at top level, rest inside tool_input
# Use \001 (non-whitespace) as separator so bash read preserves empty fields
IFS=$'\001' read -r TOOL_NAME FILE_PATH CMD LIMIT < <(
    echo "$INPUT" | python3 -c "
import sys, json
SEP = '\x01'
try:
    d = json.load(sys.stdin)
    tool_name = d.get('tool_name', '')
    ti = d.get('tool_input', {})
    file_path = ti.get('file_path', ti.get('path', ''))
    command = ti.get('command', '')
    limit = str(ti.get('limit', ''))
    print(SEP.join([tool_name, file_path, command, limit]))
except:
    print(SEP * 3)
" 2>/dev/null || printf '\001\001\001'
)

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
    if [[ "$FILE_SIZE" -gt 102400 && -z "$LIMIT" ]]; then
        echo "WARNING: $FILE_PATH is $(( FILE_SIZE / 1024 ))KB. Consider using limit/offset or grep to read only the relevant section." >&2
        exit 2
    fi
fi

# --- Warn when reading a .go file without limit/offset (symbol-lookup violation) ---
# Reading a whole .go file is almost always unnecessary — Serena.getSymbolsOverview
# gives the structure without flooding the context window.
if [[ "$TOOL_NAME" == "Read" && "$FILE_PATH" == *.go && -z "$LIMIT" ]]; then
    echo "WARNING: Reading entire .go file '$FILE_PATH' without limit/offset. Prefer Serena.getSymbolsOverview to understand structure, then Read with limit/offset for the specific symbol." >&2
    exit 2
fi

# --- Warn when using Bash instead of a dedicated native tool ---
if [[ "$TOOL_NAME" == "Bash" ]]; then
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

    # Block: rg (ripgrep) → use Grep tool (same reason as grep)
    if [[ "$CMD" == rg\ * || "$CMD" == rg\ -* ]]; then
        echo "WARNING: Use the Grep tool instead of 'rg'. It is gitignore-aware and token-efficient." >&2
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
# Skip warning in worktrees (.trees/) or on non-main/master branches — safe to edit there.
_CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
_IN_WORKTREE=0
[[ "$FILE_PATH" =~ (^|/)\.trees/ ]] && _IN_WORKTREE=1
KERNEL_FILES=("CLAUDE.md" "RTK.md" ".claude/settings.json")
for kernel in "${KERNEL_FILES[@]}"; do
    if [[ "$FILE_PATH" == *"$kernel" && "$TOOL_NAME" == "Edit" ]]; then
        if [[ "$_IN_WORKTREE" -eq 1 || ( "$_CURRENT_BRANCH" != "main" && "$_CURRENT_BRANCH" != "master" && -n "$_CURRENT_BRANCH" ) ]]; then
            # Worktree or feature branch — safe, allow without warning
            :
        else
            echo "WARNING: Editing $kernel mid-session invalidates the LLM prompt cache. Proceed only if necessary." >&2
            exit 2
        fi
    fi
done

# --- Hyper-atomic: block Edit/Write when state is blocked/overgrown ---
# Atomic state is cached for 8s to avoid running the script on every keystroke edit.
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" ]]; then
    _ATOMIC_HOOKS=$(git config --local core.hooksPath 2>/dev/null || echo "")
    if [[ "$_ATOMIC_HOOKS" == "$HOME/.dotfiles/git/hooks" ]]; then
        _ATOMIC_CACHE="/tmp/.claude-atomic-state-$(id -u)"
        _ATOMIC_TTL=8
        _ATOMIC_STATE="in_progress"
        if [[ -f "$_ATOMIC_CACHE" ]]; then
            _CACHE_AGE=$(( $(date '+%s') - $(date -r "$_ATOMIC_CACHE" '+%s' 2>/dev/null || echo 0) ))
            [[ $_CACHE_AGE -lt $_ATOMIC_TTL ]] && _ATOMIC_STATE=$(cat "$_ATOMIC_CACHE")
        fi
        if [[ "$_ATOMIC_STATE" == "in_progress" ]] || ! [[ -f "$_ATOMIC_CACHE" ]] || [[ $_CACHE_AGE -ge $_ATOMIC_TTL ]]; then
            _ATOMIC_STATE=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" 2>/dev/null || echo "in_progress")
            echo "$_ATOMIC_STATE" > "$_ATOMIC_CACHE"
        fi
        case "$_ATOMIC_STATE" in
            blocked)
                echo "BLOCKED: Mixed concerns detected in staged files (state: blocked)." >&2
                echo "  Commit or checkpoint current work before editing more files." >&2
                echo "  Run: ~/.dotfiles/scripts/ai/atomic-status.sh  to diagnose." >&2
                exit 1
                ;;
            overgrown)
                echo "WARNING: Working tree is overgrown (state: overgrown)." >&2
                echo "  Consider committing a subset before continuing." >&2
                echo "  Run: ~/.dotfiles/scripts/ai/commit.sh -m 'subject' -m 'why'" >&2
                exit 2
                ;;
            ready_to_commit)
                echo "WARNING: Changes are ready to commit (state: ready_to_commit)." >&2
                echo "  Run: ~/.dotfiles/scripts/ai/commit.sh -m 'subject' -m 'why'" >&2
                exit 2
                ;;
        esac
    fi
fi

# --- Block raw git commit when hyper-atomic hooks are installed ---
if [[ "$TOOL_NAME" == "Bash" && "$CMD" == git\ commit* ]]; then
    _ATOMIC_HOOKS=$(git config --local core.hooksPath 2>/dev/null || echo "")
    if [[ "$_ATOMIC_HOOKS" == "$HOME/.dotfiles/git/hooks" ]]; then
        echo "BLOCKED: Use '~/.dotfiles/scripts/ai/commit.sh -m \"subject\" -m \"why\"' instead of raw git commit." >&2
        exit 1
    fi
fi

exit 0
