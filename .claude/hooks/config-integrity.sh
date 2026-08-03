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

# The coordinator tier is the one policy value in ~/.codex/config.toml worth
# tracking; everything else in that file is runtime state. A tracked value that
# drifts below the live one silently demotes the coordinator on a rebuild, which
# is exactly what had happened (tracked gpt-5.5 vs live gpt-5.6-sol).
check_codex_coordinator_model() {
    local live="$HOME/.codex/config.toml" tracked="$DOTFILES/.codex/config.toml"
    [ -f "$live" ] && [ -f "$tracked" ] || return 0
    local lm tm
    lm=$(grep -m1 '^model = ' "$live" 2>/dev/null | tr -d ' "' || true)
    tm=$(grep -m1 '^model = ' "$tracked" 2>/dev/null | tr -d ' "' || true)
    if [ -n "$lm" ] && [ -n "$tm" ] && [ "$lm" != "$tm" ]; then
        ISSUES+=(".codex/config.toml: coordinator tier differs — live '$lm' vs tracked '$tm'; a rebuild would use the tracked value (decisions/0018)")
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
# ~/.claude is a REAL directory: 58 entries, mostly Claude Code runtime state
# (audit.log, bg-jobs, cache, daemon, debug, file-history, todos, shell-snapshots).
# Only individual config entries are linked into dotfiles; `hooks/` and `skills/`
# are real dirs too. Expecting the whole directory to be a symlink was wrong — it
# would require the repo to absorb all runtime state. Check the config entries
# that are genuinely meant to be links instead (decisions/0021).
for _entry in agents commands output-styles plugins claude-statusline; do
    [ -e "$DOTFILES/.claude/$_entry" ] || continue
    check_symlink ".claude/$_entry" "$HOME/.claude/$_entry" "$DOTFILES/.claude/$_entry"
done
check_symlink ".claude/settings.json" "$HOME/.claude/settings.json" "$DOTFILES/.claude/settings.json"
check_symlink ".gemini/GEMINI.md" "$HOME/.gemini/GEMINI.md" "$DOTFILES/.gemini/GEMINI.md"

# ~/.codex/config.toml is runtime-written by Codex itself ([hooks.state]
# trusted_hash, [notice.model_migrations], [tui.model_availability_nux]), so it
# cannot be a symlink into the repo without dirtying the tree on every session —
# same reasoning as settings.json (decisions/0016). Whole-file comparison is
# useless here (268 diff lines, nearly all runtime). Check only the policy-
# relevant key: the pinned coordinator tier from decisions/0018.
check_codex_coordinator_model
check_symlink "$HOME/.agents/skills" "$HOME/.agents/skills" "$DOTFILES/ai/skills"

check_template_drift "user-global CLAUDE.md" "$HOME/.claude/CLAUDE.md" "$DOTFILES/.claude-global/CLAUDE.md"
check_template_drift "user-global AGENTS.md" "$HOME/.codex/AGENTS.md" "$DOTFILES/ai/config/codex/AGENTS.global.base.md"
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
