# 0003 — Universal Constitution Loading from ai/rules/

**Date:** 2026-03-23
**Status:** Accepted

## Context

The dotfiles repo is the single source of truth for AI agent constitution files. Previously, the Tool Priority Stack (Serena > native tools > Bash), Batching Rule, and Serena API Convention were defined only in `AGENTS.md`, making them visible solely when agents worked inside the dotfiles project. `context-and-compaction.md` and `global-developer-guidelines.md` existed in `ai/rules/` but were not imported by any user-global adapter.

## Decision

Move all universal agent rules to `ai/rules/` and load them at user scope:

1. **Create `ai/rules/tool-priority.md`** — canonical source for tool priority stack, batching rule, and Serena API convention (extracted from `AGENTS.md`).

2. **Update `~/.claude/CLAUDE.md`** (`.claude/CLAUDE.md`) — `@`-import all four rules files:
   - `agent-user-global.md` (working style, git safety, file discipline)
   - `tool-priority.md` (Serena tool priority, batching, API convention)
   - `global-developer-guidelines.md` (worktree conventions, AI hub structure)
   - `context-and-compaction.md` (session discipline, Claude hook behavior)

3. **Update `~/.gemini/GEMINI.md`** (`.gemini/GEMINI.md`) — `@`-import three of the four rules files (excluding `context-and-compaction.md` which is Claude hook-specific).

4. **Trim `AGENTS.md`** — remove tool priority, batching, and Serena convention sections; replace with a one-line reference to `ai/rules/tool-priority.md`.

## Rationale

- All projects on this machine use pctx/Serena (configured via dotfiles MCP configs), so the tool priority rules apply universally.
- `@`-import is the cleanest loading mechanism: zero duplication, no generated files, no staleness risk.
- Keeping the rules in `ai/rules/` (not inside tool-specific config directories) preserves the two-domain separation from ADL-002.

## Known Gaps

- **Codex**: `model_instructions_file` supports only a single file. Codex continues to load `agent-user-global.md` only. Tool priority and developer guidelines are not loaded user-globally for Codex. Options for a future PR: generate an `agent-universal.md` combined file (with a pre-commit hook to keep it fresh), or investigate if Codex supports chained instruction files.
- **Cursor / Windsurf**: `~/.cursorrules` / `~/.windsurfrules` scope for user-global loading is unverified. Investigation deferred.

## Alternatives Considered

- **Append tool priority content into `agent-user-global.md`**: Avoided duplication concerns when Claude `@`-imports both files. Kept `agent-user-global.md` focused on general rules.
- **Generate a combined file for all single-file agents**: Clean architecture but introduces a build artifact that can go stale. Deferred until Codex gap becomes a real pain point.

## Consequences

- `validate-agent-guidance.sh` updated with 7 new checks (file existence + import chain for Claude and Gemini).
- `AGENTS.md` is now leaner and dotfiles-specific. Tool priority rules are no longer duplicated between AGENTS.md and user-global adapters.
- Any new universal rule should be added to `ai/rules/` and referenced from `.claude/CLAUDE.md` and `.gemini/GEMINI.md`.
