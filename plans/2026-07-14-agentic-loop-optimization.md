****# Goal 01 — Agentic Loop Optimization Baseline

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
- `goals/2026-07-14-01-agentic-loop-optimization.md` is the tracked active goal prompt;
  `goals/` and `plans/` provide the current handoff surface.
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

| Client               | Tracked entrypoint(s)                                  | Shared rules / policy loading                                                                             | MCP / tooling surface                                                                                   | Current drift / note                                                                                            |
| -------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Claude               | `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks/` | `CLAUDE.md` imports `AGENTS.md`; `.claude/settings.json` carries hooks, permissions, and `skillOverrides` | 14 hooks; 46 allows; 49 denies; default permission mode `acceptEdits`; 104 skill overrides set to `off` | Strongest enforcement layer; no tested home-path or bypass marker found in live Claude settings                 |
| Codex                | `.codex/config.toml`                                   | `model_instructions_file = "~/.dotfiles/ai/rules/agent-user-global.md"`                                   | `lean-ctx` and `pctx`; skill list points at `ai/skills/` plus a few local/system skills                 | Most machine-local references: project paths, `pctx.json`, skill paths, and config paths are absolute           |
| Gemini / Antigravity | `.gemini/settings.json`, `.gemini/mcp.json`            | Uses `pctx` gateway only; project guidance comes from repo docs, not a separate hook layer                | `pctx` only                                                                                             | Live config still embeds `/Users/axos-agallentes/.config/pctx/pctx.json`                                        |
| Cursor               | `.cursor/mcp.json`                                     | Uses `pctx` gateway only                                                                                  | `pctx` only                                                                                             | Live config still embeds `/Users/axos-agallentes/.config/pctx/pctx.json`                                        |
| Windsurf             | `.windsurf/mcp_config.json`                            | Uses `pctx` gateway plus LeanCtx env                                                                      | `lean-ctx` and `pctx`                                                                                   | Live config still embeds `/Users/axos-agallentes/.lean-ctx` and `/Users/axos-agallentes/.config/pctx/pctx.json` |

Shared across clients:
- `AGENTS.md` defines the repo policy entrypoint and stack/worktree convention.
- `ai/rules/tool-priority.md` defines shared tool routing and batching rules.
- `setup.sh` is the tracked distribution/bootstrap path for the symlinked runtime layout.

## File-level harness map

| Layer                        | Files                                                                                                                                            | Purpose                                                                                              |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| Neutral repo policy          | `AGENTS.md`, `docs/agent-configuration-architecture.md`                                                                                          | Defines the repository as a configuration distribution system and documents the layer boundaries     |
| Claude adapter / enforcement | `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks/`                                                                                           | Thin Claude adapter plus the strongest local enforcement layer (hooks, permissions, skill overrides) |
| Shared tool policy           | `ai/rules/tool-priority.md`                                                                                                                      | Central tool-selection, batching, and Serena/LeanCtx/Qmd routing rules                               |
| Codex runtime config         | `.codex/config.toml`                                                                                                                             | Codex-specific model instructions, skill paths, marketplace config, and MCP gateway wiring           |
| Gemini runtime config        | `.gemini/settings.json`, `.gemini/mcp.json`                                                                                                      | Gemini runtime settings and pctx gateway wiring                                                      |
| Cursor runtime config        | `.cursor/mcp.json`                                                                                                                               | Cursor MCP gateway wiring                                                                            |
| Windsurf runtime config      | `.windsurf/mcp_config.json`                                                                                                                      | Windsurf MCP wiring plus LeanCtx environment setup                                                   |
| Bootstrap / install          | `setup.sh`                                                                                                                                       | Creates the symlinked runtime layout and installs the tracked distribution                           |
| Active session state         | `plans/active-context.md`, `plans/progress.md`, `plans/decisions.md`, `plans/pctx-functions.md`, `plans/2026-07-14-agentic-loop-optimization.md` | Human-visible handoff trail for the current goal                                                     |
| Goal prompt                  | `goals/2026-07-14-01-agentic-loop-optimization.md`                                                                                               | Tracked active goal source                                                                           |

## Recommendations

1. Move machine-local path anchors out of tracked client configs into ignored overlays or generator
   inputs, starting with Codex because it has the densest absolute-path surface.
2. Keep Claude’s permission/hook surface as the primary enforcement layer, but continue verifying that
   the config stays free of bypass flags and machine-local runtime anchors.
3. Preserve `AGENTS.md`/`CLAUDE.md`/`ai/rules/tool-priority.md` as the shared source of truth, and keep
   client entrypoints thin so only the runtime-specific wiring remains in `.claude/`, `.codex/`,
   `.gemini/`, `.cursor/`, and `.windsurf/`.
4. Treat `goals/2026-07-14-01-agentic-loop-optimization.md` as a tracked coordination artifact, not
   an alternate policy source.


## Approval-ready implementation checklist

This section records the exact bounded proposal-generator scope that was approved and completed
through the final Gate 2 skip decision. No live runtime write was performed.

### Step 1 — Add TOML overlay rendering

**Files:** `scripts/config_generate.py`, `scripts/test_config_generate.py`

**Accepts:** JSON behavior remains unchanged; TOML base + TOML overlay can render a proposal without
reading process environment variables, mutating inputs, or printing local overlay contents.

- [x] Teach the generator to parse and emit TOML when the base template is TOML.
- [x] Add TOML overlay merge coverage.
- [x] Keep explicit `--set NAME=VALUE` placeholder expansion as the only variable source.

### Step 2 — Make Codex proposal generation complete

**Files:** `ai/config/codex/config.base.toml`, `ai/config/manifest.json`,
`scripts/test_portable_config_templates.py`, `scripts/test_config_manifest.py`

**Accepts:** the tracked Codex base remains portable; the manifest references the Codex base/runtime
and ignored overlay; tests prove the Codex proposal can be generated from portable source plus
explicit local values.

- [x] Verify the current Codex base contains only shared portable defaults.
- [x] Add or adjust tests so Codex generation is covered as TOML, not treated like JSON.
- [x] Keep local project allowlists, local skill paths, marketplace cache paths, and local binary
  paths out of tracked base config.
- [x] Correct the obsolete top-level `[status_line]` table to the official `[tui]` `status_line`
  setting, confirmed by the official config reference and `codex features list`.

### Step 3 — Define the local-only Codex overlay convention

**Files:** `.gitignore`, `ai/config/README.md`, optionally an example overlay under
`ai/config/codex/`

**Accepts:** local Codex-only paths have a documented ignored overlay location, and any tracked
example uses placeholders or fake portable paths only.

- [x] Document `~/.config/dotfiles-ai/codex.overlay.toml`.
- [x] Ensure the overlay path is ignored.
- [x] Provide a non-sensitive example if useful.
- [x] Complete Gate 1 by creating the minimal ignored overlay with mode `0600`; no prior overlay
  existed.

### Step 4 — Add deterministic proposal comparison evidence

**Files:** `scripts/config_generate.py`, `scripts/test_config_generate.py`

**Accepts:** comparison reports changed paths and hashes without exposing raw local values; repeated
generation with unchanged inputs is idempotent.

- [x] Extend comparison support to TOML proposal outputs.
- [x] Add an idempotency assertion for repeated Codex proposal generation.
- [x] Keep printable output strict about local paths; allow compare-only local context solely for
  redacted evidence, while rejecting secrets and private keys in every mode.

### Step 5 — Stop before live runtime apply

**Files:** none unless separately approved.

**Accepts:** no write to `~/.codex/config.toml` or other live runtime config occurs automatically.
The user receives proposal evidence and explicitly approves any runtime update.

- [x] Run the verification gates.
- [x] Summarize proposal deltas without printing sensitive overlay values.
- [x] Ask for separate live-runtime approval.

## Final proposal-slice and Gate 1 verification (2026-07-15)

- The bounded proposal-generator slice is complete on `feature/codex-config-proposals`.
- The portable Codex base was corrected from the obsolete top-level `[status_line]` table to the
  official `[tui]` `status_line` setting. The official config reference and `codex features list`
  confirm the current schema and live parse.
- TOML round-trip handling supports real Codex shapes, including arrays of tables and quoted dotted
  keys.
- Direct proposal output remains portable and strict.
- Compare-only mode can process machine-local path and work context to compute evidence while
  redacting sensitive mapping keys and emitting only redacted paths and hashes. Secrets and private
  keys remain rejected.
- The deterministic printable Codex proposal is valid TOML, repeated output is identical, and its
  SHA-256 is `bf13bdf914a7b28504e262183fd1a65182d560243e524efb44c94dbbdf7db280`.
- Gate 1 created the minimal ignored `~/.config/dotfiles-ai/codex.overlay.toml` with mode `0600`;
  no prior overlay existed.
- The final base-plus-overlay comparison against live `~/.codex/config.toml` reported zero changed
  paths. Both hashes were valid, but the proposal and target byte hashes differed because the
  proposal uses deterministic canonical rendering.
- The live `~/.codex/config.toml` SHA-256 remained unchanged across Gate 1, and the live config was
  not written.
- The plan-defined focused command covering `test_config_manifest`,
  `test_portable_config_templates`, and `test_config_generate` passed 49 of 49 tests.
- Full `scripts/` discovery ran 85 tests with exactly one failure, caused only by the absent ignored
  `.claude/settings.local.json`. The full suite is not green.
- The read-only public hygiene summary reported 390 findings: 142 absolute-home-path,
  197 private-org-name, and 51 private-org-url.
- The read-only config doctor summary reported 65 issues: 6 errors and 59 warnings, comprising
  29 absolute-home-path, 6 blanket-permission-allow, and 30 private-org-name issues.
- The pre-Gate-1 synthetic full-local-shape simulation used the existing tracked
  `.codex/config.toml` as both its local-shape overlay source and target. It reported exactly five
  changed paths, exposed no local values, and produced two structurally valid 64-character hashes.
  This remains historical synthetic evidence and is superseded by the actual Gate 1 zero-path
  comparison.
- Independent final review found no remaining correctness- or security-significant code issue in the
  bounded scope.
- Gate 1, Gate 2 preflight, and the final Gate 2 decision are complete. The final decision was to
  skip the semantically no-op canonical rewrite; no live runtime write occurred.

## Gate 2 preflight verification (2026-07-15)

- Private backup directory
  `~/.config/dotfiles-ai/backups/20260715T002308Z-pre-codex-gate2` has mode `0700`.
- The exact live backup, generated candidate, manifest, and rollback instructions each have mode
  `0600`.
- The backup hash equals the current live hash. The candidate byte hash differs, while the semantic
  changed-path count is zero.
- The candidate TOML parsed successfully, an isolated `CODEX_HOME` Codex parse passed, and the
  candidate remained unchanged.
- A sandbox rollback dry-run restored the candidate to the exact original-live hash.
- Live bytes, hash, and metadata remained unchanged; no runtime apply occurred.
- Because the semantic delta is zero and only deterministic canonical formatting differs, the final
  Gate 2 decision is to skip the no-op live rewrite and close the bounded Codex slice.
- The private backup and generated candidate are retained in the private backup directory; no live
  runtime write occurred.

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
- Implemented the proposal generator and deterministic TOML serializer, including real Codex
  structures and placeholder expansion in mapping keys.
- Added compare-only privacy handling that permits local path/work context for computation while
  emitting only redacted paths and hashes.
- Hardened structured secret, private-key, and path scanning without relaxing strict printable
  proposal validation.
- Added the portable example overlay and usage documentation.
- Expanded generator, portable-template, and public-hygiene test coverage.
- Corrected the portable Codex base to the official `[tui]` `status_line` schema.
- Created the minimal ignored machine-local Codex overlay with mode `0600` and completed the
  content-safe zero-path comparison.
- Completed private Gate 2 backup, candidate validation, and sandbox rollback preflight without
  writing live runtime state.
- Recorded the final Gate 2 skip decision, retained the private backup and candidate, and closed the
  bounded Codex slice without a live runtime write.
- Reconciled the goal, plan, active context, progress, active decision log, and ADR handoff state.
- Used `.codex/config.toml` and live `~/.codex/config.toml` only as read-only comparison inputs;
  neither file was modified.

## Implementation files changed

- `scripts/config_generate.py`
- `scripts/test_config_generate.py`
- `scripts/public_hygiene_check.py`
- `scripts/test_public_hygiene_check.py`
- `scripts/test_portable_config_templates.py`
- `ai/config/README.md`
- `ai/config/codex/codex.overlay.example.toml`
- `goals/00-index.md`
- `goals/2026-07-14-01-agentic-loop-optimization.md`
- `plans/2026-07-14-agentic-loop-optimization.md`
- `plans/active-context.md`
- `plans/progress.md`
- `plans/decisions.md`
- `decisions/0011-agentic-loop-optimization.md`

The tracked `.codex/config.toml` and live `~/.codex/config.toml` were read-only comparison inputs and
were not modified.

## Tests executed

- `mcp__pctx__list_functions`
- `Serena.initialInstructions()`
- `Serena.checkOnboardingPerformed()` → error
- `Serena.readMemory({ memory_name: "START_HERE" })` → error
- `LeanCtx.ctxOverview({ path: "/Users/axos-agallentes/.dotfiles", task: "audit goal for dotfiles agentic loop optimization" })`
- `LeanCtx.ctxCall({ name: "ctx_intent", arguments: { query: "audit goal for dotfiles agentic loop optimization" } })`
- `LeanCtx.ctxShell(...)` marker checks for tracked config files and `setup.sh`
- `git ls-files --error-unmatch` checks for tracked-file status
- Plan-defined focused command:
  `python3 -m unittest scripts.test_config_manifest scripts.test_portable_config_templates scripts.test_config_generate`
  → 49 of 49 passed.
- Full `scripts/` unittest discovery → 85 run, exactly one failure caused only by the absent ignored
  `.claude/settings.local.json`; not green.
- Read-only `public_hygiene_check.py` → 390 findings: 142 absolute-home-path,
  197 private-org-name, and 51 private-org-url.
- Read-only `config_doctor.py` → 65 issues: 6 errors and 59 warnings; rule split recorded above.
- Official Codex config reference plus `codex features list` → `[tui]` `status_line` confirmed as the
  current schema and parsed successfully by the live CLI.
- Deterministic printable Codex proposal parse/repeat/hash verification → valid TOML, identical
  output, SHA-256 `bf13bdf914a7b28504e262183fd1a65182d560243e524efb44c94dbbdf7db280`.
- Pre-Gate-1 synthetic full-local-shape simulation → five changed paths, no exposed local values,
  and two structurally valid 64-character hashes; historical synthetic evidence superseded by the
  actual Gate 1 comparison.
- Actual Gate 1 base-plus-overlay versus live comparison → zero changed paths and two valid hashes;
  differing proposal/target byte hashes are expected from deterministic canonical rendering.
- Live `~/.codex/config.toml` pre/post SHA-256 verification → unchanged; no live write occurred.
- Independent final review → no remaining correctness- or security-significant code issue in the
  bounded scope.
- Gate 2 backup preflight → private directory mode `0700`; exact live backup, generated candidate,
  manifest, and rollback instructions each mode `0600`; backup hash matched current live.
- Candidate validation → TOML parse and isolated `CODEX_HOME` Codex parse passed; candidate bytes
  remained unchanged; semantic comparison reported zero changed paths despite a different byte
  hash.
- Sandbox rollback dry-run → restored the candidate to the exact original-live hash.
- Final live-state verification → live bytes, hash, and metadata unchanged; no runtime apply.

## Results

- The session-init surface is available and documented.
- The active goal prompt is tracked.
- The tracked cross-client configs are not yet portable in the broad sense: Codex, Gemini, Cursor,
  and Windsurf still embed the local home path and/or runtime routing details.
- `setup.sh` is clean of the tested home-path and bypass markers.
- The bounded Codex proposal-generator slice, Gate 1, Gate 2 preflight, and final Gate 2 skip
  decision are complete and verified; live runtime remains untouched.

## Residual risks

- The runtime configs under `.codex/`, `.gemini/`, `.cursor/`, and `.windsurf/` still carry
  machine-specific absolute paths.
- The canonical-byte rewrite was deliberately not adopted because it would change formatting only,
  not semantics; live bytes and hash remain unchanged.
- `START_HERE` memory is absent, so future sessions cannot rely on it for project bootstrap.

## Next recommended step

Human diff review is the only next step for this bounded slice. Commit or create a PR only on a
separate explicit request. Gemini, Cursor, and Windsurf migrations are future scopes and are not part
of this completed Codex slice.
