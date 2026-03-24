# AI Agent Primitives

This directory is the authoritative source for common AI Agent primitives (rules, skills, commands, and output-styles) shared across all AI agents on this machine.

## Supported Agents

The following agents are configured to honor these primitives through granular symlinking into their respective home configuration directories:

- **Claude Code:** `~/.claude/`
- **Gemini CLI:** `~/.gemini/`
- **Codex CLI:** `~/.codex/`
- **Cursor:** `~/.cursor/`
- **Windsurf:** `~/.windsurf/`

## Structure

- `commands/`: Shared command definitions (e.g., smart-commit).
- `output-styles/`: Shared personas and formatting styles (e.g., technical-lead).
- `rules/`: Global and project-level constraints.
- `skills/`: Modular, executable agent capabilities.

## Setup & Maintenance

The primitives are linked granularly from this directory into the agent-specific folders. This ensures that a single update to a rule or skill in this repository is immediately reflected across all AI tools.

- **Source:** `~/.dotfiles/ai/`
- **Link Strategy:** Granular symlinking of individual files and directories.
