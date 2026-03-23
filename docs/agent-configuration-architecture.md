# Agent Configuration Architecture

This repository intentionally separates project guidance from dotfiles distribution.

## Two Domains

### 1. Dotfiles Distribution Layer

These files exist to install, configure, and enforce behavior for local tools:

- `setup.sh`
- `.claude/`
- `.gemini/`
- `.codex/`
- hooks, settings files, MCP wiring, and bootstrap scripts

This layer is the operational layer. It should contain as little duplicated policy text as possible.

### 2. Project Guidance Layer

These files exist to tell humans and agents how to work in this repository:

- `AGENTS.md`
- `CLAUDE.md`
- `docs/`
- `decisions/`
- `plans/`

This layer is the human-maintained source of truth for repo policy.

## Precedence Matrix

Apply guidance in this order:

1. Hard enforcement
2. Project guidance
3. User-global defaults
4. Agent-written memory

### Hard Enforcement

Examples:

- `.claude/settings.json`
- `.claude/hooks/*`
- `.gemini/settings.json`
- `.codex/config.toml`
- MCP gateway configuration

These are the only layers that can reliably enforce behavior.

### Project Guidance

This repository uses:

- `AGENTS.md` as the neutral project entrypoint
- `CLAUDE.md` as the Claude project adapter
- `decisions/` for durable architecture choices
- `plans/` for active-session artifacts

### User-Global Defaults

Machine-wide defaults live in `ai/rules/` and are loaded through tool-specific adapters:

| File | Scope | Loaded by |
|---|---|---|
| `agent-user-global.md` | All agents | Claude, Gemini, Codex |
| `tool-priority.md` | Claude, Gemini | Claude, Gemini (`@` imports) |
| `global-developer-guidelines.md` | Claude, Gemini | Claude, Gemini (`@` imports) |
| `context-and-compaction.md` | Claude only | Claude (`@` import) |

**Codex note**: Codex loads only `agent-user-global.md` via `model_instructions_file`. Tool priority and developer guidelines are a known gap for Codex in non-dotfiles projects.

### Agent Memory

Memory is helpful context. It is not the authoritative place to store repo policy.

## Tool Loading Model

### Claude Code

- User-global layer: `.claude/CLAUDE.md` — imports `agent-user-global.md`, `tool-priority.md`, `global-developer-guidelines.md`, `context-and-compaction.md`
- Project layer: `CLAUDE.md`
- Neutral project guide: `AGENTS.md`
- Enforcement: `.claude/settings.json` and `.claude/hooks/`

`CLAUDE.md` stays thin and imports `AGENTS.md`. Claude-specific details stay in Claude-owned files.

### Gemini CLI

- User-global layer: `.gemini/GEMINI.md` — imports `agent-user-global.md`, `tool-priority.md`, `global-developer-guidelines.md`
- Project discovery: `AGENTS.md` via `context.fileName`
- Enforcement and config: `.gemini/settings.json`, `.gemini/mcp.json`

`GEMINI.md` is the Gemini adapter, not the project-policy source of truth.

### Codex

- User-global layer: `model_instructions_file` in `.codex/config.toml` → `agent-user-global.md` only
- Project discovery: `AGENTS.md`
- MCP and runtime config: `.codex/config.toml`

The repo keeps `.codex/AGENT.md` only as a compatibility note, not as the primary policy document.

## Governance

- Canonical guidance files are human-maintained.
- Agents should not silently rewrite canonical policy files unless explicitly asked.
- Durable architecture changes should be recorded in `decisions/`.
- Validation scripts should check that the dotfiles layer still points to the intended guidance files.
