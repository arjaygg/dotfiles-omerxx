#!/usr/bin/env bash
# UserPromptSubmit hook: warn Claude when session artifact files are missing or stale
# Silent when healthy; outputs a structured warning (becomes system-reminder) when action needed

set -euo pipefail

CWD=$(pwd)
TODAY=$(date '+%Y-%m-%d')

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
    ["rtk"]="brew tap rtk-ai/rtk && brew install rtk"
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

# Cache miss or expired — run checks and trigger background installs
if [[ ! -f "$CACHE_FILE" ]] || [[ $CACHE_AGE -ge $CACHE_TTL ]]; then
    for bin in "${REQUIRED_BINARIES[@]}"; do
        if ! command -v "$bin" &> /dev/null; then
            MISSING_BINARIES+=("$bin")
            # Trigger silent background install if a command is defined
            install_cmd="${BINARY_AUTO_INSTALL[$bin]:-}"
            if [[ -n "$install_cmd" ]]; then
                (eval "$install_cmd" &>/dev/null) &
            fi
        fi
    done
    # Write result to cache (space-separated missing names, or empty)
    echo "${MISSING_BINARIES[*]:-}" > "$CACHE_FILE"
fi

if [[ ${#MISSING_BINARIES[@]} -gt 0 ]]; then
    echo "[SETUP HEALTH] Missing required tools (installing in background):"
    for m in "${MISSING_BINARIES[@]}"; do
        case "$m" in
            qmd) echo "  - qmd  (semantic search sync)  → auto-installing: npm install -g @tobilu/qmd" ;;
            rtk) echo "  - rtk  (Cursor shell compress) → auto-installing: brew tap rtk-ai/rtk && brew install rtk" ;;
            *)   echo "  - $m  → install manually" ;;
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
    for srv in "serena" "exa" "sequential-thinking" "notebooklm" "markitdown"; do
        if ! grep -q "\"$srv\"" "$HOME/.config/pctx/pctx.json"; then
            PCTX_WARNINGS+=("Server '$srv' not found in pctx.json")
        fi
    done
fi

if [[ ${#PCTX_WARNINGS[@]} -gt 0 ]]; then
    echo "[PCTX HEALTH] Advisory - Gateway configuration issues:"
    for warn in "${PCTX_WARNINGS[@]}"; do
        echo "  - $warn"
    done
    echo ""
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

HANDOFF_EXISTS=0
[[ -f "$CWD/plans/session-handoff.md" ]] && HANDOFF_EXISTS=1

# All healthy and no handoff → silent exit
if [[ ${#MISSING[@]} -eq 0 ]] && [[ ${#STALE[@]} -eq 0 ]] && [[ "$HANDOFF_EXISTS" -eq 0 ]]; then
    exit 0
fi

# Build and output warning
python3 - "${MISSING[*]:-}" "${STALE[*]:-}" "$HANDOFF_EXISTS" <<'PYEOF'
import sys

missing_str, stale_str, handoff_exists = sys.argv[1], sys.argv[2], sys.argv[3]
missing = [f for f in missing_str.split() if f]
stale = [f for f in stale_str.split() if f]
has_handoff = handoff_exists == "1"

lines = ["[PLANS HEALTH] Session artifact status:", ""]

if missing:
    lines.append("MISSING (must create before compaction):")
    for f in missing:
        lines.append(f"  - {f}")
    lines.append("Action: Create missing files now per CLAUDE.md instructions.")
    lines.append("  active-context.md — current focus/learnings, ≤30 lines")
    lines.append("  decisions.md      — append-only ADL log")
    lines.append("  progress.md       — task state in checkbox format")

if stale:
    if missing:
        lines.append("")
    lines.append("STALE (exist but not updated today):")
    for f in stale:
        lines.append(f"  - {f}")
    lines.append("Action: Update stale files to reflect current session state.")

if has_handoff:
    if missing or stale:
        lines.append("")
    lines.append("HANDOFF AVAILABLE: plans/session-handoff.md exists from a prior session.")
    lines.append("Action: Read plans/session-handoff.md to restore prior session context, then delete it.")

print("\n".join(lines))
PYEOF

# --- [HOOKS HEALTH] Hyper-atomic commit hooks ---
if git rev-parse --show-toplevel &>/dev/null 2>&1; then
    HOOKS_PATH=$(git config --local core.hooksPath 2>/dev/null || echo "")
    EXPECTED="$HOME/.dotfiles/git/hooks"
    if [[ "$HOOKS_PATH" != "$EXPECTED" ]]; then
        echo "[HOOKS HEALTH] Hyper-atomic commit hooks not installed in this repo."
        echo "  Action: Run /hyper-commit-setup to enable atomic commit enforcement."
    fi
fi

exit 0
