# Goal 01 — Agentic Loop Optimization Baseline

## Goal

Audit and optimize the dotfiles AI control plane so it stays safer, deterministic, portable,
maintainable, context-efficient, and cross-client consistent without silently rewriting policy.

## Verified current state

- Repository guidance still separates policy (`AGENTS.md`, `CLAUDE.md`, `docs/`, `decisions/`,
  `plans/`) from dotfiles distribution (`.claude/`, `.codex/`, `.gemini/`, `.cursor/`,
  `.windsurf/`, `setup.sh`).
- Session-init baseline is loaded:
  - `mcp__pctx__list_functions` returned Serena, Qmd, LeanCtx, Repomix, and Graphify.
  - `Serena.initialInstructions()` succeeded.
  - `Serena.checkOnboardingPerformed()` errored, so onboarding status is not freshly confirmed.
  - `Serena.readMemory({ memory_name: "START_HERE" })` failed because that memory does not exist.
- `goals/2026-07-14-01-agentic-loop-optimization.md` exists as the active goal prompt, but it is
  still untracked; `plans/` remains the tracked handoff surface.
- Tracked client configs are present and writable in the repo; the following are tracked and
  exist as regular files, not symlinks:
  - `.claude/settings.json`
  - `.codex/config.toml`
  - `.gemini/settings.json`
  - `.gemini/mcp.json`
  - `.cursor/mcp.json`
  - `.windsurf/mcp_config.json`
  - `setup.sh`
- Exact marker check from the live files:
  - `.claude/settings.json` does **not** contain `/Users/axos-agallentes`, `dangerously-skip-permissions`,
    `skipDangerousModePermissionPrompt`, `pctx.json`, or `settings-symlink-guard`.
  - `.codex/config.toml`, `.gemini/settings.json`, `.gemini/mcp.json`, `.cursor/mcp.json`, and
    `.windsurf/mcp_config.json` do contain `/Users/axos-agallentes` and `pctx.json`.
  - `setup.sh` does not contain `/Users/axos-agallentes`, `dangerously-skip-permissions`,
    `skipDangerousModePermissionPrompt`, `pctx.json`, or `settings-symlink-guard`.
- Architecture docs read this session confirm the intended layering:
  - `AGENTS.md` = neutral repository policy entrypoint
  - `CLAUDE.md` = thin Claude adapter importing `AGENTS.md`
  - `ai/rules/tool-priority.md` = shared tool-priority policy
  - `docs/agent-configuration-architecture.md` = layer separation and distribution model

## Cross-client parity matrix

| Client | Tracked entrypoint(s) | Shared rules / policy loading | MCP / tooling surface | Current drift / note |
|---|---|---|---|---|
| Claude | `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks/` | `CLAUDE.md` imports `AGENTS.md`; `.claude/settings.json` carries hooks, permissions, and `skillOverrides` | 14 hooks; 46 allows; 49 denies; default permission mode `acceptEdits`; 104 skill overrides set to `off` | Strongest enforcement layer; no tested home-path or bypass marker found in live Claude settings |
| Codex | `.codex/config.toml` | `model_instructions_file = "~/.dotfiles/ai/rules/agent-user-global.md"` | `lean-ctx` and `pctx`; skill list points at `ai/skills/` plus a few local/system skills | Most machine-local references: project paths, `pctx.json`, skill paths, and config paths are absolute |
| Gemini / Antigravity | `.gemini/settings.json`, `.gemini/mcp.json` | Uses `pctx` gateway only; project guidance comes from repo docs, not a separate hook layer | `pctx` only | Live config still embeds `/Users/axos-agallentes/.config/pctx/pctx.json` |
| Cursor | `.cursor/mcp.json` | Uses `pctx` gateway only | `pctx` only | Live config still embeds `/Users/axos-agallentes/.config/pctx/pctx.json` |
| Windsurf | `.windsurf/mcp_config.json` | Uses `pctx` gateway plus LeanCtx env | `lean-ctx` and `pctx` | Live config still embeds `/Users/axos-agallentes/.lean-ctx` and `/Users/axos-agallentes/.config/pctx/pctx.json` |

Shared across clients:
- `AGENTS.md` defines the repo policy entrypoint and stack/worktree convention.
- `ai/rules/tool-priority.md` defines shared tool routing and batching rules.
- `setup.sh` is the tracked distribution/bootstrap path for the symlinked runtime layout.

## File-level harness map

| Layer | Files | Purpose |
|---|---|---|
| Neutral repo policy | `AGENTS.md`, `docs/agent-configuration-architecture.md` | Defines the repository as a configuration distribution system and documents the layer boundaries |
| Claude adapter / enforcement | `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks/` | Thin Claude adapter plus the strongest local enforcement layer (hooks, permissions, skill overrides) |
| Shared tool policy | `ai/rules/tool-priority.md` | Central tool-selection, batching, and Serena/LeanCtx/Qmd routing rules |
| Codex runtime config | `.codex/config.toml` | Codex-specific model instructions, skill paths, marketplace config, and MCP gateway wiring |
| Gemini runtime config | `.gemini/settings.json`, `.gemini/mcp.json` | Gemini runtime settings and pctx gateway wiring |
| Cursor runtime config | `.cursor/mcp.json` | Cursor MCP gateway wiring |
| Windsurf runtime config | `.windsurf/mcp_config.json` | Windsurf MCP wiring plus LeanCtx environment setup |
| Bootstrap / install | `setup.sh` | Creates the symlinked runtime layout and installs the tracked distribution |
| Active session state | `plans/active-context.md`, `plans/progress.md`, `plans/decisions.md`, `plans/pctx-functions.md`, `plans/2026-07-14-agentic-loop-optimization.md` | Human-visible handoff trail for the current goal |
| Goal prompt | `goals/2026-07-14-01-agentic-loop-optimization.md` | Active goal source, currently untracked |

## Recommendations

1. Move machine-local path anchors out of tracked client configs into ignored overlays or generator
   inputs, starting with Codex because it has the densest absolute-path surface.
2. Keep Claude’s permission/hook surface as the primary enforcement layer, but continue verifying that
   the config stays free of bypass flags and machine-local runtime anchors.
3. Preserve `AGENTS.md`/`CLAUDE.md`/`ai/rules/tool-priority.md` as the shared source of truth, and keep
   client entrypoints thin so only the runtime-specific wiring remains in `.claude/`, `.codex/`,
   `.gemini/`, `.cursor/`, and `.windsurf/`.
4. Treat `goals/2026-07-14-01-agentic-loop-optimization.md` as an untracked coordination artifact until
   the goal convention is finalized; do not let it become an alternate policy source.

## Files in scope

- `AGENTS.md`
- `CLAUDE.md`
- `docs/agent-configuration-architecture.md`
- `ai/rules/tool-priority.md`
- `plans/active-context.md`
- `plans/progress.md`
- `plans/decisions.md`
- `plans/pctx-functions.md`
- `goals/2026-07-14-01-agentic-loop-optimization.md`
- `.claude/settings.json`
- `.codex/config.toml`
- `.gemini/settings.json`
- `.gemini/mcp.json`
- `.cursor/mcp.json`
- `.windsurf/mcp_config.json`
- `setup.sh`

## Changes made

- Refreshed `plans/active-context.md` with the resumed goal and session-init baseline.
- Added a new active section to `plans/progress.md` for the agentic-loop optimization work.
- Added a current decision note to `plans/decisions.md` to keep the session audit trail current.
- Refreshed `plans/pctx-functions.md` for the current day and session-init evidence.

## Tests executed

- `mcp__pctx__list_functions`
- `Serena.initialInstructions()`
- `Serena.checkOnboardingPerformed()` → error
- `Serena.readMemory({ memory_name: "START_HERE" })` → error
- `LeanCtx.ctxOverview({ path: "/Users/axos-agallentes/.dotfiles", task: "audit goal for dotfiles agentic loop optimization" })`
- `LeanCtx.ctxCall({ name: "ctx_intent", arguments: { query: "audit goal for dotfiles agentic loop optimization" } })`
- `LeanCtx.ctxShell(...)` marker checks for tracked config files and `setup.sh`
- `git ls-files --error-unmatch` checks for tracked-file status

## Results

- The session-init surface is available and documented.
- The active goal prompt exists, but still lives in an untracked `goals/` artifact.
- The tracked cross-client configs are not yet portable in the broad sense: Codex, Gemini, Cursor,
  and Windsurf still embed the local home path and/or runtime routing details.
- `setup.sh` is clean of the tested home-path and bypass markers.

## Residual risks

- The runtime configs under `.codex/`, `.gemini/`, `.cursor/`, and `.windsurf/` still carry
  machine-specific absolute paths.
- The baseline report is still audit-only; no live runtime changes have been proposed or applied.
- `START_HERE` memory is absent, so future sessions cannot rely on it for project bootstrap.

## Next recommended step

Draft a concrete remediation plan that moves machine-local anchors out of tracked client configs,
starting with Codex because it has the densest absolute-path surface.
