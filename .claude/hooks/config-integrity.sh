#!/usr/bin/env bash
# ConfigChange hook: advisory symlink + JSON integrity check for settings files.
# Wired with source: "*_settings" filter to avoid firing on every skill/agent edit.
# Always exits 0 — advisory only; never blocks the session.

set -euo pipefail
trap 'exit 0' ERR

DOTFILES="$HOME/.dotfiles"
ISSUES=()

check_symlink() {
    local label="$1" path="$2" expected_target="$3"
    if [ ! -L "$path" ]; then
        ISSUES+=("$label: $path is not a symlink (expected link to $expected_target)")
    elif [ ! -e "$path" ]; then
        ISSUES+=("$label: $path symlink is broken")
    fi
}

check_json() {
    local path="$1"
    if [ -f "$path" ] && command -v python3 >/dev/null 2>&1; then
        if ! python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$path" 2>/dev/null; then
            ISSUES+=("JSON invalid: $path")
        fi
    fi
}

# Critical config symlinks
check_symlink ".claude → dotfiles" "$HOME/.claude" "$DOTFILES/.claude"
check_symlink ".claude/settings.json" "$HOME/.claude/settings.json" "$DOTFILES/.claude/settings.json"
check_symlink ".gemini/GEMINI.md" "$HOME/.gemini/GEMINI.md" "$DOTFILES/.gemini/GEMINI.md"
check_symlink ".codex/config.toml" "$HOME/.codex/config.toml" "$DOTFILES/.codex/config.toml"
check_symlink "$HOME/.agents/skills" "$HOME/.agents/skills" "$DOTFILES/ai/skills"

# JSON validity for settings files that changed
SOURCE="${CLAUDE_CONFIG_CHANGE_SOURCE:-}"
if [[ "$SOURCE" == *settings* ]]; then
    check_json "$HOME/.claude/settings.json"
fi

if [ ${#ISSUES[@]} -eq 0 ]; then
    exit 0
fi

# Emit advisory via additionalContext (non-blocking)
python3 - "${ISSUES[@]}" <<'PYEOF'
import json, sys
issues = sys.argv[1:]
msg = "⚠️  Config integrity warnings:\n" + "\n".join(f"  • {i}" for i in issues)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "ConfigChange",
        "additionalContext": msg
    }
}))
PYEOF

exit 0
