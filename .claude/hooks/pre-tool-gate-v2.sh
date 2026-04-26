#!/usr/bin/env bash
# Consolidated PreToolUse gate (v2)
# Replaces: pre-tool-gate.sh, serena-tool-priority.sh, edit-without-read.sh,
#           check-agent-parallelism.sh, plan-scope-gate.sh, plan-naming-enforcer
# Matcher: Bash|Read|Edit|Write|MultiEdit|Grep|Glob|Agent
#
# Design: single process, jq for JSON parse (~3ms vs python3 ~30ms),
#         stdout only (never stderr), exit 0 or 1 (no exit 2).
#         No SQLite writes — metrics move to PostToolUse.

set -euo pipefail
trap 'echo "HOOK CRASH (pre-tool-gate-v2.sh line $LINENO): $BASH_COMMAND"' ERR

# Source violation tracker
source "$HOME/.dotfiles/.claude/hooks/violation-tracker.sh" 2>/dev/null || true

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
# GUARD: empty TOOL_NAME → eval failed silently; block to prevent pass-through
# ============================================================
[[ -z "$TOOL_NAME" ]] && {
    echo "BLOCKED: hook parse failed (empty TOOL_NAME). Use a Serena MCP tool instead of a native file tool."
    exit 1
}

# ============================================================
# SECTION 0: Serena session-init gate
# Only active in real Claude sessions (CLAUDE_SESSION_ID is set by the runtime).
# Blocks Grep AND source-file Reads before Serena has been initialized, so the
# model is forced to call mcp__pctx__list_functions → Serena.initialInstructions() first.
# Plan/config files (.md, .json, .yaml) are exempt — only code files are gated.
# ============================================================
if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
    _INIT_FLAG="/tmp/.claude-serena-init-$(id -u)-${CLAUDE_SESSION_ID}"

    # Honor "skip if plans/pctx-functions.md was written today" — auto-set the temp flag
    # so a warmed session (file exists from today) doesn't re-block tools on a new session ID.
    if [[ ! -f "$_INIT_FLAG" ]]; then
        _PCTX_FILE="plans/pctx-functions.md"
        _TODAY=$(date '+%Y-%m-%d')
        _FILE_DATE=""
        if [[ -f "$_PCTX_FILE" ]]; then
            _FILE_DATE=$(date -r "$_PCTX_FILE" '+%Y-%m-%d' 2>/dev/null || \
                         stat -c '%y' "$_PCTX_FILE" 2>/dev/null | cut -d' ' -f1 || echo "")
        fi
        if [[ "$_FILE_DATE" == "$_TODAY" ]]; then
            touch "$_INIT_FLAG" 2>/dev/null || true
        fi
    fi

    if [[ ! -f "$_INIT_FLAG" ]]; then
        _INIT_STEPS="  1. Call mcp__pctx__list_functions\n  2. Write result to plans/pctx-functions.md\n  3. Call Serena.initialInstructions()"

        if [[ "$TOOL_NAME" == "Grep" ]]; then
            echo "BLOCKED: Serena not yet initialized this session."
            echo "  Before using Grep, complete the session init sequence:"
            printf '%b\n' "$_INIT_STEPS"
            echo "  This ensures structural (AST-level) search is available before falling back to text search."
            exit 1
        fi

        # Block Read on source code files — Serena.getSymbolsOverview must come first
        if [[ "$TOOL_NAME" == "Read" && -n "$FILE_PATH" ]]; then
            _SRC_EXT="go|ts|tsx|js|jsx|py|rs|java|kt|cs|cpp|c|h"
            _EXT="${FILE_PATH##*.}"
            _EXT="${_EXT,,}"
            if [[ "$_EXT" =~ ^($_SRC_EXT)$ ]]; then
                echo "BLOCKED: Reading source file '$FILE_PATH' before Serena init."
                echo "  Complete session init first:"
                printf '%b\n' "$_INIT_STEPS"
                echo "  Then use Serena.getSymbolsOverview to explore structure instead of reading the whole file."
                exit 1
            fi
        fi

        # Block Bash before init — Claude must not bypass init via shell commands.
        # The init sequence uses only MCP tools (mcp__pctx__list_functions,
        # mcp__pctx__execute_typescript) and the Write tool — no Bash needed.
        if [[ "$TOOL_NAME" == "Bash" ]]; then
            echo "BLOCKED: Bash not available before session init."
            echo "  Complete the session init sequence first:"
            printf '%b\n' "$_INIT_STEPS"
            echo "  Session init uses only MCP tools — no Bash required."
            exit 1
        fi
    fi
fi

# ============================================================
# SECTION 0B: Context-loaded gate (ctxIntent requirement)
# Blocks Grep unless LeanCtx.ctxIntent or ctxBatchExecute was called.
# These tools load live project context — always current, not manually curated.
# ============================================================
if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
    _CTX_FLAG="/tmp/.claude-ctx-loaded-$(id -u)-${CLAUDE_SESSION_ID}"
    if [[ "$TOOL_NAME" == "Grep" && ! -f "$_CTX_FLAG" ]]; then
        echo "BLOCKED: Context not yet loaded in this session."
        echo "  Before using Grep, load project context with:"
        echo "    LeanCtx.ctxIntent({ query: '<your task description>' })"
        echo "  Batch it in: mcp__pctx__execute_typescript"
        echo "  This indexes live project context — derived from current codebase, not manually curated."
        exit 1
    fi
fi

# ============================================================
# SECTION 1B: Serena/pctx batching threshold gate
# Blocks excessive sequential calls to Serena/pctx tools without execute_typescript batching.
# ============================================================
if [[ "$TOOL_NAME" == mcp__serena__* ]] || [[ "$TOOL_NAME" == mcp__pctx__* ]]; then
    if [[ "$TOOL_NAME" != "mcp__pctx__execute_typescript" ]]; then
        # Direct Serena/pctx call (not batched) — check counter
        _COUNTER_FILE="/tmp/.claude-serena-calls-$(id -u)-${SESSION_ID}"
        if [[ -f "$_COUNTER_FILE" ]]; then
            _COUNT=$(wc -l < "$_COUNTER_FILE" 2>/dev/null || echo 0)
            if [[ "$_COUNT" -ge 4 ]]; then
                echo "BLOCKED: $_COUNT sequential Serena/pctx calls without batching."
                echo "  Use: mcp__pctx__execute_typescript with Promise.all() to batch multiple calls."
                exit 1
            fi
        fi
    fi
fi

# ============================================================
# SECTION 1: Read guards
# ============================================================
if [[ "$TOOL_NAME" == "Read" && -n "$FILE_PATH" ]]; then
    # 1a. Lock files — never read directly (backup for deny list)
    case "${FILE_PATH##*/}" in
        package-lock.json|yarn.lock|Cargo.lock|pnpm-lock.yaml|composer.lock|Gemfile.lock)
            echo "BLOCKED: Reading ${FILE_PATH##*/} directly wastes tokens. Use Grep to search for specific entries instead."
            log_violation "level1_block" "pre_tool_gate" "Read" "$FILE_PATH" "lock_file_read" 2>/dev/null || true
            exit 1 ;;
    esac

    # 1a-extra. Generated/bulk files by pattern — repomix outputs, go.sum, lock files
    _fname="${FILE_PATH##*/}"
    if [[ "$_fname" == *_repomix_* || "$FILE_PATH" == *.sum || "$FILE_PATH" == *-lock.* ]]; then
        echo "BLOCKED: ${_fname} is a generated/lock file — no direct-read value. Use ctxSmartRead or Grep to search specific entries."
        log_violation "level1_block" "pre_tool_gate" "Read" "$FILE_PATH" "generated_file_read" 2>/dev/null || true
        exit 1
    fi

    # 1b. Large files without limit — tiered by size
    if [[ -f "$FILE_PATH" && -z "$LIMIT" ]]; then
        FILE_SIZE=$(stat -f%z "$FILE_PATH" 2>/dev/null || stat -c%s "$FILE_PATH" 2>/dev/null || echo 0)
        if [[ "$FILE_SIZE" -gt 512000 ]]; then
            echo "BLOCKED: $FILE_PATH is $(( FILE_SIZE / 1024 ))KB — use LeanCtx.ctxSmartRead(\"$FILE_PATH\") for analysis-only reads."
            exit 1
        elif [[ "$FILE_SIZE" -gt 102400 ]]; then
            echo "BLOCKED: $FILE_PATH is $(( FILE_SIZE / 1024 ))KB. Use Read with limit/offset or Grep to read only the relevant section."
            exit 1
        fi
    fi

    # 1c. .go files without limit — use Serena
    if [[ "$FILE_PATH" == *.go && -z "$LIMIT" ]]; then
        echo "BLOCKED: Reading entire .go file '$FILE_PATH' without limit/offset. Use Serena.getSymbolsOverview to understand structure, then Read with limit/offset for the specific symbol."
        echo "  Call via: mcp__pctx__execute_typescript with: await Serena.getSymbolsOverview('${FILE_PATH}')"
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
                echo "  Call via: mcp__pctx__execute_typescript with: await Serena.getSymbolsOverview('${FILE_PATH}')"
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
        echo "BLOCKED: Use the Grep tool or LeanCtx.ctxSearch instead of 'grep'."
        echo "  Call via: mcp__pctx__execute_typescript with: await LeanCtx.ctxSearch({ query: '<pattern>' })"
        exit 1
    fi

    # 2b. find → use Glob or Serena.findFile
    if [[ "$CMD" == find\ .* || "$CMD" == find\ /* ]]; then
        echo "BLOCKED: Use the Glob tool or Serena.findFile instead of 'find'."
        echo "  Call via: Glob tool with a glob pattern, or: await Serena.findFile('<filename>')"
        exit 1
    fi

    # 2c. plain ls (not ls -l* for symlink inspection)
    if [[ ( "$CMD" == ls\ * || "$CMD" == "ls" ) && "$CMD" != ls\ -l* ]]; then
        echo "BLOCKED: Use the Glob tool or Serena.listDir instead of 'ls'."
        echo "  Call via: Glob tool with pattern, or: await Serena.listDir('<path>')"
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

    # 2f. Poll loop advisory — suggest Monitor for event-watching patterns (advisory, non-blocking)
    if echo "$CMD" | grep -qE 'while (true|\[::\])'; then
        if echo "$CMD" | grep -qE '(gh (run|pr|workflow)|kubectl|tail -f|curl.*http|argocd)' && \
           echo "$CMD" | grep -qE 'sleep [0-9]'; then
            echo "[MONITOR HINT] This command looks like a poll loop. If the goal is event-watching (notify when condition changes), the Monitor tool is more efficient — zero tokens when silent, vs this loop which costs tokens on every iteration. See ai/rules/monitor-patterns.md."
        fi
    fi

    # 2g. Piped text processors — catch 'cmd | head', 'cmd | grep', etc. (deny list only catches prefixes)
    if echo "$CMD" | grep -qE '\| *(head|tail|cat|sed|awk|grep|rg)( |$)'; then
        PIPE_CMD=$(echo "$CMD" | grep -oE '\| *(head|tail|cat|sed|awk|grep|rg)' | head -1 | tr -d '| ')
        echo "BLOCKED: Piped '$PIPE_CMD' is not allowed after a command."
        echo "  Use the Read tool with a limit parameter, jq for JSON output, or LeanCtx.ctxSearch for text search."
        echo "  Call via: mcp__pctx__execute_typescript with: await LeanCtx.ctxSearch({ query: '<pattern>' })"
        exit 1
    fi
fi

# ============================================================
# SECTION 3: Edit guards
# ============================================================
# 3a. Edit/MultiEdit without read check
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "MultiEdit" ]]; then
    if [[ -n "$FILE_PATH" ]]; then
        READ_LOG="/tmp/.claude-read-log-$(id -u)"
        if [[ ! -f "$READ_LOG" ]] || ! grep -qF "$FILE_PATH" "$READ_LOG" 2>/dev/null; then
            echo "BLOCKED: Editing '$FILE_PATH' without reading it first. Use Read (or Serena.getSymbolsOverview) to understand the file before editing."
            exit 1
        fi
    fi
fi

# 3b. Edit/Write/MultiEdit on main/master branch — hard block (stacking enforcement)
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "MultiEdit" ]]; then
    if [[ -n "$FILE_PATH" ]]; then
        _EDIT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
        if [[ "$_EDIT_BRANCH" == "main" || "$_EDIT_BRANCH" == "master" ]]; then
            # Exempt: plans/ files (session bookkeeping, always on current branch)
            #         .trees/ paths (already in a worktree)
            if [[ ! "$FILE_PATH" =~ (^|/)(plans|\.trees)/ ]]; then
                _SUGGESTED_BRANCH=""
                _HINT_FILE="/tmp/.claude-stack-hint-$(id -u)-${CLAUDE_SESSION_ID:-}"
                [[ -f "$_HINT_FILE" ]] && _SUGGESTED_BRANCH=$(cat "$_HINT_FILE" 2>/dev/null)
                echo "BLOCKED: Editing '$FILE_PATH' on '$_EDIT_BRANCH'. Create a stacked branch first:"
                if [[ -n "$_SUGGESTED_BRANCH" ]]; then
                    echo "  stack create feature/$_SUGGESTED_BRANCH $_EDIT_BRANCH"
                else
                    echo "  stack create feature/<name> $_EDIT_BRANCH"
                fi
                echo "  This creates a worktree at .trees/<name>/ — edit there instead."
                exit 1
            fi
        fi
    fi
fi

# 3c. Kernel file edit caution (advisory)
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "MultiEdit" ]]; then
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
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "MultiEdit" ]]; then
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
                [[ -n "$_DIAG" ]] && echo "${_DIAG//$'\n'/$'\n'  }"
                echo "  Commit or checkpoint current work before editing more files."
                log_violation "level1_block" "pre_tool_gate" "$TOOL_NAME" "$FILE_PATH" "atomic_blocked" 2>/dev/null || true
                exit 1
                ;;
            overgrown)
                echo "BLOCKED: Working tree is overgrown (state: overgrown)."
                _DIAG=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" --verbose 2>&1 1>/dev/null || true)
                [[ -n "$_DIAG" ]] && echo "${_DIAG//$'\n'/$'\n'  }"
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
                echo "BLOCKED: '$FILE_PATH' is not in scope for current step: '$STEP'" >&2
                echo "Expected files: $(echo "$EXPECTED" | tr '\n' ' ')" >&2
                echo "To add a file to scope: update plans/plan-state.json expected_files[]" >&2
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
                    echo "BLOCKED: Plan file '$FILENAME' doesn't follow naming convention." >&2
                    echo "Expected format: YYYY-MM-DD-context.md (e.g., ${TODAY}-your-task-description.md)" >&2
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
            echo "$_SERENA_PREFIX: For symbol lookups, use Serena.findSymbol (structural) or LeanCtx.ctxSearch (token-efficient) instead of Grep." >&2
            echo "  Call via: mcp__pctx__execute_typescript with: await Serena.findSymbol({ name: '<symbol>' })" >&2
            exit $_SERENA_EXIT
        fi
        if [[ "$PATTERN" =~ ^[A-Z][a-zA-Z0-9]+$ ]]; then
            echo "$_SERENA_PREFIX: '$PATTERN' looks like a symbol name. Use Serena.findSymbol('$PATTERN') for structural results, or LeanCtx.ctxSearch for pattern matching." >&2
            echo "  Call via: mcp__pctx__execute_typescript with: await Serena.findSymbol({ name: '${PATTERN}' })" >&2
            exit $_SERENA_EXIT
        fi
        # General pattern — LeanCtx.ctxSearch is a direct drop-in
        echo "$_SERENA_PREFIX: Use LeanCtx.ctxSearch instead of Grep — it's gitignore-aware, session-cached, and token-efficient." >&2
        echo "  Call via: mcp__pctx__execute_typescript with: await LeanCtx.ctxSearch({ query: '${PATTERN}' })" >&2
        exit $_SERENA_EXIT
    fi

    # 6b. Glob: specific filename → suggest Serena.findFile
    if [[ "$TOOL_NAME" == "Glob" && -n "$PATTERN" ]]; then
        if [[ "$PATTERN" =~ /[a-zA-Z0-9_-]+\.[a-zA-Z]+$ && ! "$PATTERN" =~ \*\.[a-zA-Z]+$ ]]; then
            FILENAME="${PATTERN##*/}"
            echo "HINT: For finding '$FILENAME', use Serena.findFile('$FILENAME') or LeanCtx.ctxTree for directory listings." >&2
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
        echo "HINT: This Agent call appears to involve multiple independent sub-tasks." >&2
        echo "Use TaskCreate for parallel execution instead." >&2
        echo "If tasks are truly sequential or dependent, rephrase your prompt to make that explicit." >&2
        exit 0
    fi
fi

# Log successful pass-through (Level 1 allowed operation)
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "Bash" || "$TOOL_NAME" == "Read" ]]; then
    log_violation "level1_pass" "pre_tool_gate" "$TOOL_NAME" "$FILE_PATH" "" 2>/dev/null || true
    [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" ]] && log_operation "edit" "$FILE_PATH" 2>/dev/null || true
fi

exit 0
