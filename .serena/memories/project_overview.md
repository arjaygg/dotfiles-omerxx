# Project Overview

## Purpose
Personal dotfiles repository for agallentes. Manages configuration for macOS tools, AI agents (Claude Code, Gemini, Codex, Cursor, Windsurf), shell environment, editors, and window managers.

## Tech Stack
- Shell: nushell (primary), zsh (legacy), bash (scripts)
- Package Manager: Homebrew (Brewfile), Nix/nix-darwin
- Config Deployment: GNU Stow (stows dotfiles into ~/)
- AI Agents: Claude Code, Gemini CLI, Codex, Cursor, Windsurf
- MCP Gateway: pctx v0.6.0 (routes all MCP traffic for all agents)
- Branch Stacking: Charcoal (gt) + custom stack scripts in .claude/scripts/
- Editor: Neovim (nvim/), VSCode
- Terminal: Ghostty, tmux
- Window Manager: Aerospace, Sketchybar, Skhd

## Key Files
- CLAUDE.md — per-session instructions for Claude Code (read every session)
- setup.sh — creates all agent config symlinks (run on fresh machine)
- pctx.json — symlink to ~/.config/pctx/pctx.json (MCP gateway config)
- Brewfile — Homebrew package list
- .stowrc — GNU Stow configuration

## Key Directories
- ai/skills/ — all skill definitions (source of truth; symlinked into .claude/skills/)
- .claude/ — Claude Code config, hooks, agents, scripts, skills
- plans/ — active-context.md, decisions.md, progress.md
- .cursor/, .windsurf/, .gemini/, .codex/ — agent-specific configs (all symlinked from dotfiles)
- nvim/ — Neovim config
- nushell/ — Nushell config
