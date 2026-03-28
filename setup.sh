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

# Cleanup legacy files if they exist in root
rm -rf ~/.dotfiles/daily-standup-insights 2>/dev/null
rm -rf ~/.dotfiles/daily-standup-insights.skill 2>/dev/null

echo "Setup complete. All configurations linked via GNU Stow."
