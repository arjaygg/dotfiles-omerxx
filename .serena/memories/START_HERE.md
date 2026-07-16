# START_HERE

Read this first in any fresh session on this project (`.dotfiles`).

## What this repo is

A personal dotfiles repository for agallentes — not an application codebase. It manages macOS
tool config (shell, editors, window manager) and, most actively, unified AI-agent configuration
(Claude Code, Gemini CLI, Codex, Cursor, Windsurf) distributed via symlinks from `ai/` into each
agent's config directory. See `Serena.readMemory({ memory_name: "project_overview" })` for the
full tech-stack/key-files/key-directories rundown.

## Governance / precedence

Read `AGENTS.md` (repo root) first — it states the precedence order for this repo:
1. Hard enforcement — hooks, settings, denied tools, MCP config, wrappers
2. Project guidance — `AGENTS.md`, project docs, durable decisions
3. User-global agent defaults — `ai/rules/agent-user-global.md`
4. Agent-written memory (this file included) — never authoritative over the above

Tool selection, batching, and Serena/pctx quirks are fully specified in
`ai/rules/tool-priority.md` — read it before doing any file exploration or editing. Key points:
Serena first for code nav/edit, pctx `execute_typescript` to batch 2+ Serena/LeanCtx/Qmd/Repomix
calls, session-init (`mcp__pctx__list_functions` + `Serena.initialInstructions()` +
`LeanCtx.ctxCall({name:"ctx_intent",...})`) required once per session before Grep/Bash/source-Read
are unblocked by `pre-tool-gate-v2.sh`.

## goals / plans / decisions convention

- `goals/00-index.md` — table of numbered goals with Status (Proposed / In progress / Completed)
  and a one-line note. Each goal is a dated file `goals/YYYY-MM-DD-NN-<slug>.md` with Objective,
  Why, Current state, Non-goals, Steps, Acceptance criteria, Evidence to update, and a
  "Stop and ask if" section — treat that last section as real stop conditions, not decoration.
  A goal's index status of "Proposed... Awaiting user alignment" means implementation work needs
  explicit user scope confirmation before large/irreversible steps, even if a session-scoped Stop
  hook is actively pushing toward the goal condition.
- `plans/active-context.md` — current focus, most-recent session at the top; append, don't
  rewrite history. Read the top entry to resume; each entry usually links to a dated plan doc.
- `plans/progress.md` — checkbox-per-step milestone log, oldest-relevant-goal-first sections;
  check off as steps complete, append new dated sections rather than deleting old ones.
- `plans/decisions.md` — short session-friendly ADR-style entries (Decision/Why/Alternatives/
  Assumptions). Promote to a durable `decisions/NNNN-title.md` when cross-cutting or long-lived.
- `plans/<date>-<slug>.md` — per-initiative working plan/checklist docs; goal files point to these
  once execution starts.
- A goal's "Current state" section can go stale if other work lands after it's written — verify
  against the actual repo (git log, live files) rather than trusting it blindly before executing.

## Common gotchas already hit in this repo (don't re-discover)

- `Serena.readMemory({ memory_name: "START_HERE" })` used to fail (this file didn't exist) —
  flagged twice as a bootstrap gap before being created.
- `.gemini/mcp.json`, `.gemini/settings.json`, `.windsurf/mcp_config.json` are live symlinks into
  this dotfiles repo (editing the tracked file changes live behavior immediately — treat as a live
  runtime write). `.cursor/mcp.json` is NOT a symlink; it's a separate untracked-from-repo file.
- `ai/config/<client>/*.base.json|toml` + `ai/config/manifest.json` + `scripts/config_generate.py`
  is the portable-base-plus-ignored-overlay pattern (see `ai/config/README.md`). It only produces
  proposals/comparisons — it never writes a live runtime file. Codex's slice (Gate 1/2) is the
  reference example of the full propose→compare→approve flow for one client.
- The full `scripts/` test suite has historically had exactly one known, explained failure tied to
  the intentionally-gitignored `.claude/settings.local.json` fixture — check whether this is still
  true rather than assuming it, since it can be fixed or can drift.
