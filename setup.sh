#!/usr/bin/env bash

# The Router: Symlinks inside the repo (like .claude/skills/daily-standup-insights)
# point back to the Unified AI Hub (ai/skills/).
# GNU Stow mirrors this structure into your Home directory automatically.

stow .

# Specific tool setup (for things Stow can't easily handle)
mkdir -p ~/.cursor
ln -sf ~/.dotfiles/.cursor/Library ~/.cursor/Library

# Claude Code global settings (Stow handles the directory structure)

# Install NotebookLM MCP tool
uv tool install notebooklm-mcp-cli
mkdir -p ~/.claude
ln -sf ~/.dotfiles/.claude/settings.json ~/.claude/settings.json

# Gemini setup - dynamically symlink tracked config directories/files
mkdir -p ~/.gemini
for item in ~/.dotfiles/.gemini/*; do
    if [ -e "$item" ]; then
        base_item=$(basename "$item")
        ln -sf "$item" ~/.gemini/"$base_item"
    fi
done

# Cleanup legacy files if they exist in root
rm -rf ~/.dotfiles/daily-standup-insights 2>/dev/null
rm -rf ~/.dotfiles/daily-standup-insights.skill 2>/dev/null
