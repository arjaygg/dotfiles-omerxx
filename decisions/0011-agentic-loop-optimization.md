# Architecture Decision Record: Agentic Loop Optimization Plan

## Status

Completed for the bounded Codex proposal slice. Gate 1 and Gate 2 preflight passed, and the final
decision was to skip the semantically no-op canonical-byte live rewrite.

## Decision

Optimize the dotfiles AI control plane by preserving the existing shared-hub architecture while
moving machine-local runtime anchors out of tracked client configs through deterministic,
proposal-only generation.

The accepted first implementation slice is Codex-focused because current evidence shows
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

## Accepted staged implementation

1. Add TOML overlay support to the proposal generator.
2. Keep `ai/config/codex/config.base.toml` as the portable tracked base and use the official `[tui]`
   `status_line` setting rather than the obsolete top-level `[status_line]` table.
3. Move local Codex project, skill, marketplace, binary, and `pctx` path values into the ignored
   overlay convention.
4. Add deterministic comparison checks that report changed paths and hashes without printing local
   secrets or overlay contents.
5. Require a zero-changed-path base-plus-overlay comparison before any apply decision.
6. Stop before writing live `~/.codex/config.toml`; apply runtime changes only after separate user
   approval.
7. Before the final Gate 2 decision, preserve an exact private live backup and prove candidate
   parsing plus rollback without mutating live runtime state.

## Execution state (2026-07-15)

- The baseline/report, this ADR, and the bounded proposal-generator implementation and verification
  are complete on `feature/codex-config-proposals`.
- Gate 1 is complete. The portable base was corrected to official `[tui]` `status_line`; the
  official config reference and `codex features list` confirm the current schema and live parse.
- Gate 1 created the minimal ignored `~/.config/dotfiles-ai/codex.overlay.toml` with mode `0600`;
  no prior overlay existed.
- The final base-plus-overlay comparison against live `~/.codex/config.toml` reported zero changed
  paths. Both hashes were valid, while the proposal and target byte hashes differed because the
  proposal uses deterministic canonical rendering.
- The live `~/.codex/config.toml` SHA-256 remained unchanged, and the live config was not written.
- Gate 2 preflight created private backup directory
  `~/.config/dotfiles-ai/backups/20260715T002308Z-pre-codex-gate2` with mode `0700`. The exact live
  backup, generated candidate, manifest, and rollback instructions each have mode `0600`.
- The backup hash equals current live. The candidate byte hash differs, but semantic comparison
  reports zero changed paths.
- Candidate TOML parsing and an isolated `CODEX_HOME` Codex parse passed without changing the
  candidate.
- A sandbox rollback dry-run restored the candidate to the exact original-live hash.
- Live bytes, hash, and metadata remained unchanged; no runtime apply occurred.
- Final Gate 2 decision: skip the no-op canonical rewrite and close the bounded Codex slice. The
  semantic delta was zero, so no live runtime write occurred.
- Broader client migration remains separately scoped.
- The tracked `.codex/config.toml` and live `~/.codex/config.toml` were read-only comparison inputs
  and were not modified.

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
- A zero-changed-path comparison is a required Gate 2 precondition; differing byte hashes alone do
  not imply a semantic config delta when deterministic canonical rendering is used.
- With the precondition satisfied and rollback proven, skipping the byte-only rewrite avoids a
  needless live mutation while preserving an explicit apply option.

## Verification

Final staged acceptance evidence is recorded in
`plans/2026-07-14-agentic-loop-optimization.md`:

- The plan-defined focused command covering `test_config_manifest`,
  `test_portable_config_templates`, and `test_config_generate` passed 49 of 49 tests.
- Full `scripts/` discovery ran 85 tests with exactly one failure, caused only by the absent ignored
  `.claude/settings.local.json`. The full suite is not green.
- Read-only public hygiene reported 390 findings: 142 absolute-home-path, 197 private-org-name, and
  51 private-org-url.
- Read-only config doctor reported 65 issues: 6 errors and 59 warnings, comprising
  29 absolute-home-path, 6 blanket-permission-allow, and 30 private-org-name issues.
- The official Codex config reference and `codex features list` confirmed `[tui]` `status_line` as
  the current schema and confirmed the live config parses.
- The deterministic printable Codex proposal is valid TOML, repeated output is identical, and its
  SHA-256 is `bf13bdf914a7b28504e262183fd1a65182d560243e524efb44c94dbbdf7db280`.
- The minimal ignored overlay was created with mode `0600`, and no prior overlay existed.
- The actual Gate 1 base-plus-overlay comparison against live config reported zero changed paths
  and two valid hashes. The proposal and target byte hashes differed because of deterministic
  canonical rendering, not a semantic path delta.
- The live config SHA-256 remained unchanged across the comparison; no live write occurred.
- The pre-Gate-1 synthetic full-local-shape simulation used the existing tracked
  `.codex/config.toml` as both its local-shape overlay source and target. It reported five changed
  paths, exposed no local values, and produced two structurally valid 64-character hashes. It
  remains historical synthetic evidence and is superseded by the actual Gate 1 zero-path
  comparison.
- Independent final review found no remaining correctness- or security-significant code issue in the
  bounded scope.
- Gate 2 backup preflight created the private mode-`0700` directory
  `~/.config/dotfiles-ai/backups/20260715T002308Z-pre-codex-gate2`; the exact live backup, generated
  candidate, manifest, and rollback instructions are each mode `0600`.
- The backup hash matched current live; the candidate byte hash differed while semantic comparison
  reported zero changed paths.
- Candidate TOML and isolated `CODEX_HOME` Codex parsing passed, and the candidate remained
  unchanged.
- The sandbox rollback dry-run restored the candidate to the exact original-live hash.
- Final verification confirmed live bytes, hash, and metadata remained unchanged; no runtime apply
  occurred.

The final Gate 2 decision was to skip the no-op rewrite. No live runtime apply occurred.

## References

- `plans/2026-07-14-agentic-loop-optimization.md`
- `plans/2026-07-13-execution-plan.md`
- `decisions/0010-governed-read-only-validation.md`
- `docs/agent-configuration-architecture.md`
