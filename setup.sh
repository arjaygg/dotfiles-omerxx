#!/usr/bin/env bash
stow .

# Setup Claude Code global config
mkdir -p ~/.claude
ln -sf ~/.dotfiles/.claude/commands ~/.claude/commands
ln -sf ~/.dotfiles/.claude/settings.json ~/.claude/settings.json
ln -sf ~/.dotfiles/.claude/output-styles ~/.claude/output-styles
