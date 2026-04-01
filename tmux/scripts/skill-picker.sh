#!/usr/bin/env bash
# skill-picker.sh — fzf picker for skills, commands, slash commands, and saved prompts
#
# Sources:
#   ai/skills/*/SKILL.md   → Claude Code skill invocations (/skill-name)
#   ai/commands/*.md       → AI commands
#   .claude/commands/*.md  → Claude Code slash commands (/cmd-name)
#   ai/prompts/*.md        → Saved prompt templates (pasted via tmux buffer)
#
# Keybindings (inside picker):
#   Enter    → paste invocation into parent pane (caller keeps focus; press Enter to run)
#   Alt-P    → toggle full file preview
#   Esc      → close
#
# Bound to: Ctrl+A /  (tmux.conf)
# Requires: PARENT_PANE env var set by tmux display-popup -e PARENT_PANE=#{pane_id}

set -euo pipefail

DOTFILES="${DOTFILES_ROOT:-$HOME/.dotfiles}"

# ── Build item list (tab-separated: TYPE\tNAME\tPATH) ───────────────────────
declare -a items=()

# Skills: ai/skills/*/SKILL.md or skill.md
while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    name=$(basename "$(dirname "$path")")
    items+=("skill	${name}	${path}")
done < <(find "$DOTFILES/ai/skills" -maxdepth 2 \( -name "SKILL.md" -o -name "skill.md" \) 2>/dev/null | sort)

# Commands: ai/commands/*.md
while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    name=$(basename "$path" .md)
    items+=("command	${name}	${path}")
done < <(find "$DOTFILES/ai/commands" -maxdepth 1 -name "*.md" 2>/dev/null | sort)

# Slash commands: .claude/commands/*.md
while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    name=$(basename "$path" .md)
    items+=("/cmd	/${name}	${path}")
done < <(find "$DOTFILES/.claude/commands" -maxdepth 1 -name "*.md" 2>/dev/null | sort)

# Saved prompts: ai/prompts/*.md
while IFS= read -r path; do
    [[ -z "$path" ]] && continue
    name=$(basename "$path" .md)
    items+=("prompt	${name}	${path}")
done < <(find "$DOTFILES/ai/prompts" -maxdepth 1 -name "*.md" 2>/dev/null | sort)

if [[ ${#items[@]} -eq 0 ]]; then
    echo "No skills, commands, or prompts found in $DOTFILES"
    read -r
    exit 0
fi

# ── fzf picker ───────────────────────────────────────────────────────────────
selected=$(printf '%s\n' "${items[@]}" \
    | fzf \
        --delimiter='\t' \
        --with-nth=1,2 \
        --prompt="  skills & prompts: " \
        --header="Enter: paste · Alt-P: preview · Esc: close" \
        --border \
        --height=80% \
        --ansi \
        --preview='cat {3}' \
        --preview-window='right:55%:wrap:hidden' \
        --bind='alt-p:toggle-preview' \
    2>/dev/null || true)

[[ -z "$selected" ]] && exit 0

item_type=$(cut -f1 <<< "$selected")
item_name=$(cut -f2 <<< "$selected")
item_path=$(cut -f3 <<< "$selected")


# ── Determine text to send ───────────────────────────────────────────────────
text=""
case "$item_type" in
    /cmd)    text="$item_name" ;;
    skill)   text="/$item_name" ;;
    command) text="/$item_name" ;;
    prompt)
        # Strip frontmatter (everything between --- markers)
        text=$(sed -n '/^---$/,/^---$/!p' "$item_path" | sed '/^$/N;/^\n$/d')
        ;;
    *)       exit 0 ;;
esac

[[ -z "$text" ]] && exit 0

# ── Always copy to clipboard ─────────────────────────────────────────────────
printf '%s' "$text" | pbcopy

# ── Try send-keys to parent pane (works for regular terminals, not Claude TUI)
target="${PARENT_PANE:-}"
if [[ -n "$target" ]]; then
    tmux send-keys -t "$target" -l -- "$text" 2>/dev/null || true
fi

# ── Always show status message ────────────────────────────────────────────────
tmux display-message "📋 Copied to clipboard — Cmd+V to paste in Claude Code" 2>/dev/null || true
