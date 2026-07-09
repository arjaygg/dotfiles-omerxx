#!/usr/bin/env bash
# UserPromptSubmit hook: warn Claude when session artifact files are missing or stale
# Silent when healthy; outputs a structured warning (becomes system-reminder) when action needed

set -euo pipefail
trap 'echo "HOOK CRASH (plans-healthcheck.sh line $LINENO): $BASH_COMMAND"; exit 0' ERR

# CRITICAL: Drain stdin — all UserPromptSubmit hooks must consume stdin to prevent buffering issues
# (N1b) Capture instead of discarding so session_id can key per-session dedup flags.
HOOK_PAYLOAD=$(cat || true)
SESSION_ID=$(echo "$HOOK_PAYLOAD" | python3 -c "
import sys, json
try:
    print(json.load(sys.stdin).get('session_id', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

# UserPromptSubmit expects JSON output when emitting context.
# Capture plain-text advisory output from this script and wrap it as hookSpecificOutput.
TMP_OUT="$(mktemp "/tmp/plans-healthcheck.XXXXXX")"
exec 3>&1
exec >"$TMP_OUT"

flush_userprompt_json() {
    local status=$?
    if [[ -s "$TMP_OUT" ]]; then
        python3 - "$TMP_OUT" >&3 <<'PYEOF'
import json, sys
path = sys.argv[1]
with open(path, encoding="utf-8", errors="replace") as f:
    msg = f.read().strip()
if msg:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": msg
        }
    }))
PYEOF
    fi
    rm -f "$TMP_OUT"
    exit "$status"
}
trap flush_userprompt_json EXIT

CWD=$(pwd)
TODAY=$(date '+%Y-%m-%d')

# Environment checks below (setup/pctx/hooks/stack) describe machine/repo state
# that rarely changes mid-session — surface once per session instead of on
# every prompt. Session id comes from stdin JSON already drained above, so
# re-read it isn't available here; fall back to a per-UID, per-day flag.
_ENV_NOTIFY_FLAG="/tmp/.claude-plans-healthcheck-env-$(id -u)-${TODAY}"
_SKIP_ENV_CHECKS=0
[[ -f "$_ENV_NOTIFY_FLAG" ]] && _SKIP_ENV_CHECKS=1

# Binary dependency checks (global) — cached in /tmp for 1 hour to avoid per-prompt overhead
CACHE_FILE="/tmp/.claude-binary-check-$(id -u)"
NOW=$(date '+%s')
CACHE_TTL=3600

MISSING_BINARIES=()
CACHE_AGE=0

# Binaries that can be auto-installed in the background
# format: "binary:install-command"
declare -A BINARY_AUTO_INSTALL=(
    ["qmd"]="npm install -g @tobilu/qmd"
    ["rtk"]="brew install rtk"
)
REQUIRED_BINARIES=("qmd" "rtk")

# Use cache if fresh enough
if [[ -f "$CACHE_FILE" ]]; then
    CACHE_AGE=$(( NOW - $(date -r "$CACHE_FILE" '+%s' 2>/dev/null || echo 0) ))
    if [[ $CACHE_AGE -lt $CACHE_TTL ]]; then
        # Read cached missing list; skip re-check
        CACHED=$(cat "$CACHE_FILE")
        [[ -n "$CACHED" ]] && read -ra MISSING_BINARIES <<< "$CACHED"
    fi
fi

# Cache miss or expired — run checks and (opt-in only) trigger background installs
# M5 (2026-07-08): auto-install was previously opt-OUT (ran by default unless
# CLAUDE_HOOKS_DISABLE_AUTO_INSTALL=1 was set) — silently running `npm install -g`/
# `brew install` on every cache-miss prompt without explicit consent. Now opt-IN:
# nothing installs unless DOTFILES_AUTO_INSTALL=1 is explicitly set.
_AUTO_INSTALL_ENABLED=0
[[ "${DOTFILES_AUTO_INSTALL:-0}" == "1" ]] && _AUTO_INSTALL_ENABLED=1

if [[ ! -f "$CACHE_FILE" ]] || [[ $CACHE_AGE -ge $CACHE_TTL ]]; then
    for bin in "${REQUIRED_BINARIES[@]}"; do
        if ! command -v "$bin" &> /dev/null; then
            MISSING_BINARIES+=("$bin")
            # Trigger silent background install only when explicitly opted in
            install_cmd="${BINARY_AUTO_INSTALL[$bin]:-}"
            if [[ -n "$install_cmd" ]] && [[ "$_AUTO_INSTALL_ENABLED" -eq 1 ]]; then
                (eval "$install_cmd" &>/dev/null) &
            fi
        fi
    done
    # Write result to cache (space-separated missing names, or empty)
    echo "${MISSING_BINARIES[*]:-}" > "$CACHE_FILE"
fi

if [[ ${#MISSING_BINARIES[@]} -gt 0 && "$_SKIP_ENV_CHECKS" -eq 0 ]]; then
    echo "hook: setup-health"
    if [[ "$_AUTO_INSTALL_ENABLED" -eq 1 ]]; then
        echo "status: installing in background"
    else
        echo "status: missing (auto-install disabled — set DOTFILES_AUTO_INSTALL=1 to enable)"
    fi
    for m in "${MISSING_BINARIES[@]}"; do
        case "$m" in
            qmd) echo "  - qmd (semantic search sync): npm install -g @tobilu/qmd" ;;
            rtk) echo "  - rtk (token optimizer): brew install rtk" ;;
            *)   echo "  - $m: no auto-install command, install manually" ;;
        esac
    done
    echo ""
fi

PCTX_WARNINGS=()
if ! command -v "pctx" &> /dev/null; then
    PCTX_WARNINGS+=("pctx binary not found in PATH (npm i -g @portofcontext/pctx)")
fi
if [[ ! -r "$HOME/.config/pctx/pctx.json" ]]; then
    PCTX_WARNINGS+=("~/.config/pctx/pctx.json is missing or unreadable")
else
    # Use python3 for proper JSON lookup (avoids false positives from substring grep matches)
    # pctx.json uses {"servers": [{"name": "serena"}, ...]} structure
    MISSING_SERVERS=$(python3 -c "
import json
try:
    with open('$HOME/.config/pctx/pctx.json') as f:
        d = json.load(f)
    raw = d.get('servers', [])
    # Support both list-of-objects and dict-of-objects formats
    if isinstance(raw, list):
        names = {s.get('name','') for s in raw if isinstance(s, dict)}
    else:
        names = set(raw.keys())
    required = ['serena', 'lean-ctx']
    missing = [s for s in required if s not in names]
    print('\n'.join(missing))
except Exception as e:
    print(f'parse-error: {e}')
" 2>/dev/null || echo "")
    while IFS= read -r srv; do
        [[ -n "$srv" ]] && PCTX_WARNINGS+=("Server '$srv' not found in pctx.json")
    done <<< "$MISSING_SERVERS"
fi

if [[ ${#PCTX_WARNINGS[@]} -gt 0 && "$_SKIP_ENV_CHECKS" -eq 0 ]]; then
    echo "hook: pctx-health"
    echo "status: gateway configuration issues"
    for warn in "${PCTX_WARNINGS[@]}"; do
        echo "  - $warn"
    done
    echo ""
fi

# --- Hyper-atomic commit hooks (runs unconditionally — independent of plan state) ---
if [[ "$_SKIP_ENV_CHECKS" -eq 0 ]] && git rev-parse --show-toplevel &>/dev/null 2>&1; then
    HOOKS_PATH=$(git config --local core.hooksPath 2>/dev/null || echo "")
    EXPECTED="$HOME/.dotfiles/git/hooks"
    if [[ "$HOOKS_PATH" != "$EXPECTED" ]]; then
        echo "hook: hooks-health"
        echo "status: atomic commit hooks not installed in this repo"
        echo "  suggested: /hyper-commit-setup"
        echo ""
    fi
fi

# --- Charcoal / stacking readiness (runs unconditionally) ---
if [[ "$_SKIP_ENV_CHECKS" -eq 0 ]] && git rev-parse --show-toplevel &>/dev/null 2>&1; then
    STACK_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
    GT_INIT=0
    [[ -f ".git/.graphite_repo_config" ]] && GT_INIT=1

    # (N1b) once per session per branch — re-arms on branch switch (state change)
    _STACK_FLAG="/tmp/.claude-stackhealth-$(id -u)-${SESSION_ID:-$TODAY}-${STACK_BRANCH}"
    if [[ "$STACK_BRANCH" == "main" || "$STACK_BRANCH" == "master" ]] && [[ ! -f "$_STACK_FLAG" ]]; then
        echo "hook: stack-health"
        echo "status: on '$STACK_BRANCH'"
        echo "  suggested: stack-create skill before editing files"
        echo ""
        touch "$_STACK_FLAG" 2>/dev/null || true
    fi

    if [[ "$GT_INIT" -eq 0 ]] && command -v gt &>/dev/null; then
        echo "hook: stack-health"
        echo "status: charcoal installed, 'gt repo init' not run in this repo"
        echo "  suggested: gt repo init, then stack-create skill"
        echo ""
    elif ! command -v gt &>/dev/null; then
        echo "hook: stack-health"
        echo "status: charcoal (gt) not found"
        echo "  suggested: npm install -g @withgraphite/graphite-cli, then gt repo init"
        echo ""
    fi
fi

[[ "$_SKIP_ENV_CHECKS" -eq 0 ]] && touch "$_ENV_NOTIFY_FLAG" 2>/dev/null || true

# --- Turn-30 checkpoint nudge ---
_TURN_COUNT=$(cat "/tmp/.claude-turn-count-${UID}" 2>/dev/null || echo "0")
if [[ "$_TURN_COUNT" -eq 30 ]]; then
    echo "hook: session-health"
    echo "status: turn 30 reached"
    echo "  suggested: update plans/active-context.md with current task state"
fi

# Opt-in: only run if plans/ directory exists
[[ -d "$CWD/plans" ]] || exit 0

ARTIFACT_FILES=(
    "plans/active-context.md"
    "plans/decisions.md"
    "plans/progress.md"
)

MISSING=()
STALE=()

for rel in "${ARTIFACT_FILES[@]}"; do
    fp="$CWD/$rel"
    if [[ ! -f "$fp" ]]; then
        MISSING+=("$rel")
    else
        FILE_DATE=$(date -r "$fp" '+%Y-%m-%d' 2>/dev/null || echo "")
        if [[ "$FILE_DATE" != "$TODAY" ]]; then
            STALE+=("$rel")
        fi
    fi
done

# Check if active-context.md is 3+ days old (content may describe a different task)
ACTIVE_CTX_AGE=""
ACTIVE_CTX_PATH="$CWD/plans/active-context.md"
if [[ -f "$ACTIVE_CTX_PATH" ]]; then
    MTIME=$(stat -f%m "$ACTIVE_CTX_PATH" 2>/dev/null || stat -c%Y "$ACTIVE_CTX_PATH" 2>/dev/null || echo 0)
    NOW=$(date +%s)
    AGE_DAYS=$(( (NOW - MTIME) / 86400 ))
    if [[ "$AGE_DAYS" -ge 3 ]]; then
        ACTIVE_CTX_AGE="${AGE_DAYS}"
    fi
fi

# All healthy → silent exit
if [[ ${#MISSING[@]} -eq 0 ]] && [[ ${#STALE[@]} -eq 0 ]] && [[ -z "$ACTIVE_CTX_AGE" ]]; then
    exit 0
fi

# (N1b) once per session per state — re-emits only when the warning content
# changes (file becomes stale/missing/fresh), not on every prompt
_PLANS_SIG="${MISSING[*]:-}|${STALE[*]:-}|${ACTIVE_CTX_AGE}"
_PLANS_FLAG="/tmp/.claude-planshealth-$(id -u)-${SESSION_ID:-$TODAY}"
if [[ -f "$_PLANS_FLAG" ]] && [[ "$(cat "$_PLANS_FLAG" 2>/dev/null || true)" == "$_PLANS_SIG" ]]; then
    exit 0
fi
echo "$_PLANS_SIG" > "$_PLANS_FLAG" 2>/dev/null || true

# Build and output warning
python3 - "${MISSING[*]:-}" "${STALE[*]:-}" "$ACTIVE_CTX_AGE" <<'PYEOF'
import sys

missing_str, stale_str, ctx_age = sys.argv[1], sys.argv[2], sys.argv[3]
missing = [f for f in missing_str.split() if f]
stale = [f for f in stale_str.split() if f]

lines = ["hook: plans-health", ""]

if missing:
    lines.append("missing (per CLAUDE.md, create before compaction):")
    for f in missing:
        lines.append(f"  - {f}")
    lines.append("  active-context.md — current focus/learnings, <=30 lines")
    lines.append("  decisions.md      — append-only ADL log")
    lines.append("  progress.md       — task state in checkbox format")

if stale:
    if missing:
        lines.append("")
    lines.append("stale (not updated today):")
    for f in stale:
        lines.append(f"  - {f}")

if ctx_age:
    if missing or stale:
        lines.append("")
    lines.append(f"active-context.md age: {ctx_age} days")
    lines.append("  note: content may describe a task other than the current one — worth a quick check")

print("\n".join(lines))
PYEOF

exit 0
