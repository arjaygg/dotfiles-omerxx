# Architecture Decision Record: Agentic Loop Optimization Plan

## Status

Proposed — implementation requires explicit user approval.

## Decision

Optimize the dotfiles AI control plane by preserving the existing shared-hub architecture while
moving machine-local runtime anchors out of tracked client configs through deterministic,
proposal-only generation.

The first approved implementation slice should be Codex-focused because current evidence shows
`.codex/config.toml` has the densest machine-local surface: project allowlists, skill paths,
marketplace/cache paths, local MCP config paths, and local binary paths.

## Why

The repository is intentionally a multi-client AI configuration distribution system:

- shared source of truth lives under `ai/`;
- neutral repo policy lives in `AGENTS.md`, `docs/`, `decisions/`, and `plans/`;
- client directories (`.claude/`, `.codex/`, `.gemini/`, `.cursor/`, `.windsurf/`) are runtime
  integration layers;
- hooks and settings provide enforcement;
- plans and decisions provide human-readable continuity.

The verified baseline in `plans/2026-07-14-agentic-loop-optimization.md` shows this architecture is
still valid, but the tracked client configs are uneven:

- Claude settings no longer contain the tested bypass markers or local home-path anchors.
- Codex, Gemini, Cursor, and Windsurf still contain machine-local absolute paths.
- Codex contains the broadest mix of local project state and runtime wiring in tracked source.

## Proposed implementation

1. Add TOML overlay support to the proposal generator.
2. Keep `ai/config/codex/config.base.toml` as the portable tracked base.
3. Move local Codex project, skill, marketplace, binary, and `pctx` path values into the ignored
   overlay convention.
4. Add deterministic comparison checks that report changed paths and hashes without printing local
   secrets or overlay contents.
5. Stop before writing live `~/.codex/config.toml`; apply runtime changes only after separate user
   approval.

## Alternatives rejected

- **Edit `.codex/config.toml` directly in-place.** Rejected because it preserves tracked runtime
  drift and weakens the base-plus-overlay architecture.
- **Move all clients at once.** Rejected because Codex has enough distinct TOML/generator work to
  deserve a focused, reviewable slice.
- **Duplicate shared policy into each client config.** Rejected because repository policy requires
  thin client entrypoints and shared source under `ai/`.
- **Automatically update live runtime config.** Rejected because the goal and existing Phase 0 plan
  require proposal review and explicit approval before live runtime changes.

## Consequences

- Codex portability improves first without weakening Claude enforcement.
- The generator becomes capable of handling both JSON and TOML client templates.
- Runtime-local details remain available to this machine through ignored overlays.
- Reviewers get deterministic evidence before any live config update.

## Verification

Before implementation is accepted, evidence should include:

- `python3 -m unittest scripts.test_config_manifest scripts.test_portable_config_templates scripts.test_config_generate`
- `python3 scripts/public_hygiene_check.py`
- `python3 scripts/config_doctor.py`
- repeated Codex proposal generation with identical output/hash from unchanged inputs;
- a clean tracked diff after repeated proposal-only generation.

## References

- `plans/2026-07-14-agentic-loop-optimization.md`
- `plans/2026-07-13-execution-plan.md`
- `decisions/0010-governed-read-only-validation.md`
- `docs/agent-configuration-architecture.md`
