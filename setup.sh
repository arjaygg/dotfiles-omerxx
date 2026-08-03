#!/usr/bin/env bash

# The Router: Symlinks inside the repo (like .claude/skills/daily-standup-insights)
# point back to the Unified AI Hub (ai/skills/).
# GNU Stow mirrors this structure into your Home directory automatically.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

run_setup_check() {
    echo "setup check: validating tracked config boundaries without writing runtime files"
    (
        set -e
        cd "$ROOT"
        bash -n setup.sh
        bash -n scripts/check-skill-drift.sh
        python3 scripts/shell_syntax_check.py --summary || true
        python3 scripts/syntax_check.py --summary || true
        python3 scripts/guidance_adapter_check.py --summary || true
        python3 scripts/autonomous_skill_check.py --summary || true
        python3 scripts/mcp_topology_check.py --summary || true
        python3 scripts/hook_fixture_runner.py .claude/hooks/pre-tool-gate-v2.sh scripts/fixtures/pretool-gate-v2.json --summary || true
        python3 scripts/hook_target_check.py ai/config/claude/settings.base.json --summary || true
        python3 scripts/hook_output_schema_check.py .claude/hooks --summary || true
        python3 scripts/self_modification_check.py --summary || true
        python3 scripts/config_inventory.py --summary || true
        python3 scripts/config_base_hygiene_check.py --summary || true
        python3 scripts/public_hygiene_check.py --summary || true
        python3 scripts/config_doctor.py --summary || true
        python3 scripts/instruction_budget_check.py --summary || true
        bash scripts/check-skill-drift.sh .claude/skills .gemini/skills .cursor/skills || true
        # --check-coverage is scoped to .claude/skills and $HOME/.claude/skills only:
        # those are the two dirs setup.sh promises full 1:1 ai/skills/ coverage for.
        # .cursor/skills and .gemini/skills link a deliberately partial subset.
        bash scripts/check-skill-drift.sh --check-coverage ai/skills .claude/skills "$HOME/.claude/skills" || true
        python3 scripts/hook_config_check.py ai/config/claude/settings.base.json --summary || true
        python3 scripts/skill_reference_check.py --summary || true
    )
}

case "${1:-}" in
    --check)
        run_setup_check
        ;;
    --dry-run)
        run_setup_check
        echo "setup dry-run: no stow, symlink, install, prune, extension, or cleanup commands were run"
        ;;
    --help|-h)
        echo "usage: $0 [--check|--dry-run]"
        ;;
    "")
        ;;
    *)
        echo "usage: $0 [--check|--dry-run]" >&2
        exit 2
        ;;
esac

if [ "${1:-}" = "--check" ] || [ "${1:-}" = "--dry-run" ] || [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    exit 0
fi

# Ensure directories exist for stow to link into if they aren't already managed
mkdir -p ~/.cursor
mkdir -p ~/.claude
mkdir -p ~/.gemini
mkdir -p ~/.codex
mkdir -p ~/.windsurf

# Run Stow to link everything from the dotfiles root to the home directory
stow .

# Specific tool setup (for things Stow might need help with or additional setup)
ln -sfn "$HOME/.dotfiles/.codex/AGENTS.md" "$HOME/.codex/AGENTS.md"

# Claude Code runtime settings: untracked, runtime-managed projection
# (decisions/0016). Bootstrap from the base template (+ machine overlay when
# present) on fresh machines only — never regenerate over an existing live
# file, which the lean-ctx daemon and Claude Code legitimately rewrite.
if [ ! -f "$HOME/.dotfiles/.claude/settings.json" ]; then
    _claude_overlay="$HOME/.config/dotfiles-ai/claude.overlay.json"
    if [ -f "$_claude_overlay" ]; then
        python3 "$HOME/.dotfiles/scripts/config_generate.py" \
            "$HOME/.dotfiles/ai/config/claude/settings.base.json" \
            --overlay "$_claude_overlay" \
            --write "$HOME/.dotfiles/.claude/settings.json"
    else
        python3 "$HOME/.dotfiles/scripts/config_generate.py" \
            "$HOME/.dotfiles/ai/config/claude/settings.base.json" \
            --write "$HOME/.dotfiles/.claude/settings.json"
    fi
fi
ln -sfn "$HOME/.dotfiles/.claude/settings.json" "$HOME/.claude/settings.json"

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

# One persistent provider proxy; normal client sessions must not register the
# Headroom MCP server (each registration creates a disposable Docker container).
if command -v headroom &> /dev/null; then
    export HEADROOM_CONTEXT_TOOL=lean-ctx
    export HEADROOM_DISABLE_KOMPRESS=1
    export HEADROOM_EXCLUDE_TOOLS="bash,codebase_search,ctx_call,ctx_compose,ctx_expand,ctx_glob,ctx_read,ctx_search,ctx_session,ctx_shell,ctx_tree,exec_command,glob,grep,grep_search,list_directory,list_files,listdirectory,listfiles,mcp__lean-ctx__ctx_call,mcp__lean-ctx__ctx_compose,mcp__lean-ctx__ctx_expand,mcp__lean-ctx__ctx_glob,mcp__lean-ctx__ctx_read,mcp__lean-ctx__ctx_search,mcp__lean-ctx__ctx_session,mcp__lean-ctx__ctx_shell,mcp__lean-ctx__ctx_tree,mcp__lean-ctx__shell,mcp__lean_ctx__ctx_call,mcp__lean_ctx__ctx_compose,mcp__lean_ctx__ctx_expand,mcp__lean_ctx__ctx_glob,mcp__lean_ctx__ctx_read,mcp__lean_ctx__ctx_search,mcp__lean_ctx__ctx_session,mcp__lean_ctx__ctx_shell,mcp__lean_ctx__ctx_tree,mcp__lean_ctx__shell,read,read_file,read_many_files,read_text_file,readfile,run_command,run_shell_command,search,search_file_content,search_files,semantic_search,shell,shell_command,view,view_file"
    export HEADROOM_NO_SUBSCRIPTION_TRACKING=1
    if [ -f "$HOME/.headroom/ccr_store.db" ]; then
        python3 "$HOME/.dotfiles/scripts/headroom_hardening.py" \
            audit-ccr "$HOME/.headroom/ccr_store.db" --delete-invalid
    fi
    if headroom install status >/dev/null 2>&1; then
        headroom install restart --profile default
    else
        headroom install apply --preset persistent-docker --profile default --port 8788
    fi
    python3 "$HOME/.dotfiles/scripts/headroom_hardening.py" \
        containers --stop-orphans >/dev/null 2>&1 || true
    if [ -f "$HOME/.codex/config.toml" ]; then
        python3 "$HOME/.dotfiles/scripts/headroom_hardening.py" \
            clean-codex "$HOME/.codex/config.toml" --write
    fi
fi

# Retired skills (per ai/skills/REMOVALS.md ledger) must not get a skills symlink.
_removals_ledger="$HOME/.dotfiles/ai/skills/REMOVALS.md"
is_retired_skill() {
    [ -f "$_removals_ledger" ] || return 1
    grep -qE "^\| \`$1\` \| retired \|" "$_removals_ledger"
}

# Every managed skills directory. Used by both the link loops and the removal pass, so a
# newly-retired skill cannot survive in a directory the removal pass forgot about.
_managed_skill_dirs() {
    printf '%s\n' \
        "$HOME/.dotfiles/.claude/skills" \
        "$HOME/.claude/skills" \
        "$HOME/.codex/skills" \
        "$HOME/.gemini/skills" \
        "$HOME/.agents/skills"
}

# Skipping link *creation* is not enough: a skill retired after its link already existed keeps
# that link forever. `check-skill-drift.sh --prune-stale-links` does not catch it either — it
# removes only dangling links, and a retired skill's target is still a valid directory. So
# retirement needs an explicit removal pass.
#
# Only ever unlinks symlinks. A real directory is left alone and reported, because tool-managed
# folders (e.g. ~/.codex/skills/.system) live in these same trees and deleting one would be
# destructive, not tidy.
remove_retired_skill_links() {
    [ -f "$_removals_ledger" ] || return 0
    local name target dir removed=0

    while IFS= read -r name; do
        [ -n "$name" ] || continue
        while IFS= read -r dir; do
            target="$dir/$name"
            [ -e "$target" ] || [ -L "$target" ] || continue
            if [ -L "$target" ]; then
                rm -f "$target" && {
                    echo "Removed retired skill link: $target"
                    removed=$((removed + 1))
                }
            else
                echo "Retired skill '$name' is a real directory at $target — left in place (remove by hand if intended)"
            fi
        done < <(_managed_skill_dirs)
    done < <(sed -nE 's/^\| `([A-Za-z0-9._-]+)` \| retired \|.*/\1/p' "$_removals_ledger")

    [ "$removed" -gt 0 ] && echo "Retired-skill cleanup: removed $removed link(s)"
    return 0
}

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

        # Without this, every run re-creates retired links via the `ln -sfn` below — the
        # .claude/skills loops guard for this but this function did not, so ~/.codex/skills
        # resurrected them on each setup.
        if is_retired_skill "$name"; then
            continue
        fi

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
    is_retired_skill "$_name" && continue
    _target="$HOME/.dotfiles/.claude/skills/$_name"
    if [ -e "$_target" ] && [ ! -L "$_target" ]; then
        echo "Skipping $_target (exists and is not a symlink)"
        continue
    fi
    ln -sfn "../../ai/skills/$_name" "$_target"
done

# Claude Code references symlink — relative link so worktrees resolve correctly.
_references_target="$HOME/.dotfiles/.claude/references"
if [ -e "$_references_target" ] && [ ! -L "$_references_target" ]; then
    echo "Skipping $_references_target (exists and is not a symlink)"
else
    ln -sfn "../ai/references" "$_references_target"
fi

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
    is_retired_skill "$_name" && continue
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
for _skill in explore quarantine-triage-live; do
    [ -d ~/.dotfiles/ai/skills/$_skill ] && ln -sfn ~/.dotfiles/ai/skills/$_skill ~/.cursor/skills/$_skill
done

# Cursor output-style symlinks — all styles from ai/output-styles/
mkdir -p ~/.cursor/output-styles
for _style in ~/.dotfiles/ai/output-styles/*.md; do
    [ -f "$_style" ] && ln -sf "$_style" ~/.cursor/output-styles/"$(basename "$_style")"
done

# Gemini/Codex modern skill discovery is covered by ~/.agents/skills.
# Do not place aggregate symlinks inside ~/.gemini/skills; entries there must be real skills.
# check-skill-drift.sh --prune-stale-links removes stale generated skill symlinks only.
if [ -f "$HOME/.dotfiles/scripts/check-skill-drift.sh" ]; then
    bash "$HOME/.dotfiles/scripts/check-skill-drift.sh" --prune-stale-links \
        "$HOME/.claude/skills" \
        "$HOME/.codex/skills" \
        "$HOME/.gemini/skills" \
        "$HOME/.cursor/skills" || true
fi

# Runs AFTER every link pass, so a retired skill cannot be re-created and then survive. Ordering
# is load-bearing: placed before the link passes it would remove links they immediately restore.
remove_retired_skill_links
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
