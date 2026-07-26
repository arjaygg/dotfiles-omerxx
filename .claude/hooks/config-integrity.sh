#!/usr/bin/env bash
# ConfigChange hook: advisory symlink + JSON integrity check for settings files.
# Wired with source: "*_settings" filter to avoid firing on every skill/agent edit.
# Symlink/JSON checks are advisory (exit 0). Agent model: frontmatter is hard-enforced (exit 1 on violation).

set -euo pipefail
trap 'exit 0' ERR

DOTFILES="$HOME/.dotfiles"
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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

ALLOWED_MODELS=("haiku" "sonnet" "opus" "fable" "inherit")
BAD_MODELS=()

check_agent_models() {
    local dir="$SCRIPT_ROOT/.claude/agents"
    [ -d "$dir" ] || return 0
    local f model m valid
    for f in "$dir"/*.md; do
        [ -e "$f" ] || continue
        model=$(awk '/^---$/{c++; next} c==1 && /^model:/{sub(/^model:[ \t]*/,""); print; exit}' "$f")
        if [ -z "$model" ]; then
            BAD_MODELS+=("$f: missing 'model:' frontmatter field")
            continue
        fi
        valid=0
        for m in "${ALLOWED_MODELS[@]}"; do
            [ "$model" = "$m" ] && valid=1 && break
        done
        if [ "$valid" -ne 1 ]; then
            BAD_MODELS+=("$f: model '$model' not in {${ALLOWED_MODELS[*]}} (aliases only, no dated model IDs)")
        fi
    done
}

check_agent_models

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

# Agent model: frontmatter is hard-enforced (unlike the advisory checks above):
# a missing/invalid model: field is a deterministic policy violation, not drift to warn about.
if [ ${#BAD_MODELS[@]} -gt 0 ]; then
    echo "❌ Agent model frontmatter violations:" >&2
    for b in "${BAD_MODELS[@]}"; do
        echo "  • $b" >&2
    done
    exit 1
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
