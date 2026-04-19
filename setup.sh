#!/usr/bin/env bash

# The Router: Symlinks inside the repo (like .claude/skills/daily-standup-insights)
# point back to the Unified AI Hub (ai/skills/).
# GNU Stow mirrors this structure into your Home directory automatically.

# Ensure directories exist for stow to link into if they aren't already managed
mkdir -p ~/.config/pctx
mkdir -p ~/.cursor
mkdir -p ~/.claude
mkdir -p ~/.gemini
mkdir -p ~/.codex
mkdir -p ~/.windsurf

# Run Stow to link everything from the dotfiles root to the home directory
stow .

# Specific tool setup (for things Stow might need help with or additional setup)

# Cursor Library link (if not already handled by stow)
if [ ! -L ~/.cursor/Library ]; then
    ln -sf ~/.dotfiles/.cursor/Library ~/.cursor/Library
fi

# Install NotebookLM MCP tool (idempotent)
if ! command -v notebooklm-mcp &> /dev/null; then
    uv tool install notebooklm-mcp-cli
fi

# Symlink all shared skills from the Unified AI Hub into an agent's user-scoped
# skills directory. Existing real directories are preserved so tool-managed
# folders like ~/.codex/skills/.system are not overwritten.
link_skills_from_dir() {
    local source_dir="$1"
    local target_dir="$2"
    local mode="${3:-replace}" # replace | only-missing

    [ -d "$source_dir" ] || return 0
    mkdir -p "$target_dir"

    local skill_dir name target
    for skill_dir in "$source_dir"/*; do
        [ -d "$skill_dir" ] || continue
        [ -f "$skill_dir/SKILL.md" ] || [ -f "$skill_dir/skill.md" ] || continue

        name="$(basename "$skill_dir")"
        target="$target_dir/$name"

        if [ -e "$target" ] && [ ! -L "$target" ]; then
            echo "Skipping $target (exists and is not a symlink)"
            continue
        fi

        if [ "$mode" = "only-missing" ] && [ -e "$target" ]; then
            continue
        fi

        ln -sfn "$skill_dir" "$target"
    done
}

# Claude Code skill symlinks (repo-scoped distribution layer)
link_skills_from_dir "$HOME/.dotfiles/ai/skills" "$HOME/.dotfiles/.claude/skills"

# Codex user-scoped skill symlinks. Codex discovers user skills from
# ~/.codex/skills, so link every shared AI skill there while preserving Codex's
# own ~/.codex/skills/.system directory. Then include any Claude-local skills
# that have not yet been promoted into ai/skills.
link_skills_from_dir "$HOME/.dotfiles/ai/skills" "$HOME/.codex/skills"
link_skills_from_dir "$HOME/.dotfiles/.claude/skills" "$HOME/.codex/skills" only-missing

# Cursor skill symlinks (absolute paths — cursor resolves from ~/.cursor/skills/)
mkdir -p ~/.cursor/skills
ln -sf ~/.dotfiles/ai/skills/pctx-code-mode ~/.cursor/skills/pctx-code-mode
ln -sf ~/.dotfiles/ai/skills/explore ~/.cursor/skills/explore

# Gemini: covered via ~/.gemini/skills/ai -> ~/.dotfiles/ai/skills (stow-managed)

# Cleanup legacy files if they exist in root
rm -rf ~/.dotfiles/daily-standup-insights 2>/dev/null
rm -rf ~/.dotfiles/daily-standup-insights.skill 2>/dev/null

# Catppuccin custom module for Claude tmux integration
if [ -d "$HOME/.tmux/plugins/catppuccin-tmux/custom" ]; then
    ln -sf "$HOME/.dotfiles/tmux/scripts/catppuccin-claude.sh" \
           "$HOME/.tmux/plugins/catppuccin-tmux/custom/claude.sh"
fi

echo "Setup complete. All configurations linked via GNU Stow."
