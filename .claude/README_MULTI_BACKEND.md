# Claude Code Multi-Backend Integration

This integration allows you to use different backends for Claude Code via CLIProxyAPI.

## Available Backends

- **Gemini**: `claude-gemini` (Port 8317)
- **Codex**: `claude-codex` (Port 8318)
- **Cursor**: `claude-cursor` (Port 8319)
- **Native**: `claude-native` (Standard Anthropic API)

## Setup

1. Log in to the respective backends once:
   - Gemini: `CLIProxyAPI -login`
   - Codex: `CLIProxyAPI -codex-login`
   - Cursor: (Handled via `cursor-agent` CLI)

2. Start using the aliases provided in your zshrc.

## Configuration

Configs are stored in `~/.config/cliproxyapi/`.
Launch script is at `~/.dotfiles/.claude/scripts/claude-launch.sh`.
