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

# Cursor config symlinks (explicit — ~/.cursor is a real dir, config items linked from dotfiles)
# Runtime state (projects, plans, plugins, extensions, etc.) lives in the real dir only.
mkdir -p ~/.cursor
for _dir in commands hooks rules; do
    [ -d ~/.dotfiles/.cursor/$_dir ] && ln -sfn ~/.dotfiles/.cursor/$_dir ~/.cursor/$_dir
done
for _file in rules.md CURSOR_SETUP_GUIDE.md mcp.example.json blocklist; do
    [ -f ~/.dotfiles/.cursor/$_file ] && ln -sf ~/.dotfiles/.cursor/$_file ~/.cursor/$_file
done
# Library link
ln -sfn ~/.dotfiles/.cursor/Library ~/.cursor/Library

# Install NotebookLM MCP tool (idempotent)
if ! command -v notebooklm-mcp &> /dev/null; then
    uv tool install notebooklm-mcp-cli
fi

# Install headroom-ai context compression tool (idempotent)
if ! command -v headroom &> /dev/null; then
    uv tool install "headroom-ai[proxy,code,memory]"
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

# Claude Code skill symlinks — relative links so worktrees resolve correctly.
mkdir -p "$HOME/.dotfiles/.claude/skills"
for _skill_dir in "$HOME/.dotfiles/ai/skills"/*/; do
    [ -d "$_skill_dir" ] || continue
    { [ -f "${_skill_dir}SKILL.md" ] || [ -f "${_skill_dir}skill.md" ]; } || continue
    _name="$(basename "${_skill_dir%/}")"
    _target="$HOME/.dotfiles/.claude/skills/$_name"
    if [ -e "$_target" ] && [ ! -L "$_target" ]; then
        echo "Skipping $_target (exists and is not a symlink)"
        continue
    fi
    ln -sfn "../../ai/skills/$_name" "$_target"
done

# Claude Code user-scoped skills: ~/.claude/skills must be a REAL directory.
# Stow creates it as a directory symlink (→ .dotfiles/.claude/skills), which
# Claude Code does not follow when discovering user-scoped skills across projects.
# Replace any directory symlink with a real dir containing individual symlinks.
if [ -L "$HOME/.claude/skills" ]; then
    rm "$HOME/.claude/skills"
fi
mkdir -p "$HOME/.claude/skills"
for _skill_dir in "$HOME/.dotfiles/ai/skills"/*/; do
    [ -d "$_skill_dir" ] || continue
    { [ -f "${_skill_dir}SKILL.md" ] || [ -f "${_skill_dir}skill.md" ]; } || continue
    _name="$(basename "${_skill_dir%/}")"
    _dest="$HOME/.claude/skills/$_name"
    if [ -e "$_dest" ] && [ ! -L "$_dest" ]; then
        echo "Skipping $_dest (exists and is not a symlink)"
        continue
    fi
    ln -sfn "$HOME/.dotfiles/ai/skills/$_name" "$_dest"
done

# Claude Code command symlinks — ai/commands/*.md → .claude/commands/ as relative links.
# Only ai/commands/ files are symlinked; Claude-specific files already in .claude/commands/
# (session-*, context-eval, migration-clean) are left untouched as real files.
mkdir -p "$HOME/.dotfiles/.claude/commands"
for _cmd in "$HOME/.dotfiles/ai/commands"/*.md; do
    [ -f "$_cmd" ] || continue
    _base="$(basename "$_cmd")"
    _target="$HOME/.dotfiles/.claude/commands/$_base"
    if [ -e "$_target" ] && [ ! -L "$_target" ]; then
        echo "Skipping $_target (exists and is not a symlink)"
        continue
    fi
    ln -sfn "../../ai/commands/$_base" "$_target"
done

# Claude Code agent symlinks — ai/agents/*.md → .claude/agents/ as relative links.
# Source of truth is ai/agents/; .claude/agents/ holds the distribution symlinks.
mkdir -p "$HOME/.dotfiles/.claude/agents"
for _agent in "$HOME/.dotfiles/ai/agents"/*.md; do
    [ -f "$_agent" ] || continue
    _base="$(basename "$_agent")"
    _target="$HOME/.dotfiles/.claude/agents/$_base"
    if [ -e "$_target" ] && [ ! -L "$_target" ]; then
        echo "Skipping $_target (exists and is not a symlink)"
        continue
    fi
    ln -sfn "../../ai/agents/$_base" "$_target"
done

# Cross-tool standard skills path (Codex 0.130.0+, Gemini 0.42.0+).
# A single symlink covers all tools that discover skills from ~/.agents/skills.
mkdir -p "$HOME/.agents"
ln -sfn "$HOME/.dotfiles/ai/skills" "$HOME/.agents/skills"

# Codex legacy path: keep for Codex < 0.130.0. Both paths coexist harmlessly.
link_skills_from_dir "$HOME/.dotfiles/ai/skills" "$HOME/.codex/skills"
link_skills_from_dir "$HOME/.dotfiles/.claude/skills" "$HOME/.codex/skills" only-missing

# Cursor skill symlinks — explicit subset from ai/skills/
# Remove dangling symlinks (e.g. left over when .cursor/skills moved out of dotfiles source)
for _d in skills output-styles; do
    [ -L "$HOME/.cursor/$_d" ] && [ ! -e "$HOME/.cursor/$_d" ] && rm "$HOME/.cursor/$_d"
done
mkdir -p ~/.cursor/skills
for _skill in pctx-code-mode explore quarantine-triage-live; do
    [ -d ~/.dotfiles/ai/skills/$_skill ] && ln -sfn ~/.dotfiles/ai/skills/$_skill ~/.cursor/skills/$_skill
done

# Cursor output-style symlinks — all styles from ai/output-styles/
mkdir -p ~/.cursor/output-styles
for _style in ~/.dotfiles/ai/output-styles/*.md; do
    [ -f "$_style" ] && ln -sf "$_style" ~/.cursor/output-styles/"$(basename "$_style")"
done

# Gemini: covered via ~/.gemini/skills/ai -> ~/.dotfiles/ai/skills (stow-managed)
mkdir -p "$HOME/.gemini/antigravity-cli"
ln -sfn "$HOME/.dotfiles/.gemini/settings.json" "$HOME/.gemini/antigravity-cli/settings.json"

# Gemini extension: link dotfiles-guards extension (hooks, policies, commands).
# stow handles ~/.gemini/extension/ → .dotfiles/.gemini/extension/ automatically,
# but the extension must be explicitly registered with gemini extension link.
mkdir -p "$HOME/.dotfiles/.gemini/extension/scripts"
if command -v gemini >/dev/null 2>&1; then
    if ! gemini extension list 2>/dev/null | grep -q "dotfiles-guards"; then
        gemini extension link "$HOME/.dotfiles/.gemini/extension" 2>/dev/null || true
    fi
fi

# AI Engineering Coach — sync rules from upstream on first install (idempotent)
if [ ! -d "$HOME/.dotfiles/ai/skills/coach/rules" ] || \
   [ "$(find "$HOME/.dotfiles/ai/skills/coach/rules" -maxdepth 1 -name "*.md" 2>/dev/null | wc -l)" -eq 0 ]; then
    echo "Syncing AI Engineering Coach rules from upstream..."
    bash "$HOME/.dotfiles/ai/skills/coach/sync.sh" || echo "⚠️  Coach sync failed (check gh auth). Run manually: bash ~/.dotfiles/ai/skills/coach/sync.sh"
fi

# Cleanup legacy files if they exist in root
rm -rf ~/.dotfiles/daily-standup-insights 2>/dev/null
rm -rf ~/.dotfiles/daily-standup-insights.skill 2>/dev/null

# Catppuccin custom module for Claude tmux integration
if [ -d "$HOME/.tmux/plugins/catppuccin-tmux/custom" ]; then
    ln -sf "$HOME/.dotfiles/tmux/scripts/catppuccin-claude.sh" \
           "$HOME/.tmux/plugins/catppuccin-tmux/custom/claude.sh"
fi

echo "Setup complete. All configurations linked via GNU Stow."
