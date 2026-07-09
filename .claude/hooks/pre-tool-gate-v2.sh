#!/usr/bin/env bash
# Consolidated PreToolUse gate (v2)
# Replaces: pre-tool-gate.sh, serena-tool-priority.sh, edit-without-read.sh,
#           check-agent-parallelism.sh, plan-scope-gate.sh, plan-naming-enforcer,
#           pr-title-conventional-guard.sh, git-commit-guard.sh, pre-push-remote-check.sh
#           (folded 2026-07-08, H2 — see Section 2h/2i/2j)
# Matcher: Bash|Read|Edit|Write|MultiEdit|Grep|Glob|Agent
#
# NOT folded in (left as standalone PreToolUse entries in settings.json):
#   rtk-rewrite.sh, `lean-ctx hook rewrite` — both mutate tool_input.command
#   before it runs. Their content/ordering interaction with this gate's own
#   command-rewrite path (Section 2g pipe-stripping) was not fully verifiable
#   from this worktree (rtk-rewrite.sh lives only at the live, untracked
#   ~/.claude/hooks/rtk-rewrite.sh, not in the tracked repo), so folding them
#   in was judged too risky to do blind. Conservatively left separate.
#
# Design: single process, jq for JSON parse (~3ms vs python3 ~30ms).
#         No SYNCHRONOUS SQLite writes on this path — hook_metric()/
#         hook_learning_metric() (R8, 2026-07-09) are flat-file appends only;
#         they're drained into metrics.db by hook-graduate.sh's cmd_flush.
#
# Blocking semantics (fixed 2026-06-12):
#   Claude Code halts a tool call only when a PreToolUse hook exits 2 or emits
#   JSON {"hookSpecificOutput":{"permissionDecision":"deny",...}} on stdout
#   with exit 0. A plain `exit 1` is a NON-BLOCKING error: the tool runs
#   anyway, the model never receives the message, and the UI renders a red
#   "PreToolUse hook error — Failed with non-blocking status code". That is
#   why BLOCKED messages used to repeat forever. All block sites now call
#   _deny(): the tool is actually halted AND the reason is fed back to the
#   model so it self-corrects in the same turn.

set -euo pipefail
trap 'echo "HOOK CRASH (pre-tool-gate-v2.sh line $LINENO): $BASH_COMMAND" >&2' ERR

_START_NS=$(date +%s%N 2>/dev/null || echo 0)
_DENIED=0
_DENY_TOOL=""

# Halt the tool call: emit PreToolUse JSON deny on stdout, mirror reason to
# stderr for the UI. stdout must contain ONLY this JSON — never echo anything
# else to stdout on a code path that can reach _deny.
_deny() {
    local reason="[HARD-BLOCK — DO NOT RETRY] $1"
    _DENIED=1
    _DENY_TOOL="${TOOL_NAME:-}"
    printf '%s\n' "$reason" >&2
    jq -cn --arg r "$reason" \
        '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
    exit 0
}

# RC7 fix (R8b, 2026-07-09): every _deny() call and every clean pass-through
# runs through here via EXIT trap (installed after hook-metrics.sh is
# sourced below) so hook_events/learning_events actually get populated —
# previously this script never sourced hook-metrics.sh at all. Uses a
# per-session flag file to classify the reaction to a PRIOR block: same tool
# retried => block_repeat, a different/allowed tool used next => block_recover.
_finalize_metrics() {
    [[ "${_METRICS_LOGGED:-0}" -eq 1 ]] && return 0
    _METRICS_LOGGED=1
    declare -f hook_metric >/dev/null 2>&1 || return 0

    local end_ns dur_ms exit_code=0
    end_ns=$(date +%s%N 2>/dev/null || echo 0)
    dur_ms=$(( (end_ns - _START_NS) / 1000000 ))
    [[ "$_DENIED" -eq 1 ]] && exit_code=2
    hook_metric "pre-tool-gate-v2" "${TOOL_NAME:-}" "$exit_code" "${EFFECTIVE_SESSION_ID:-}" "$dur_ms"

    local block_flag="/tmp/.claude-last-block-$(id -u)-${EFFECTIVE_SESSION_ID:-default}"
    if [[ "$_DENIED" -eq 1 ]]; then
        if [[ -f "$block_flag" ]] && [[ "$(cat "$block_flag" 2>/dev/null)" == "$_DENY_TOOL" ]]; then
            hook_learning_metric "${EFFECTIVE_SESSION_ID:-}" "pre-tool-gate-v2" "block_repeat" "$_DENY_TOOL" ""
        fi
        printf '%s' "$_DENY_TOOL" > "$block_flag" 2>/dev/null || true
    elif [[ -f "$block_flag" ]]; then
        local prev_tool
        prev_tool=$(cat "$block_flag" 2>/dev/null || echo "")
        if [[ -n "$prev_tool" ]]; then
            hook_learning_metric "${EFFECTIVE_SESSION_ID:-}" "pre-tool-gate-v2" "block_recover" "$prev_tool" "${TOOL_NAME:-}"
        fi
        rm -f "$block_flag" 2>/dev/null || true
    fi
}

# Resolve the current branch of the repo that actually owns a file path,
# rather than the hook process's own cwd — a bare `git branch --show-current`
# reflects the session's home repo, which is wrong for any FILE_PATH pointing
# into a different repo (e.g. a cross-repo Write via absolute path).
_branch_for_path() {
    local path="$1"
    local dir
    dir=$(dirname -- "$path" 2>/dev/null) || return 0
    git -C "$dir" branch --show-current 2>/dev/null || echo ""
}

# Declarative block/warn rules from hook-config.yaml (sed/awk/echo/printf/tee
# redirects, read-guards for node_modules/go.sum/repomix output). Sourced
# after _deny() so check_bash_cmd_rules/check_read_path_rules use it directly
# instead of the non-blocking exit 1 fallback.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=hook-rule-loader.sh
source "${SCRIPT_DIR}/hook-rule-loader.sh"
# shellcheck source=hook-metrics.sh
source "${SCRIPT_DIR}/hook-metrics.sh" 2>/dev/null || true

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
  @sh "CONTENT=\(.tool_input.content // "")",
  @sh "SESSION_ID=\(.session_id // "")"
' 2>/dev/null)" 2>/dev/null || exit 0

# session_id arrives via the stdin JSON payload, not an env var — no
# CLAUDE_SESSION_ID is ever set in hook environments. EFFECTIVE_SESSION_ID
# mirrors post-tool-analytics.sh's fallback so flag files set by one script
# are found by the other.
EFFECTIVE_SESSION_ID="${SESSION_ID:-${CLAUDE_SESSION_ID:-default}}"

# Installed once EFFECTIVE_SESSION_ID/TOOL_NAME exist so _finalize_metrics can
# see them; fires on every exit path below (deny, warn/hint early-return, or
# the final pass-through exit 0).
trap _finalize_metrics EXIT

# ============================================================
# GUARD: empty TOOL_NAME → eval failed silently; block to prevent pass-through
# ============================================================
[[ -z "$TOOL_NAME" ]] && _deny "BLOCKED: hook parse failed (empty TOOL_NAME). Use a Serena MCP tool instead of a native file tool."

_INIT_STEPS=$'  1. Call mcp__pctx__list_functions\n  2. Write result to plans/pctx-functions.md\n  3. Call Serena.initialInstructions()'

# ============================================================
# SECTION 0: Serena session-init gate
# Only active in real Claude sessions (session_id present in the stdin payload).
# Blocks Grep AND source-file Reads before Serena has been initialized, so the
# model is forced to call mcp__pctx__list_functions → Serena.initialInstructions() first.
# Plan/config files (.md, .json, .yaml) are exempt — only code files are gated.
# ============================================================
if [[ -n "$SESSION_ID" ]]; then
    _INIT_FLAG="/tmp/.claude-serena-init-$(id -u)-${EFFECTIVE_SESSION_ID}"

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
        if [[ "$TOOL_NAME" == "Grep" ]]; then
            _deny "BLOCKED: Serena not yet initialized this session.
  Before using Grep, complete the session init sequence:
${_INIT_STEPS}
  This ensures structural (AST-level) search is available before falling back to text search."
        fi

        # Block Read on source code files — Serena.getSymbolsOverview must come first
        if [[ "$TOOL_NAME" == "Read" && -n "$FILE_PATH" ]]; then
            _SRC_EXT="go|ts|tsx|js|jsx|py|rs|java|kt|cs|cpp|c|h"
            _EXT="${FILE_PATH##*.}"
            _EXT="${_EXT,,}"
            if [[ "$_EXT" =~ ^($_SRC_EXT)$ ]]; then
                _deny "BLOCKED: Reading source file '$FILE_PATH' before Serena init.
  Complete session init first:
${_INIT_STEPS}
  Then use Serena.getSymbolsOverview to explore structure instead of reading the whole file."
            fi
        fi

        # Block Bash before init — Claude must not bypass init via shell commands.
        # The init sequence uses only MCP tools (mcp__pctx__list_functions,
        # mcp__pctx__execute_typescript) and the Write tool — no Bash needed.
        if [[ "$TOOL_NAME" == "Bash" ]]; then
            _deny "BLOCKED: Bash not available before session init.
  Complete the session init sequence first:
${_INIT_STEPS}
  Session init uses only MCP tools — no Bash required."
        fi
    fi
fi

# ============================================================
# SECTION 0B: Context-loaded gate (ctxIntent requirement)
# Blocks Grep unless LeanCtx.ctxIntent or ctxBatchExecute was called.
# These tools load live project context — always current, not manually curated.
# ============================================================
if [[ -n "$SESSION_ID" ]]; then
    _CTX_FLAG="/tmp/.claude-ctx-loaded-$(id -u)-${EFFECTIVE_SESSION_ID}"
    if [[ "$TOOL_NAME" == "Grep" && ! -f "$_CTX_FLAG" ]]; then
        _deny "BLOCKED: Context not yet loaded in this session.
  Before using Grep, load project context with:
    LeanCtx.ctxIntent({ query: '<your task description>' })
  Batch it in: mcp__pctx__execute_typescript
  This indexes live project context — derived from current codebase, not manually curated."
    fi
fi

# ============================================================
# SECTION 1B: Serena/pctx batching threshold gate
# Blocks excessive sequential calls to Serena/pctx tools without execute_typescript batching.
# ============================================================
if [[ "$TOOL_NAME" == mcp__serena__* ]] || [[ "$TOOL_NAME" == mcp__pctx__* ]]; then
    if [[ "$TOOL_NAME" != "mcp__pctx__execute_typescript" ]]; then
        # Direct Serena/pctx call (not batched) — check counter
        _COUNTER_FILE="/tmp/.claude-serena-calls-$(id -u)-${EFFECTIVE_SESSION_ID}"
        if [[ -f "$_COUNTER_FILE" ]]; then
            _COUNT=$(wc -l < "$_COUNTER_FILE" 2>/dev/null || echo 0)
            if [[ "$_COUNT" -ge 4 ]]; then
                _deny "BLOCKED: $_COUNT sequential Serena/pctx calls without batching.
  Use: mcp__pctx__execute_typescript with Promise.all() to batch multiple calls."
            fi
        fi
    fi
fi

# ============================================================
# SECTION 1: Read guards
# ============================================================
if [[ "$TOOL_NAME" == "Read" && -n "$FILE_PATH" ]]; then
    # 1-pre. Declarative read-guard.* rules from hook-config.yaml (node_modules, etc.)
    check_read_path_rules "$FILE_PATH"

    # 1a. Lock files — never read directly (backup for deny list)
    case "${FILE_PATH##*/}" in
        package-lock.json|yarn.lock|Cargo.lock|pnpm-lock.yaml|composer.lock|Gemfile.lock)
            _deny "BLOCKED: Reading ${FILE_PATH##*/} directly wastes tokens. Use Grep to search for specific entries instead." ;;
    esac

    # 1a-extra. Generated/bulk files by pattern — repomix outputs, go.sum, lock files
    _fname="${FILE_PATH##*/}"
    if [[ "$_fname" == *_repomix_* || "$FILE_PATH" == *.sum || "$FILE_PATH" == *-lock.* ]]; then
        _deny "BLOCKED: ${_fname} is a generated/lock file — no direct-read value. Use ctxSmartRead or Grep to search specific entries."
    fi

    # 1b. Large files without limit — tiered by size
    if [[ -f "$FILE_PATH" && -z "$LIMIT" ]]; then
        FILE_SIZE=$(stat -f%z "$FILE_PATH" 2>/dev/null || stat -c%s "$FILE_PATH" 2>/dev/null || echo 0)
        if [[ "$FILE_SIZE" -gt 512000 ]]; then
            _deny "BLOCKED: $FILE_PATH is $(( FILE_SIZE / 1024 ))KB — use LeanCtx.ctxSmartRead(\"$FILE_PATH\") for analysis-only reads."
        elif [[ "$FILE_SIZE" -gt 102400 ]]; then
            _deny "BLOCKED: $FILE_PATH is $(( FILE_SIZE / 1024 ))KB. Use Read with limit/offset or Grep to read only the relevant section."
        fi
    fi

    # 1c. .go files without limit — use Serena
    if [[ "$FILE_PATH" == *.go && -z "$LIMIT" ]]; then
        _deny "BLOCKED: Reading entire .go file '$FILE_PATH' without limit/offset. Use Serena.getSymbolsOverview to understand structure, then Read with limit/offset for the specific symbol.
  Call via: mcp__pctx__execute_typescript with: await Serena.getSymbolsOverview('${FILE_PATH}')"
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
                _deny "BLOCKED: Reading entire source file '$FILE_PATH' without limit/offset. Use Serena.getSymbolsOverview to understand structure, then LeanCtx.ctxRead or Read with limit/offset for specific symbols.
  Call via: mcp__pctx__execute_typescript with: await Serena.getSymbolsOverview('${FILE_PATH}')"
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
    # ------------------------------------------------------------
    # 2h-2j: folded standalone Bash-matched PreToolUse hooks (H2, 2026-07-08)
    # Replaces: pr-title-conventional-guard.sh, git-commit-guard.sh,
    #           pre-push-remote-check.sh
    #
    # Placement note: these run FIRST in Section 2, before 2-pre/2a-2g,
    # intentionally. Any later check that calls the real _deny() (JSON
    # permissionDecision:deny) does an unconditional `exit 0` on this whole
    # process — that would silently skip everything below it, including
    # these fold-ins, for the same command. Confirmed by testing: Section 2d's
    # "hyper-atomic hooks installed" check already does this for every
    # `git commit*` command in this repo. Running 2h-2j first guarantees they
    # always get to execute and produce their own diagnostics, matching their
    # pre-fold-in behavior as independent hook processes that always ran
    # regardless of what gate-v2 (or any other hook) decided.
    #
    # Each block is wrapped in its own `( ... ) || true` subshell. This is
    # load-bearing, not stylistic:
    #   1. pr-title-conventional-guard.sh and git-commit-guard.sh both used a
    #      plain `exit 1` on failure. Per this file's own "Blocking semantics"
    #      header comment, exit 1 is NON-BLOCKING (the tool still runs) — but
    #      it terminates whatever process runs it. Unwrapped, that `exit 1`
    #      would kill this entire consolidated script, silently skipping every
    #      check after it for the SAME command — concretely, `gh pr create` is
    #      matched by BOTH pr-title-conventional-guard.sh AND
    #      pre-push-remote-check.sh today as two independent standalone
    #      processes, and both run. Subshell wrapping preserves that
    #      "both checks always run" property inside one process.
    #   2. This intentionally preserves the pre-fold-in non-blocking `exit 1`
    #      behavior verbatim — no upgrade to `_deny` was made here, since that
    #      would change *what gets blocked*, out of scope for H2.
    #   3. Known cosmetic side effect: standalone hooks exiting 1 previously
    #      surfaced Claude Code's red "PreToolUse hook error — non-blocking
    #      status code" UI banner; swallowed via `|| true`, that banner no
    #      longer appears. The BLOCKED/ADVISORY text itself still reaches
    #      stderr unchanged either way — presentation-only, not a gating diff.
    # ------------------------------------------------------------

    # 2h. PR title conventional-commit guard (folded from pr-title-conventional-guard.sh)
    if [[ "$CMD" =~ ^[[:space:]]*gh[[:space:]]+pr[[:space:]]+(create|edit)([[:space:]]|$) ]]; then
        ( _PR_ACTION="${BASH_REMATCH[1]}"
          _PR_TITLE=""
          if [[ "$CMD" =~ (--title|-t)[[:space:]]+\"([^\"]+)\" ]]; then
              _PR_TITLE="${BASH_REMATCH[2]}"
          elif [[ "$CMD" =~ (--title|-t)[[:space:]]+\'([^\']+)\' ]]; then
              _PR_TITLE="${BASH_REMATCH[2]}"
          elif [[ "$CMD" =~ (--title|-t)[[:space:]]+([^[:space:]]+) ]]; then
              _PR_TITLE="${BASH_REMATCH[2]}"
          fi

          if [[ "$_PR_ACTION" == "create" && -z "$_PR_TITLE" ]]; then
              echo "BLOCKED: gh pr create requires --title in Conventional Commits format." >&2
              echo "Use: gh pr create --title \"feat: <summary>\" ..." >&2
              echo "Or use: ~/.dotfiles/.claude/scripts/stack pr <branch> <target> \"feat: <summary>\"" >&2
              exit 1
          fi

          if [[ -n "$_PR_TITLE" ]]; then
              _PR_VALIDATOR="$HOME/.dotfiles/.claude/scripts/pr-stack/lib/pr-title.sh"
              if [[ -f "$_PR_VALIDATOR" ]]; then
                  # shellcheck disable=SC1090
                  source "$_PR_VALIDATOR"
                  if ! is_conventional_pr_title "$_PR_TITLE"; then
                      echo "BLOCKED: PR title is not Conventional Commits compliant: \"$_PR_TITLE\"" >&2
                      echo "Expected: <type>(optional-scope): <summary>" >&2
                      echo "Allowed types: feat, fix, perf, refactor, test, ci, chore, docs, style, revert" >&2
                      exit 1
                  fi
              fi
          fi
          exit 0
        ) || true
    fi

    # 2i. git commit message + squash-merge guard (folded from git-commit-guard.sh)
    # Folded as one atomic subshell to preserve the original script's
    # `commit_msg` variable dependency between Policy A and Policy A2.
    (
        _extract_commit_message() {
            local cmd="$1"
            local delim
            delim=$(printf '%s\n' "$cmd" | grep -oE "<<-?[\"']?[A-Za-z_][A-Za-z0-9_]*[\"']?" | head -1 | sed -E "s/^<<-?[\"']?//; s/[\"']?\$//")
            if [[ -n "$delim" ]]; then
                printf '%s\n' "$cmd" | awk -v delim="$delim" '
                    found && $0 == delim { exit }
                    found { print; next }
                    index($0, "<<") > 0 && index($0, delim) > 0 { found=1 }
                '
                return 0
            fi
            printf '%s\n' "$cmd" | sed -n 's/.*-m[[:space:]]*"\([^"]*\)".*/\1/p'
        }

        # POLICY A: Conventional Commits format on git commit -m
        if echo "$CMD" | grep -qE 'git commit.*-m'; then
            commit_msg=$(_extract_commit_message "$CMD")

            if [[ -n "$commit_msg" ]]; then
                subject=$(echo "$commit_msg" | head -1)

                # Skip auto-generated merge/revert commits
                if echo "$subject" | grep -qE '^(Merge|Revert) '; then
                    exit 0
                fi

                # Use shared pr-title.sh lib (canonical types); extend with wip/build for commits.
                _CG_VALIDATOR="$HOME/.dotfiles/.claude/scripts/pr-stack/lib/pr-title.sh"
                valid=false
                if [[ -f "$_CG_VALIDATOR" ]]; then
                    # shellcheck disable=SC1090
                    source "$_CG_VALIDATOR"
                    is_conventional_pr_title "$subject" && valid=true
                    # wip and build are valid commit types but not PR title types
                    echo "$subject" | grep -qE '^(wip|build)(\([a-z0-9._/-]+\))?(!)?:[[:space:]].+$' && valid=true
                else
                    echo "$subject" | grep -qE \
                        '^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert|wip)(\([a-z0-9._/-]+\))?(!)?:[[:space:]].+$' \
                        && valid=true
                fi

                if [[ "$valid" != "true" ]]; then
                    echo "BLOCKED: Commit message does not follow Conventional Commits format." >&2
                    echo "" >&2
                    echo "  Your message: $subject" >&2
                    echo "  Expected:     <type>(<optional-scope>): <summary>" >&2
                    echo "" >&2
                    echo "  Allowed types: feat, fix, docs, style, refactor, test, chore, perf, ci, build, revert, wip" >&2
                    echo "" >&2
                    echo "  Examples:" >&2
                    echo "    feat(auth): add JWT refresh token support" >&2
                    echo "    fix(worker): resolve bulk insert timeout" >&2
                    echo "    wip(migration): experimenting with sequence algorithm" >&2
                    exit 1
                fi

                # Co-authored-by advisory for AI commits (warning only, non-blocking)
                if ! echo "$commit_msg" | grep -q "Co-authored-by:"; then
                    echo "[ADVISORY] AI-generated commits should include:" >&2
                    echo "  Co-authored-by: Claude Sonnet 4.6 <noreply@anthropic.com>" >&2
                fi
            fi
        fi

        # =============================================================
        # POLICY A1: commitlint header-max-length + subject-case
        # Conventional Commits format alone (POLICY A) does not catch these
        # two active commitlint rules — a subject can match the regex above
        # while still failing CI's `npx commitlint` on header length or case.
        # =============================================================
        if [[ -n "${subject:-}" ]]; then
            header_len=${#subject}
            if [[ $header_len -gt 100 ]]; then
                echo "BLOCKED: Commit header exceeds commitlint's header-max-length (100 chars)." >&2
                echo "  Header ($header_len chars): $subject" >&2
                exit 1
            fi

            # subject-case: lowerCase — text after "type(scope): " must not
            # contain uppercase (e.g. a capitalized filename like GRAPH_REPORT.md
            # breaks this even though it matches Conventional Commits format).
            subject_text=$(echo "$subject" | sed -E 's/^[a-z]+(\([a-z0-9._/-]+\))?!?:[[:space:]]*//')
            if [[ "$subject_text" =~ [A-Z] ]]; then
                echo "BLOCKED: Commit subject must be lowerCase per commitlint's subject-case rule." >&2
                echo "  Subject: $subject_text" >&2
                echo "  Rewrite without uppercase (spell out filenames/acronyms in lowercase prose)." >&2
                exit 1
            fi
        fi

        # POLICY A2: commitlint body-max-line-length (default rule: 100 chars)
        if [[ -n "${commit_msg:-}" ]]; then
            body_violations=""
            line_no=0
            while IFS= read -r line; do
                line_no=$((line_no + 1))
                # skip subject line and blank lines
                [[ $line_no -eq 1 || -z "$line" ]] && continue
                # skip trailer/footer lines
                echo "$line" | grep -qiE '^(co-authored-by|signed-off-by|reviewed-by|fixes|closes|refs):' && continue
                line_len=${#line}
                if [[ $line_len -gt 100 ]]; then
                    body_violations+="  Line $line_no ($line_len chars): ${line:0:70}...
"
                fi
            done <<< "$commit_msg"

            if [[ -n "$body_violations" ]]; then
                echo "BLOCKED: Commit message body exceeds commitlint's body-max-line-length (100 chars)." >&2
                echo "" >&2
                printf '%s' "$body_violations" >&2
                echo "" >&2
                echo "  Wrap body lines at ~100 chars. Trailer lines (Co-authored-by, Signed-off-by, etc.) are exempt." >&2
                exit 1
            fi
        fi

        # POLICY B: Squash merge advisory for large PRs
        if echo "$CMD" | grep -qE '(gh pr merge.*--squash|az repos pr update.*--squash)'; then
            pr_number=$(echo "$CMD" | grep -oE '(merge|update) [0-9]+' | grep -oE '[0-9]+$' | head -1)

            if [[ -n "$pr_number" ]] && command -v gh &>/dev/null; then
                files_changed=$(gh pr view "$pr_number" --json files --jq '.files | length' 2>/dev/null || echo "")

                if [[ -n "$files_changed" && "$files_changed" -gt 5 ]]; then
                    echo "[ADVISORY] Squash merging PR #$pr_number with $files_changed files changed." >&2
                    echo "  Consider regular merge to preserve commit history for git bisect:" >&2
                    echo "    gh pr merge $pr_number --merge" >&2
                fi
            fi
        fi
        exit 0
    ) || true

    # 2j. Pre-push remote/auth advisory (folded from pre-push-remote-check.sh)
    # Pure advisory (always exit 0 upstream) — still subshell-wrapped for
    # defensive isolation, so an unexpected git/gh failure here (this file's
    # own ERR trap only logs, it does not `exit 0` like the standalone hook's
    # trap did) cannot abort the rest of Section 2 under `set -e`.
    ( if echo "$CMD" | grep -qE '(git push|gh pr create|gh pr edit|az repos pr)'; then
          _PP_REMOTE_INFO=$(git remote -v 2>/dev/null | awk '/^origin.*\(fetch\)/{print $2}' | sed -n '1p' || echo "unknown")
          _PP_GH_USER=$(gh auth status --active 2>&1 | awk '/Logged in to/{print $(NF-1)}' | tr -d '"()' | sed -n '1p' || echo "unknown")

          _PP_REMOTE_HOST="unknown"
          _PP_REMOTE_REPO="unknown"
          if [[ "$_PP_REMOTE_INFO" =~ github\.com[:/](.+)\.git$ ]] || [[ "$_PP_REMOTE_INFO" =~ github\.com[:/](.+)$ ]]; then
              _PP_REMOTE_HOST="github.com"
              _PP_REMOTE_REPO="${BASH_REMATCH[1]}"
          elif [[ "$_PP_REMOTE_INFO" =~ dev\.azure\.com/([^/]+)/([^/]+)/_git/(.+) ]]; then
              _PP_REMOTE_HOST="dev.azure.com/${BASH_REMATCH[1]}"
              _PP_REMOTE_REPO="${BASH_REMATCH[2]}/${BASH_REMATCH[3]}"
          elif [[ "$_PP_REMOTE_INFO" =~ visualstudio\.com/([^/]+)/_git/(.+) ]]; then
              _PP_REMOTE_HOST="visualstudio.com"
              _PP_REMOTE_REPO="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
          else
              _PP_REMOTE_HOST="$_PP_REMOTE_INFO"
          fi

          _PP_CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")

          echo "Remote: origin → ${_PP_REMOTE_HOST}/${_PP_REMOTE_REPO} | branch: ${_PP_CURRENT_BRANCH} | gh: ${_PP_GH_USER}" >&2

          if [[ "$_PP_REMOTE_HOST" == "github.com" && "$_PP_GH_USER" != "arjaygg" && "$_PP_GH_USER" != "unknown" ]]; then
              echo "WARNING: gh CLI authenticated as '${_PP_GH_USER}' — expected 'arjaygg' for GitHub personal repos." >&2
              echo "  Run: gh auth switch --user arjaygg" >&2
          fi

          if [[ "$_PP_REMOTE_HOST" == dev.azure.com* || "$_PP_REMOTE_HOST" == visualstudio.com* ]]; then
              if echo "$CMD" | grep -q 'gh pr'; then
                  echo "WARNING: 'gh pr' targets GitHub but remote is ADO (${_PP_REMOTE_HOST})." >&2
                  echo "  Use: az repos pr create --organization https://bofaz.visualstudio.com" >&2
              fi
          fi
      fi
    ) || true

    # 2-pre. Declarative rule.* rules from hook-config.yaml (sed -i, awk>file,
    # echo/printf redirects, piped tee — real gaps not caught by 2a-2g below)
    check_bash_cmd_rules "$CMD"

    # 2a. grep (but not git grep) — no Grep tool exists in this session; use LeanCtx.ctxSearch
    if [[ ( "$CMD" == grep\ * || "$CMD" == grep\ -* ) && "$CMD" != *"git grep"* ]]; then
        _deny "BLOCKED: Use LeanCtx.ctxSearch instead of 'grep' (no Grep tool exists in this session).
  Call via: mcp__pctx__execute_typescript with: await LeanCtx.ctxSearch({ query: '<pattern>' })
  Requires session init to have run first (Serena.initialInstructions / pctx list_functions) or the call itself may be blocked."
    fi

    # 2b. find → no Glob tool exists in this session; use Serena.findFile
    if [[ "$CMD" == find\ * ]]; then
        _deny "BLOCKED: Use Serena.findFile instead of 'find' (no Glob tool exists in this session).
  Call via: mcp__pctx__execute_typescript with: await Serena.findFile('<filename>')
  Requires session init to have run first (Serena.initialInstructions / pctx list_functions) or the call itself may be blocked."
    fi

    # 2c. plain ls (not ls -l* for symlink inspection) — no Glob tool exists in this session; use Serena.listDir
    if [[ ( "$CMD" == ls\ * || "$CMD" == "ls" ) && "$CMD" != ls\ -l* ]]; then
        _deny "BLOCKED: Use Serena.listDir instead of 'ls' (no Glob tool exists in this session).
  Call via: mcp__pctx__execute_typescript with: await Serena.listDir('<path>')
  Requires session init to have run first (Serena.initialInstructions / pctx list_functions) or the call itself may be blocked."
    fi

    # 2d. git commit on main/master
    if [[ "$CMD" == git\ commit* ]]; then
        CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
        if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" ]]; then
            _deny "BLOCKED: You are about to commit directly to '$CURRENT_BRANCH'. Create a feature branch first: stack create <name> $CURRENT_BRANCH"
        fi
        # Block raw git commit when hyper-atomic hooks are installed
        _ATOMIC_HOOKS=$(git config --local core.hooksPath 2>/dev/null || echo "")
        if [[ "$_ATOMIC_HOOKS" == "$HOME/.dotfiles/git/hooks" ]]; then
            _deny "BLOCKED: Use '~/.dotfiles/scripts/ai/commit.sh -m \"subject\" -m \"why\"' instead of raw git commit."
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
            echo "[MONITOR HINT] This command looks like a poll loop. If the goal is event-watching (notify when condition changes), the Monitor tool is more efficient — zero tokens when silent, vs this loop which costs tokens on every iteration. See ai/rules/monitor-patterns.md." >&2
        fi
    # 2f-chained. Same poll-loop signal, but chained via ';'/'&&' instead of a while-loop
    elif echo "$CMD" | grep -qE '(gh (run|pr|workflow)|kubectl|tail -f|curl.*http|argocd)' && \
         echo "$CMD" | grep -qE '(;|&&) *sleep [0-9]'; then
        echo "[MONITOR HINT] This command looks like a poll loop (chained sleep outside a while-loop). If the goal is event-watching (notify when condition changes), the Monitor tool is more efficient — zero tokens when silent, vs repeated invocations which cost tokens every time. See ai/rules/monitor-patterns.md." >&2
    fi

    # 2f-standalone. Standalone head/tail/cat — use Read tool instead (mirrors deny-list entries being removed)
    _FIRST_CMD=$(echo "$CMD" | awk '{print $1}')
    if [[ "$_FIRST_CMD" == "head" || "$_FIRST_CMD" == "tail" || "$_FIRST_CMD" == "cat" ]]; then
        _deny "BLOCKED: Use the Read tool with a limit/offset parameter instead of '$_FIRST_CMD'."
    fi

    # 2g. Piped text processors — catch 'cmd | head', 'cmd | grep', etc. (deny list only catches prefixes)
    if echo "$CMD" | grep -qE '\| *(head|tail|cat|sed|awk|grep|rg)( |$)'; then
        PIPE_CMD=$(echo "$CMD" | grep -oE '\| *(head|tail|cat|sed|awk|grep|rg)' | head -1 | tr -d '| ')
        # For | head / | tail on safe CLI commands — rewrite by stripping the pipe (exit 0 + JSON = Claude Code rewrite)
        if [[ "$PIPE_CMD" == "head" || "$PIPE_CMD" == "tail" ]]; then
            _BASE_CMD=$(echo "$CMD" | sed 's/ *|.*//')
            _FIRST_WORD=$(echo "$_BASE_CMD" | awk '{print $1}')
            if echo "$_FIRST_WORD" | grep -qE '^(gh|kubectl|git|argocd|az|docker|helm|aws|rtk|jq|curl)$'; then
                echo "$INPUT" | jq --arg cmd "$_BASE_CMD" '.tool_input.command = $cmd'
                echo "REWRITE: Stripped '| $PIPE_CMD' — running: $_BASE_CMD" >&2
                exit 0
            fi
        fi
        _deny "BLOCKED: Piped '$PIPE_CMD' is not allowed after a command.
  Use the Read tool with a limit parameter, jq for JSON output, or LeanCtx.ctxSearch for text search.
  Call via: mcp__pctx__execute_typescript with: await LeanCtx.ctxSearch({ query: '<pattern>' })"
    fi
fi

# ============================================================
# SECTION 3: Edit guards
# ============================================================
# 3a. Edit/MultiEdit (always) or Write to existing files — require prior Read in this session.
# Write to a *new* file is allowed. The standalone read-before-write-guard.sh has been
# removed (ADL-013 fix): it blocked blindly with exit 2 and no read-log check.
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "MultiEdit" ]] || \
   [[ "$TOOL_NAME" == "Write" && -n "$FILE_PATH" && -f "$FILE_PATH" ]]; then
    if [[ -n "$FILE_PATH" ]]; then
        READ_LOG="/tmp/.claude-read-log-$(id -u)"
        if [[ ! -f "$READ_LOG" ]] || ! grep -qF "$FILE_PATH" "$READ_LOG" 2>/dev/null; then
            if [[ "$TOOL_NAME" == "Write" ]]; then
                _deny "BLOCKED: Overwriting existing '$FILE_PATH' without reading it first. Read it first to avoid data loss."
            else
                _deny "BLOCKED: Editing '$FILE_PATH' without reading it first. Use Read (or Serena.getSymbolsOverview) to understand the file before editing."
            fi
        fi
    fi
fi

# 3b. Edit/Write/MultiEdit on main/master branch — hard block (stacking enforcement)
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "MultiEdit" ]]; then
    if [[ -n "$FILE_PATH" ]]; then
        _EDIT_BRANCH=$(_branch_for_path "$FILE_PATH")
        if [[ "$_EDIT_BRANCH" == "main" || "$_EDIT_BRANCH" == "master" ]]; then
            # Exempt: plans/ files (session bookkeeping, always on current branch)
            #         .trees/ paths (already in a worktree)
            #         .claude/projects/*/memory/ (auto-memory storage) — $HOME can
            #         itself be a git repo on main for unrelated project work; that
            #         must never gate Claude's own memory writes.
            if [[ ! "$FILE_PATH" =~ (^|/)(plans|\.trees)/ ]] && \
               [[ ! "$FILE_PATH" =~ /\.claude/projects/[^/]+/memory/ ]]; then
                _SUGGESTED_BRANCH=""
                _HINT_FILE="/tmp/.claude-stack-hint-$(id -u)-${EFFECTIVE_SESSION_ID}"
                [[ -f "$_HINT_FILE" ]] && _SUGGESTED_BRANCH=$(cat "$_HINT_FILE" 2>/dev/null)
                _REASON="BLOCKED: Editing '$FILE_PATH' on '$_EDIT_BRANCH'. Create a stacked branch first:"
                if [[ -n "$_SUGGESTED_BRANCH" ]]; then
                    _REASON+=$'\n'"  stack create feature/$_SUGGESTED_BRANCH $_EDIT_BRANCH"
                else
                    _REASON+=$'\n'"  stack create feature/<name> $_EDIT_BRANCH"
                fi
                _REASON+=$'\n'"  This creates a worktree at .trees/<name>/ — edit there instead."
                _deny "$_REASON"
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
                _DIAG=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" --verbose 2>&1 1>/dev/null || true)
                _REASON="BLOCKED: Mixed concerns detected in staged files (state: blocked)."
                [[ -n "$_DIAG" ]] && _REASON+=$'\n'"  ${_DIAG//$'\n'/$'\n'  }"
                _REASON+=$'\n'"  Commit or checkpoint current work before editing more files."
                _deny "$_REASON"
                ;;
            overgrown)
                _DIAG=$("$HOME/.dotfiles/scripts/ai/atomic-status.sh" --verbose 2>&1 1>/dev/null || true)
                _REASON="BLOCKED: Working tree is overgrown (state: overgrown)."
                [[ -n "$_DIAG" ]] && _REASON+=$'\n'"  ${_DIAG//$'\n'/$'\n'  }"
                _REASON+=$'\n'"  Consider committing a subset before continuing."
                _REASON+=$'\n'"  Run: ~/.dotfiles/scripts/ai/commit.sh -m 'subject' -m 'why'"
                _deny "$_REASON"
                ;;
            ready_to_commit)
                _deny "BLOCKED: Changes are ready to commit (state: ready_to_commit).
  Run: ~/.dotfiles/scripts/ai/commit.sh -m 'subject' -m 'why'"
                ;;
        esac
    fi

    # 4b. Plan scope gate
    if [[ -n "$FILE_PATH" && -f "plans/plan-state.json" ]]; then
        EXPECTED=$(jq -r '.expected_files[]' plans/plan-state.json 2>/dev/null || true)
        if [[ -n "$EXPECTED" ]]; then
            STEP=$(jq -r '.step_title // "unknown step"' plans/plan-state.json 2>/dev/null || echo "unknown step")
            if ! echo "$EXPECTED" | grep -qF "$FILE_PATH"; then
                _deny "BLOCKED: '$FILE_PATH' is not in scope for current step: '$STEP'
Expected files: $(echo "$EXPECTED" | tr '\n' ' ')
To add a file to scope: update plans/plan-state.json expected_files[]"
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
            active-context*|decisions*|progress*|plan-state*|pctx-functions*|hook-learning*|plan.md) ;;
            *)
                # Check naming convention: YYYY-MM-DD-context.md
                if [[ ! "$FILENAME" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}-.+\.md$ ]]; then
                    TODAY=$(date '+%Y-%m-%d')
                    _deny "BLOCKED: Plan file '$FILENAME' doesn't follow naming convention.
Expected format: YYYY-MM-DD-context.md (e.g., ${TODAY}-your-task-description.md)"
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
    # 6a. Grep — prefer LeanCtx.ctxSearch or Serena.
    # Post-init unlock: once LeanCtx.ctxIntent has run this session (ctx flag
    # exists), Grep is the sanctioned native fallback — downgrade to hint.
    # Without this, Section 2a says "use the Grep tool" while this section
    # denies it, and the model ping-pongs between Bash grep and Grep forever.
    if [[ "$TOOL_NAME" == "Grep" && -n "$PATTERN" ]]; then
        if [[ -f "/tmp/.claude-ctx-loaded-$(id -u)-${EFFECTIVE_SESSION_ID}" ]]; then
            _SERENA_LEVEL="warn"
        fi
        _SERENA_PREFIX="HINT"
        [[ "$_SERENA_LEVEL" == "block" ]] && _SERENA_PREFIX="BLOCKED"

        if [[ "$PATTERN" =~ ^(func|class|type|struct|interface|def|fn)[[:space:]] ]]; then
            _MSG="$_SERENA_PREFIX: For symbol lookups, use Serena.findSymbol (structural) or LeanCtx.ctxSearch (token-efficient) instead of Grep.
  Call via: mcp__pctx__execute_typescript with: await Serena.findSymbol({ name: '<symbol>' })"
            [[ "$_SERENA_LEVEL" == "block" ]] && _deny "$_MSG"
            echo "$_MSG" >&2
            exit 0
        fi
        if [[ "$PATTERN" =~ ^[A-Z][a-zA-Z0-9]+$ ]]; then
            _MSG="$_SERENA_PREFIX: '$PATTERN' looks like a symbol name. Use Serena.findSymbol('$PATTERN') for structural results, or LeanCtx.ctxSearch for pattern matching.
  Call via: mcp__pctx__execute_typescript with: await Serena.findSymbol({ name: '${PATTERN}' })"
            [[ "$_SERENA_LEVEL" == "block" ]] && _deny "$_MSG"
            echo "$_MSG" >&2
            exit 0
        fi
        # General pattern — LeanCtx.ctxSearch is a direct drop-in
        _MSG="$_SERENA_PREFIX: Use LeanCtx.ctxSearch instead of Grep — it's gitignore-aware, session-cached, and token-efficient.
  Call via: mcp__pctx__execute_typescript with: await LeanCtx.ctxSearch({ query: '${PATTERN}' })"
        [[ "$_SERENA_LEVEL" == "block" ]] && _deny "$_MSG"
        echo "$_MSG" >&2
        exit 0
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

exit 0
