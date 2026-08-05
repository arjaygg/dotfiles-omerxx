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

## Master Router (Task-Specific Switching)

You can use `claude-router` to start a session that supports all backends at once. Use the `/model` command in Claude Code to switch between them on the fly:

- `/model claude-native`: Use the official Claude Code backend.
- `/model claude-gemini`: Route tasks to Gemini 2.0 Pro.
- `/model claude-codex`: Route tasks to Codex (GPT-4o).
- `/model claude-cursor`: Route tasks to Cursor (GPT-4o via Cursor Agent).

## Model Mappings for Claude Code Menu

When using `claude-router`, the standard `/model` menu roles are mapped to your best available models:

- **Sonnet 4.6 (Default)**: Claude 3.7 Sonnet (Native)
- **Opus 4.6 (Capable)**: Gemini 2.0 Pro (CLI)
- **Haiku 4.5 (Fast)**: Gemini 2.0 Flash (CLI)

### **Direct Model Switching**

You can also use `/model --model <alias>` to switch to any specific model from your accounts:

- **Claude Native**: `claude-native`, `claude-3-5-sonnet`, `claude-3-5-haiku`
- **Gemini**: `g-pro`, `g-flash`
- **Codex (GPT)**: `c-4o`, `c-mini`, `c-o1`, `c-o3`
- **Cursor**: `claude-cursor`, `cur-sonnet`
