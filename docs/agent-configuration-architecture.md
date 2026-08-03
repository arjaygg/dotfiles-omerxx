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
| `agent-user-global.md` | Supported coding agents | Claude, Codex, Cursor, AGY/Antigravity |
| `tool-priority.md` | Supported coding agents | The four in-scope client adapters (`@` imports) |
| `context-and-compaction.md` | Supported coding agents | The four in-scope client adapters (`@` imports, exactly once) |

Codex installs `.codex/AGENTS.md` as its user adapter in addition to the compact `model_instructions_file`. Windsurf and other coding clients are outside the current hardening scope.

### Agent Memory

Memory is helpful context. It is not the authoritative place to store repo policy.

## Skill Distribution

User-scoped skills live in `ai/skills/` (canonical source). Distribution to agent runtimes is:

| Path | Who reads it | Notes |
|---|---|---|
| `~/.agents/skills` → `~/.dotfiles/ai/skills` | Codex ≥ 0.130.0, Gemini ≥ 0.42.0 | Single symlink; cross-tool standard |
| `~/.codex/skills/` | Codex < 0.130.0 | Populated per-skill by `setup.sh`; legacy |
| `~/.claude/skills/` | Claude Code | Relative symlinks → `ai/skills/` per skill |
| `~/.cursor/skills/` | Cursor | Explicit subset (manual list in `setup.sh`) |

`setup.sh` creates `~/.agents/skills` and maintains the legacy Codex path in parallel.
See `decisions/0006-agents-skills-standard-path.md` for rationale.

## Tool Loading Model

### Claude Code

- User-global layer: `.claude/CLAUDE.md` — imports `agent-user-global.md`, `tool-priority.md`, `context-and-compaction.md`, and `hyper-atomic-commits.md`
- `qmd-usage.md` and `monitor-patterns.md` were retired (2026-07): both were thin pointers to skills (`qmd-routing`, `monitor-patterns`) with no unique content — their pointer facts were folded into `agent-user-global.md` and `tool-priority.md` directly, and the rule files were deleted rather than wired in.
- `pctx-session-init.md` was retired the same pass: its "why each step matters" content was merged into `tool-priority.md` §6 (Session Start), which already carried the enforcement note. (The gateway it was named for was itself removed on 2026-08-03 — see `decisions/0017-remove-pctx-gateway.md`.)
- `kubectl-efficiency.md` was converted to a skill (`ai/skills/kubectl-efficiency/SKILL.md`) since it's invoked situationally (writing kubectl commands), not always-relevant baseline policy.
- `chrome-mcp-efficiency.md` (new, 2026-07) was authored as a skill from the start (`ai/skills/chrome-mcp-efficiency/SKILL.md`), not wired into `.claude/CLAUDE.md`, for the same reason as `kubectl-efficiency.md` — browser automation is situational, not every session's baseline policy. Enforcement (the PreToolUse guard) is independent of this and always active regardless of whether the skill doc is loaded.
- Project layer: `CLAUDE.md`
- Neutral project guide: `AGENTS.md`
- Enforcement: `.claude/settings.json` and `.claude/hooks/`

`CLAUDE.md` stays thin and imports `AGENTS.md`. Claude-specific details stay in Claude-owned files.

### Gemini CLI

- User-global layer: `.gemini/GEMINI.md` — imports `agent-user-global.md`, `tool-priority.md`, and `context-and-compaction.md`
- Project discovery: `AGENTS.md` via `context.fileName`
- Enforcement and config: `.gemini/settings.json`, `.gemini/mcp.json`

`GEMINI.md` is the Gemini adapter, not the project-policy source of truth.

### Codex

- User-global layer: `model_instructions_file` in `.codex/config.toml` → `agent-user-global.md` only
- Project discovery: `AGENTS.md`
- MCP and runtime config: `.codex/config.toml`

`.codex/AGENT.md` (singular) was removed 2026-08-03. Codex 0.146.0 recognises only `AGENTS.md` —
the shipped binary contains no singular form, and `project_doc_fallback_filenames` is `["AGENTS.md"]` —
so the file was a compatibility note for a filename no Codex version reads.

## Governance

- Canonical guidance files are human-maintained.
- Agents should not silently rewrite canonical policy files unless explicitly asked.
- Durable architecture changes should be recorded in `decisions/`.
- Validation scripts should check that the dotfiles layer still points to the intended guidance files.
