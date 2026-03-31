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

# Claude Code skill symlinks (relative paths, tool-agnostic)
mkdir -p ~/.dotfiles/.claude/skills
ln -sf ../../ai/skills/pctx-code-mode ~/.dotfiles/.claude/skills/pctx-code-mode
ln -sf ../../ai/skills/autoresearch ~/.dotfiles/.claude/skills/autoresearch
ln -sf ../../ai/skills/explore ~/.dotfiles/.claude/skills/explore

# Codex skill symlinks (absolute paths — codex resolves from ~/.codex/skills/)
mkdir -p ~/.codex/skills
ln -sf ~/.dotfiles/ai/skills/pctx-code-mode ~/.codex/skills/pctx-code-mode
ln -sf ~/.dotfiles/ai/skills/explore ~/.codex/skills/explore

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
