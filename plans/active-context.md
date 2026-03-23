# Active Context

## Current Focus: AI Agent Behavior Improvement (2026-03-23)

Following a 2-hour session audit (`5f651a5e`), we identified systematic inefficiency patterns across Claude Code's own behavior and the pctx agent configuration. The audit found:

- 47 Bash calls for file ops (vs 0 Serena, 0 Grep, 2 Glob)
- No tool priority guidance anywhere in the project
- CLAUDE.md missing (no per-session behavioral guidance)
- Gemini settings.json had 6 stale MCP servers (not pctx)
- Cursor and Windsurf configs were unlinked regular files
- Codex config was unlinked and diverged from dotfiles
- Serena onboarding never run → empty `.serena/memories/`
- pctx SKILL.md had wrong example code and narrow triggers

### Completed This Session

1. **Agent config convergence**: All 5 agents (Claude Code, Gemini, Codex, Cursor, Windsurf) now route through pctx gateway. Cursor and Windsurf symlinks created.
2. **Gemini dual-source fix**: Replaced 6 stale servers in `~/.gemini/settings.json` with pctx.
3. **markitdown added**: `markitdown-mcp` added to `/Users/agallentes/.config/pctx/pctx.json`.
4. **setup.sh**: Added Codex and Windsurf symlink blocks (were missing).
5. **Codex sync**: `.codex/config.toml` synced from live.
6. **pctx permissions**: Added `mcp__pctx__list_functions` and `mcp__pctx__get_function_details` to `settings.local.json`.
7. **pre-tool-gate.sh**: Added Bash-native guard (cat/grep/find) and git-main guard.
8. **post-tool-handler.sh**: Added batching reminder after pctx calls.
9. **pctx-code-mode SKILL.md**: Complete rewrite — correct API, tool priority stack, batching decision rule, Serena camelCase table.
10. **mcp_config_manager**: Added Gemini dual-file validation checklist.
11. **CLAUDE.md**: Created at repo root with tool priority, batching, branch workflow, Serena convention, project structure.
12. **decisions.md**: Populated with ADL-001 through ADL-004.
13. **AGENT.md / GEMINI.md**: Created Codex instructions; updated Gemini instructions.

### Branch

All changes on `feat/pctx-agent-convergence` (stacked on main).

### Next After Merge

- Run `Serena.onboarding()` to populate `.serena/memories/` with project knowledge.
- Replace `pctx.json` at dotfiles root with symlink → `~/.config/pctx/pctx.json`.
- Apply live Codex symlink: `ln -sf ~/.dotfiles/.codex/config.toml ~/.codex/config.toml`.
