# Agent Guide

This repository is a dotfiles repository. Treat it as a configuration distribution system, not an application codebase.

## Repo Purpose

- User-scoped AI tool configuration lives here and is installed onto the machine via symlinks and `setup.sh`.
- Tool-specific config directories such as `.claude/`, `.gemini/`, and `.codex/` are the dotfiles distribution layer.
- Shared project guidance and architecture notes live in neutral docs such as this file, `docs/`, `decisions/`, and `plans/`.

## Precedence

When instructions conflict, apply this order:

1. Hard enforcement: hooks, settings, denied tools, MCP config, wrappers
2. Project guidance: `AGENTS.md`, project docs, durable decisions
3. User-global agent defaults: `ai/rules/agent-user-global.md`
4. Agent-written memory

Memory is never the source of truth for repo policy.

## Working Rules

- Keep shared repo policy in neutral files, not inside tool-specific config directories unless a tool needs a loader file.
- Keep user-global defaults in `ai/rules/agent-user-global.md`.
- Keep tool-specific entrypoints thin. They should load shared guidance and record tool quirks, not duplicate full policy blocks.
- Preserve symlink-based configuration management. If a live config changes, reflect it in the tracked dotfiles source.
- Use stack branches and worktrees for non-trivial changes. Do not commit directly to `main`.
- Update `decisions/` for durable architecture changes and `plans/` for active-session state when those artifacts are in use.

## Source Of Truth

- User-global defaults: `ai/rules/agent-user-global.md`
- Guidance architecture: `docs/agent-configuration-architecture.md`
- Durable decisions: `decisions/`
- Active session context: `plans/`
- Dotfiles installation and enforcement: `.claude/`, `.gemini/`, `.codex/`, `setup.sh`

---

## Tool Priority Stack

Always use tools in this order. Stop at the first that satisfies your need. **Never use Bash for operations that have a dedicated tool.**

```
DIRECTORY LISTING:
  1st: Serena.listDir           — gitignore-aware, project-scoped, recursive
  2nd: Glob                     — flexible patterns, fast
  ✗    Bash ls / find           — never; raw filesystem noise

SEARCHING CODE:
  1st: Serena.findSymbol        — LSP-backed, zero false positives from comments
  2nd: Serena.searchForPattern  — project-scoped, gitignore-aware, LSP context
  3rd: Grep tool                — flexible regex, ripgrep-backed, gitignore-aware
  ✗    Bash grep/rg             — never; no gitignore, 8× slower, token waste

FINDING FILES:
  1st: Serena.findFile          — LSP-aware, project-scoped
  2nd: Glob                     — pattern-based, fast
  ✗    Bash find                — never; no project awareness

READING FILES (stop as soon as you have what you need):
  1st: Serena.getSymbolsOverview    — understand structure WITHOUT reading file
  2nd: Grep / Serena.searchForPattern — find the specific section first
  3rd: Read (with limit/offset)     — targeted read once you know the location
  4th: Read (full file)             — only when entire content is truly needed
  ✗    Bash cat/head/tail           — never; use Read tool

CODE EDITING:
  1st: Serena.replaceSymbolBody / insertAfterSymbol — symbol-aware, precise
  2nd: Edit tool                    — line-based when symbol bounds are unknown
  ✗    Bash sed/awk                 — never for code edits

BATCH / MULTI-STEP:
  1st: pctx execute_typescript      — combine multiple Serena ops in ONE call
  ✗    Multiple sequential calls    — always check if batchable first
```

---

## Batching Rule

> **Before any tool call that accesses the project, ask: "What else will I need in the next 3 steps?"**
> - If 2+ Serena operations are planned → write ONE `execute_typescript`.
> - If 2+ Read/Grep/Glob ops are independent → fire them in **parallel** (single message, multiple tool calls).
> - Never make a sequential Serena call when a batch would work.

---

## Branch Workflow

**Never commit directly to `main`.** Always use the stack workflow:

```bash
# Create feature branch (use stack-create skill)
$HOME/.dotfiles/.claude/scripts/stack create <branch-name> main

# Make changes, then commit on the feature branch
git add <files>
git commit -m "..."

# Create PR when ready
# Use stack-pr skill
```

The `pre-tool-gate.sh` hook will warn you if you attempt `git commit` on `main`.

---

## Serena API Convention

All Serena methods use **camelCase**. Call `mcp__pctx__list_functions` at the start of a new session to confirm current signatures.

| ✅ camelCase (correct) | ✗ snake_case (WRONG) |
|---|---|
| `Serena.listDir(...)` | ~~`Serena.list_dir`~~ |
| `Serena.searchForPattern(...)` | ~~`Serena.search_for_pattern`~~ |
| `Serena.findFile(...)` | ~~`Serena.find_file`~~ |
| `Serena.findSymbol(...)` | ~~`Serena.find_symbol`~~ |
| `Serena.getSymbolsOverview(...)` | ~~`Serena.get_symbols_overview`~~ |
| `Serena.listMemories()` | ~~`Serena.list_memories`~~ |
| `Serena.initialInstructions()` | ~~`Serena.initial_instructions`~~ |

---

## Project Structure

```
~/.dotfiles/
├── CLAUDE.md              ← this file (read every session)
├── AGENTS.md              ← project guidance (read by all agents)
├── .mcp.json              ← Claude Code MCP: pctx gateway only
├── .claude/
│   ├── settings.json      ← Claude Code user settings
│   ├── settings.local.json← local permissions (gitignored)
│   ├── hooks/             ← PreToolUse / PostToolUse / UserPromptSubmit hooks
│   ├── agents/            ← subagent definitions (mcp_config_manager, etc.)
│   └── skills/            ← symlinks → ai/skills/
├── ai/
│   └── skills/            ← all skill definitions (source of truth)
├── .cursor/mcp.json       ← Cursor MCP: pctx gateway only
├── .windsurf/mcp_config.json ← Windsurf MCP: pctx gateway only
├── .gemini/
│   ├── mcp.json           ← Gemini MCP: pctx gateway only
│   └── settings.json      ← Gemini settings: also pctx gateway only
├── .codex/config.toml     ← Codex: pctx mcp_servers section
├── plans/
│   ├── active-context.md  ← current focus (keep updated)
│   ├── decisions.md       ← concise decision log for active work
│   └── progress.md        ← milestone tracking
├── decisions/             ← durable human-facing decision records
├── docs/
│   └── decision-records.md← canonical decision-doc convention
└── setup.sh               ← creates all symlinks (run on fresh machine)
```

All agent configs (`~/.cursor/mcp.json`, `~/.gemini/*`, `~/.codex/config.toml`, `~/.windsurf/mcp_config.json`, `~/.claude/settings.json`) are symlinks into this dotfiles repo.

---

## MCP Gateway

All MCP traffic routes through `pctx`:
- **Gateway config:** `/Users/agallentes/.config/pctx/pctx.json`
- **Servers:** serena, exa, sequential-thinking, notebooklm, markitdown
- **Serena context:** `--context claude-code` (19 of 43 tools — LSP intelligence only, no file mutation)

---

## plans/ Directory

Keep these files current:
- **`active-context.md`**: Current work focus. Update when focus shifts.
- **`decisions.md`**: Concise ADL log for active work. Append when decisions are made; link to `decisions/` when a durable record exists.
- **`progress.md`**: Milestone tracking. Update when milestones are completed.

Decision-document rules:
- Use **`plans/decisions.md`** for short, session-friendly decision entries.
- Use **`decisions/NNNN-title.md`** for durable rationale, alternatives, and migration notes.
- Promote decisions to a durable record when they are cross-cutting, long-lived, or likely to be revisited.
- Canonical convention: `docs/decision-records.md`
