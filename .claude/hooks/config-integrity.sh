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

# Bootstrap-if-absent files (decisions/0016, 0020) are copies, not symlinks, so
# they can drift from their tracked template. These checks make that visible
# instead of leaving it for a future session to rediscover — the live
# ~/.claude/CLAUDE.md sat six weeks ahead of its template before 0020.
check_template_drift() {
    local label="$1" live="$2" template="$3"
    [ -f "$live" ] || { ISSUES+=("$label: live file missing at $live — run setup.sh"); return 0; }
    [ -f "$template" ] || return 0
    # Compare with three things excluded, each expected to differ legitimately:
    #   - the generated lean-ctx block (rewritten at runtime by the lean-ctx binary)
    #   - the template's leading HTML comment (maintainer notes, not instructions)
    #   - blank lines (stripping the comment leaves one behind; whitespace-only
    #     divergence is not drift worth reporting)
    local a b
    a=$(sed '/<!-- lean-ctx -->/,/<!-- \/lean-ctx -->/d' "$live" 2>/dev/null | grep -v '^[[:space:]]*$' || true)
    b=$(sed '/<!-- lean-ctx -->/,/<!-- \/lean-ctx -->/d' "$template" 2>/dev/null | sed '/^<!--$/,/^-->$/d' | grep -v '^[[:space:]]*$' || true)
    if [ "$a" != "$b" ]; then
        ISSUES+=("$label: live $live differs from tracked $template (outside the generated block) — reconcile both")
    fi
}

# A rule referenced in CLAUDE.md but not linked into ~/.claude/rules does not load.
check_rule_links() {
    local missing=()
    local r
    for r in agent-user-global tool-priority context-and-compaction delegation-and-context-admission; do
        [ -f "$DOTFILES/ai/rules/$r.md" ] || continue
        [ -e "$HOME/.claude/rules/$r.md" ] || missing+=("claude:$r")
        [ -e "$HOME/.codex/rules/$r.md" ] || missing+=("codex:$r")
    done
    if [ ${#missing[@]} -gt 0 ]; then
        ISSUES+=("rule links missing (rule will NOT load): ${missing[*]} — run setup.sh")
    fi
}

# The Codex subagent gate must be in the USER-GLOBAL hooks file; the project-scoped
# .codex/hooks.json only fires with ~/.dotfiles as cwd (decisions/0018).
check_codex_agent_gate() {
    local live="$HOME/.codex/hooks.json"
    [ -f "$live" ] || { ISSUES+=("codex hooks: $live missing — run setup.sh"); return 0; }
    if ! grep -q "pre-agent-gate.sh" "$live" 2>/dev/null; then
        ISSUES+=("codex hooks: $live has no pre-agent-gate.sh matcher — subagent model/spec gate is inactive outside ~/.dotfiles")
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

check_template_drift "user-global CLAUDE.md" "$HOME/.claude/CLAUDE.md" "$DOTFILES/.claude-global/CLAUDE.md"
check_rule_links
check_codex_agent_gate

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
