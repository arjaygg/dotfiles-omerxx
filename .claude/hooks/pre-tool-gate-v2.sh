#!/usr/bin/env bash
# Consolidated PreToolUse gate (v2)
# Replaces: pre-tool-gate.sh, serena-tool-priority.sh, edit-without-read.sh,
#           check-agent-parallelism.sh, plan-scope-gate.sh, plan-naming-enforcer
# Matcher: Bash|Read|Edit|Write|Grep|Glob|Agent
#
# Design: single process, jq for JSON parse (~3ms vs python3 ~30ms),
#         stdout only (never stderr), exit 0 or 1 (no exit 2).
#         No SQLite writes — metrics move to PostToolUse.

set -euo pipefail
trap 'echo "HOOK CRASH (pre-tool-gate-v2.sh line $LINENO): $BASH_COMMAND"' ERR

INPUT=$(cat)

# --- Single JSON parse via jq ---
eval "$(echo "$INPUT" | jq -r '
  @sh "TOOL_NAME=\(.tool_name // "")",
  @sh "FILE_PATH=\(.tool_input.file_path // .tool_input.path // "")",
  @sh "CMD=\(.tool_input.command // "")",
  @sh "LIMIT=\(.tool_input.limit // "")",
  @sh "PATTERN=\(.tool_input.pattern // "")",
  @sh "PROMPT=\(.tool_input.prompt // "")",
  @sh "SUBAGENT=\(.tool_input.subagent_type // "")",
  @sh "RUN_BG=\(.tool_input.run_in_background // false)",
  @sh "CONTENT=\(.tool_input.content // "")"
' 2>/dev/null)" 2>/dev/null || exit 0

# ============================================================
# SECTION 1: Read guards
# ============================================================
if [[ "$TOOL_NAME" == "Read" && -n "$FILE_PATH" ]]; then
    # 1a. Lock files — never read directly (backup for deny list)
    case "${FILE_PATH##*/}" in
        package-lock.json|yarn.lock|Cargo.lock|pnpm-lock.yaml|composer.lock|Gemfile.lock)
            echo "BLOCKED: Reading ${FILE_PATH##*/} directly wastes tokens. Use Grep to search for specific entries instead."
            exit 1 ;;
    esac

    # 1b. Large files without limit
    if [[ -f "$FILE_PATH" && -z "$LIMIT" ]]; then
        FILE_SIZE=$(stat -f%z "$FILE_PATH" 2>/dev/null || stat -c%s "$FILE_PATH" 2>/dev/null || echo 0)
        if [[ "$FILE_SIZE" -gt 102400 ]]; then
            echo "BLOCKED: $FILE_PATH is $(( FILE_SIZE / 1024 ))KB. Use Read with limit/offset or Grep to read only the relevant section."
            exit 1
        fi
    fi

    # 1c. .go files without limit — use Serena
    if [[ "$FILE_PATH" == *.go && -z "$LIMIT" ]]; then
        echo "BLOCKED: Reading entire .go file '$FILE_PATH' without limit/offset. Use Serena.getSymbolsOverview to understand structure, then Read with limit/offset for the specific symbol."
        exit 1
    fi

    # 1d. Source code without limit (non-.go, non-config) — check enforcement level
    if [[ -z "$LIMIT" && -f "$FILE_PATH" && -f "${HOME}/.config/pctx/pctx.json" ]]; then
        NON_CODE_EXT="md|json|yaml|yml|sql|txt|env|toml|csv|tsv|xml|html|css|lock|sum|mod|cfg|ini|conf|sh|bash|zsh"
        ext="${FILE_PATH##*.}"
        ext="${ext,,}"
        if [[ ! "$ext" =~ ^($NON_CODE_EXT)$ && "$FILE_PATH" != *.go ]]; then
            _HOOK_CFG="${HOME}/.dotfiles/.claude/hooks/hook-config.yaml"
            _SERENA_LEVEL="block"
            if [[ -f "$_HOOK_CFG" ]]; then
                _SERENA_LEVEL=$(grep '^serena-tool-priority:' "$_HOOK_CFG" 2>/dev/null | awk '{print $2}' | tr -d '[:space:]')
                [[ -z "$_SERENA_LEVEL" ]] && _SERENA_LEVEL="block"
            fi
            if [[ "$_SERENA_LEVEL" == "block" ]]; then
                echo "BLOCKED: Reading entire source file '$FILE_PATH' without limit/offset. Use Serena.getSymbolsOverview to understand structure, then LeanCtx.ctxRead or Read with limit/offset for specific symbols."
                exit 1
            else
                echo "HINT: Consider Serena.getSymbolsOverview for '$FILE_PATH' to see structure first, then Read with limit/offset for specific symbols."
                exit 0
            fi
        fi
    fi
fi

# ============================================================
# SECTION 2: Bash guards
# ============================================================
if [[ "$TOOL_NAME" == "Bash" ]]; then
    # 2a. grep (but not git grep) — use Grep tool
    if [[ ( "$CMD" == grep\ * || "$CMD" == grep\ -* ) && "$CMD" != *"git grep"* ]]; then
        echo "BLOCKED: Use the Grep tool (ripgrep-backed, gitignore-aware) or Serena.searchForPattern instead of 'grep'."
        exit 1
    fi

    # 2b. find → use Glob or Serena.findFile
    if [[ "$CMD" == find\ .* || "$CMD" == find\ /* ]]; then
        echo "BLOCKED: Use the Glob tool or Serena.findFile instead of 'find'. They are project-aware and faster."
        exit 1
    fi

    # 2c. plain ls (not ls -l* for symlink inspection)
    if [[ ( "$CMD" == ls\ * || "$CMD" == "ls" ) && "$CMD" != ls\ -l* ]]; then
        echo "BLOCKED: Use Glob or Serena.listDir instead of 'ls'. They are structured and token-efficient."
        exit 1
    fi

    # 2d. git commit on main/master
    if [[ "$CMD" == git\ commit* ]]; then
        CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
        if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
            echo "BLOCKED: You are about to commit directly to '$CURRENT_BRANCH'. Create a feature branch first: stack create <name> $CURRENT_BRANCH"
            exit 1
        fi
        # Block raw git commit when hyper-atomic hooks are installed
        _ATOMIC_HOOKS=$(git config --local core.hooksPath 2>/dev/null || echo "")
        if [[ "$_ATOMIC_HOOKS" == "$HOME/.dotfiles/git/hooks" ]]; then
            echo "BLOCKED: Use '~/.dotfiles/scripts/ai/commit.sh -m \"subject\" -m \"why\"' instead of raw git commit."
            exit 1
        fi
    fi

    # 2e. Invalidate atomic cache on git add
    if [[ "$CMD" == git\ add* ]]; then
        _repo_root_raw=$(git rev-parse --show-toplevel 2>/dev/null || echo "unknown")
        _REPO_HASH=$(printf '%s' "$_repo_root_raw" | md5 -q 2>/dev/null || printf '%s' "$_repo_root_raw" | md5sum 2>/dev/null | cut -d' ' -f1)
        rm -f "/tmp/.claude-atomic-state-$(id -u)-${_REPO_HASH}" 2>/dev/null || true
    fi
fi

# ============================================================
# SECTION 3: Edit guards
# ============================================================
if [[ "$TOOL_NAME" == "Edit" ]]; then
    # 3a. Edit without read check
    if [[ -n "$FILE_PATH" ]]; then
        READ_LOG="/tmp/.claude-read-log-$(id -u)"
        if [[ ! -f "$READ_LOG" ]] || ! grep -qF "$FILE_PATH" "$READ_LOG" 2>/dev/null; then
            echo "BLOCKED: Editing '$FILE_PATH' without reading it first. Use Read (or Serena.getSymbolsOverview) to understand the file before editing."
            exit 1
        fi
    fi

    # 3b. Kernel file edit caution (advisory)
    if [[ -n "$FILE_PATH" ]]; then
        _CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
        _IN_WORKTREE=0
        [[ "$FILE_PATH" =~ (^|/)\.trees/ ]] && _IN_WORKTREE=1
        _IN_GIT_REPO=0
        git rev-parse --is-inside-work-tree &>/dev/null && _IN_GIT_REPO=1
        for kernel in "CLAUDE.md" "RTK.md" ".claude/settings.json"; do
            if [[ "$FILE_PATH" == *"$kernel" ]]; then
                if [[ "$_IN_WORKTREE" -eq 0 && "$_IN_GIT_REPO" -eq 1 && ( "$_CURRENT_BRANCH" == "main" || "$_CURRENT_BRANCH" == "master" || -z "$_CURRENT_BRANCH" ) ]]; then
                    echo "CAUTION: Editing $kernel mid-session invalidates the LLM prompt cache. Proceed only if necessary."
                    exit 0
                fi
            fi
        done
    fi
fi

# ============================================================
# SECTION 4: Edit/Write — hyper-atomic state + plan scope
# ============================================================
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" ]]; then
    # 4a. Hyper-atomic state check
    _ATOMIC_HOOKS=$(git config --local core.hooksPath 2>/dev/null || echo "")
    if [[ "$_ATOMIC_HOOKS" == "$HOME/.dotfiles/git/hooks" ]]; then
        _repo_root_raw=$(git rev-parse --show-toplevel 2>/dev/null || echo "unknown")
        _REPO_HASH=$(printf '%s' "$_repo_root_raw" | md5 -q 2>/dev/null || printf '%s' "$_repo_root_raw" | md5sum 2>/dev/null | cut -d' ' -f1)
        _ATOMIC_CACHE="/tmp/.claude-atomic-state-$(id -u)-${_REPO_HASH}"
        _ATOMIC_TTL=4
        _ATOMIC_STATE="in_progress"
        if [[ -f "$_ATOMIC_CACHE" ]]; then
            _CACHE_AGE=$(( $(date '+%s') - $(date -r "$_ATOMIC_CACHE" '+%s' 2>/dev/null || echo 0) ))
            [[ $_CACHE_AGE -lt $_ATOMIC_TTL ]] && _ATOMIC_STATE=$(cat "$_ATOMIC_CACHE")
        fi
        if [[ "$_ATOMIC_STATE" == "in_progress" ]] || ! [[ -f "$_ATOMIC_CACHE" ]] || [[ ${_CACHE_AGE:-999} -ge $_ATOMIC_TTL ]]; then
            _ATOMIC_STATE=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" 2>/dev/null || echo "in_progress")
            echo "$_ATOMIC_STATE" > "$_ATOMIC_CACHE"
        fi
        case "$_ATOMIC_STATE" in
            blocked)
                echo "BLOCKED: Mixed concerns detected in staged files (state: blocked)."
                _DIAG=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" --verbose 2>&1 1>/dev/null || true)
                [[ -n "$_DIAG" ]] && echo "$_DIAG" | sed 's/^/  /'
                echo "  Commit or checkpoint current work before editing more files."
                exit 1
                ;;
            overgrown)
                echo "BLOCKED: Working tree is overgrown (state: overgrown)."
                _DIAG=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" --verbose 2>&1 1>/dev/null || true)
                [[ -n "$_DIAG" ]] && echo "$_DIAG" | sed 's/^/  /'
                echo "  Consider committing a subset before continuing."
                echo "  Run: ~/.dotfiles/scripts/ai/commit.sh -m 'subject' -m 'why'"
                exit 1
                ;;
            ready_to_commit)
                echo "BLOCKED: Changes are ready to commit (state: ready_to_commit)."
                echo "  Run: ~/.dotfiles/scripts/ai/commit.sh -m 'subject' -m 'why'"
                exit 1
                ;;
        esac
    fi

    # 4b. Plan scope gate
    if [[ -n "$FILE_PATH" && -f "plans/plan-state.json" ]]; then
        EXPECTED=$(jq -r '.expected_files[]' plans/plan-state.json 2>/dev/null || true)
        if [[ -n "$EXPECTED" ]]; then
            STEP=$(jq -r '.step_title // "unknown step"' plans/plan-state.json 2>/dev/null || echo "unknown step")
            if ! echo "$EXPECTED" | grep -qF "$FILE_PATH"; then
                echo "BLOCKED: '$FILE_PATH' is not in scope for current step: '$STEP'"
                echo "Expected files: $(echo "$EXPECTED" | tr '\n' ' ')"
                echo "To add a file to scope: update plans/plan-state.json expected_files[]"
                exit 1
            fi
        fi
    fi
fi

# ============================================================
# SECTION 5: Write — plan naming convention
# ============================================================
if [[ "$TOOL_NAME" == "Write" && -n "$FILE_PATH" ]]; then
    # Only check files in plans/ directory that are .md
    if [[ "$FILE_PATH" == */plans/*.md || "$FILE_PATH" == plans/*.md ]]; then
        FILENAME="${FILE_PATH##*/}"
        # Skip system files
        case "$FILENAME" in
            active-context*|decisions*|progress*|session-handoff*|plan-state*|pctx-functions*|hook-learning*|plan.md) ;;
            *)
                # Check naming convention: YYYY-MM-DD-context.md
                if [[ ! "$FILENAME" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}-.+\.md$ ]]; then
                    TODAY=$(date '+%Y-%m-%d')
                    echo "BLOCKED: Plan file '$FILENAME' doesn't follow naming convention."
                    echo "Expected format: YYYY-MM-DD-context.md (e.g., ${TODAY}-your-task-description.md)"
                    exit 1
                fi
                ;;
        esac
    fi
fi

# ============================================================
# SECTION 6: Grep/Glob — Serena/LeanCtx tool priority
# ============================================================
if [[ -f "${HOME}/.config/pctx/pctx.json" ]]; then
    # Read enforcement level from hook-config.yaml
    _HOOK_CFG="${HOME}/.dotfiles/.claude/hooks/hook-config.yaml"
    _SERENA_LEVEL="block"
    if [[ -f "$_HOOK_CFG" ]]; then
        _SERENA_LEVEL=$(grep '^serena-tool-priority:' "$_HOOK_CFG" 2>/dev/null | awk '{print $2}' | tr -d '[:space:]')
        [[ -z "$_SERENA_LEVEL" ]] && _SERENA_LEVEL="block"
    fi
    _SERENA_EXIT=0
    [[ "$_SERENA_LEVEL" == "block" ]] && _SERENA_EXIT=1
    _SERENA_PREFIX="HINT"
    [[ "$_SERENA_LEVEL" == "block" ]] && _SERENA_PREFIX="BLOCKED"

    # 6a. Grep — prefer LeanCtx.ctxSearch or Serena
    if [[ "$TOOL_NAME" == "Grep" && -n "$PATTERN" ]]; then
        if [[ "$PATTERN" =~ ^(func|class|type|struct|interface|def|fn)[[:space:]] ]]; then
            echo "$_SERENA_PREFIX: For symbol lookups, use Serena.findSymbol (structural) or LeanCtx.ctxSearch (token-efficient) instead of Grep."
            exit $_SERENA_EXIT
        fi
        if [[ "$PATTERN" =~ ^[A-Z][a-zA-Z0-9]+$ ]]; then
            echo "$_SERENA_PREFIX: '$PATTERN' looks like a symbol name. Use Serena.findSymbol('$PATTERN') for structural results, or LeanCtx.ctxSearch for pattern matching."
            exit $_SERENA_EXIT
        fi
        # General pattern — LeanCtx.ctxSearch is a direct drop-in
        echo "$_SERENA_PREFIX: Use LeanCtx.ctxSearch instead of Grep — it's gitignore-aware, session-cached, and token-efficient."
        exit $_SERENA_EXIT
    fi

    # 6b. Glob: specific filename → suggest Serena.findFile
    if [[ "$TOOL_NAME" == "Glob" && -n "$PATTERN" ]]; then
        if [[ "$PATTERN" =~ /[a-zA-Z0-9_-]+\.[a-zA-Z]+$ && ! "$PATTERN" =~ \*\.[a-zA-Z]+$ ]]; then
            FILENAME="${PATTERN##*/}"
            echo "HINT: For finding '$FILENAME', use Serena.findFile('$FILENAME') or LeanCtx.ctxTree for directory listings."
            exit 0
        fi
    fi
fi

# ============================================================
# SECTION 7: Agent — parallelism check
# ============================================================
if [[ "$TOOL_NAME" == "Agent" ]]; then
    # Exempt read-only and background agents
    if [[ "$SUBAGENT" == "Explore" || "$SUBAGENT" == "Plan" || "$RUN_BG" == "true" ]]; then
        exit 0
    fi
    NUMBERED_ITEMS=$(echo "$PROMPT" | grep -cE '^\s*[0-9]+\.\s' || true)
    BULLET_ITEMS=$(echo "$PROMPT" | grep -cE '^\s*[-]*\s+[A-Z]' || true)
    if [[ "$NUMBERED_ITEMS" -ge 3 || "$BULLET_ITEMS" -ge 3 ]]; then
        echo "HINT: This Agent call appears to involve multiple independent sub-tasks."
        echo "Use TaskCreate for parallel execution instead."
        echo "If tasks are truly sequential or dependent, rephrase your prompt to make that explicit."
        exit 0
    fi
fi

exit 0
