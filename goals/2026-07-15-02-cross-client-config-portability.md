# Goal 02 — Cross-client config portability (post-Codex clients)

## Objective

Extend the overlay-based, proposal-only config generation workflow proven for Codex in
[Goal 01](2026-07-14-01-agentic-loop-optimization.md) to the remaining tracked clients — Claude,
Gemini, Cursor, Windsurf, and `pctx` — so machine-local runtime values are moved out of tracked
config into ignored per-client overlays across the whole harness, not just Codex.

## Why

`decisions/0011-agentic-loop-optimization.md` explicitly scoped its accepted implementation to
Codex only ("Codex has enough distinct TOML/generator work to deserve a focused, reviewable
slice") and recorded as an open item: "Broader client migration remains separately scoped." The
baseline evidence behind that decision found Claude settings already clean of tested
bypass/local-path anchors, while Codex, Gemini, Cursor, and Windsurf still contained machine-local
absolute paths. This goal closes that gap using the same deterministic, review-before-apply
approach rather than ad hoc per-client edits.

## Current state

- Repo root: `/Users/axos-agallentes/.dotfiles`.
- `ai/config/manifest.json` already declares base/runtime/overlay paths for all six clients:
  `claude`, `codex`, `gemini`, `cursor`, `windsurf`, `pctx`.
- Portable base templates already exist on disk for every client:
  - `ai/config/claude/settings.base.json` (+ `settings.overlay.example.json`)
  - `ai/config/codex/config.base.toml` (+ `codex.overlay.example.toml`)
  - `ai/config/gemini/mcp.base.json`
  - `ai/config/cursor/mcp.base.json`
  - `ai/config/windsurf/mcp_config.base.json`
  - `ai/config/pctx/pctx.base.json`
- `scripts/config_generate.py` is format-agnostic (JSON and TOML) and already exposes
  `build_proposal` / `compare_proposal` / `main` (`base`, `--overlay`, `--compare-against`,
  `--set NAME=VALUE`) independent of any one client.
- Only Codex has been taken through the full Gate 1 (portable base correction + zero-changed-path
  comparison) and Gate 2 (private backup, candidate parse, isolated-runtime parse, rollback
  dry-run) verification cycle. `scripts/test_portable_config_templates.py` currently only defines
  `CODEX_TEMPLATE` / `CODEX_OVERLAY` constants — no equivalent deep test coverage exists yet for
  Claude, Gemini, Cursor, Windsurf, or `pctx`.
- `scripts/test_config_manifest.py` validates the manifest shape but has not been confirmed (in
  this goal's research) to assert per-client base-file parseability for the non-Codex entries.
- Public hygiene (390 findings) and config doctor (65 issues) baselines from Goal 01 still include
  absolute-home-path and private-org-name findings attributable to non-Codex clients; those counts
  are expected to drop as this goal proceeds, and should be re-measured rather than assumed.
- No live runtime file has been modified for any client as part of Goal 01; this goal inherits that
  same constraint.

## Non-goals

- Do not write to any live runtime config (`~/.claude/settings.json`, `~/.gemini/*`,
  `~/.cursor/mcp.json`, `~/.windsurf/mcp_config.json`, `~/.config/pctx/pctx.json`) without a
  separate, explicit user-approved apply step per client, mirroring Codex Gate 2.
  Note: `~/.codex/config.toml` is only referenced here as the Goal 01 comparison baseline —
  Codex is functionally complete and out of scope for new work in this goal.
- Do not weaken existing hard-denies, hook enforcement, branch protections, or credential hygiene
  in any client's tracked settings.
- Do not duplicate shared policy from `ai/rules/` or `ai/skills/` into client-local overlays —
  overlays carry only machine-local values (paths, local toggles), not policy.
- Do not change `scripts/config_generate.py`'s public CLI surface or output format in
  backward-incompatible ways without updating all existing Codex-focused tests and docs that
  depend on it.

## Steps

1. Re-confirm session context and re-verify the manifest and base templates listed above are still
   current (files can drift between goal authoring and execution).
2. For each remaining client (Claude, Gemini, Cursor, Windsurf, `pctx`), diff the tracked base
   template against the live runtime file to enumerate machine-local values that need to move to
   an overlay (absolute paths, machine-specific local toggles, local marketplace/cache paths).
3. Extend or add per-client `*.overlay.example.json` templates (mirroring
   `ai/config/codex/codex.overlay.example.toml` and
   `ai/config/claude/settings.overlay.example.json`) documenting the expected overlay shape for
   Gemini, Cursor, Windsurf, and `pctx`.
4. Extend `scripts/test_portable_config_templates.py` with per-client constants and test cases
   equivalent to the existing `CODEX_TEMPLATE`/`CODEX_OVERLAY` coverage (base parses, overlay
   merges deterministically, `deep_merge`/`expand_placeholders` behave correctly per format).
5. Run Gate 1 per client: generate the deterministic proposal from base + minimal ignored overlay,
   compare against the live runtime file with `compare_proposal`, and require a zero-changed-path
   result (or an explicit, reviewed list of intended path changes) before proceeding.
6. Run Gate 2 per client: create a private mode-`0700` backup directory under
   `~/.config/dotfiles-ai/backups/`, back up the exact live file (mode `0600`), generate the
   candidate, parse-validate the candidate in the client's native format, and prove a rollback
   dry-run restores the original hash exactly.
7. Re-run the full `scripts/` test discovery, `public_hygiene_check.py`, and `config_doctor.py`
   after each client's slice and record the before/after finding counts (do not assume improvement
   without re-measuring).
8. Update `decisions/0011-agentic-loop-optimization.md` or draft a new
   `decisions/NNNN-cross-client-config-portability.md` capturing per-client Gate 1/Gate 2 evidence,
   or amend it incrementally as each client's slice completes.
9. Present a per-client apply decision (apply vs. skip-as-no-op, following the Codex precedent of
   skipping a purely canonical-format rewrite when the semantic delta is zero) and stop for
   explicit user approval before any live write.

## Acceptance criteria

- Every client in `ai/config/manifest.json` (Claude, Gemini, Cursor, Windsurf, `pctx` — Codex
  already done) has an overlay example template and passing deterministic base+overlay generation.
- `scripts/test_portable_config_templates.py` has explicit test coverage for each client's base
  template and overlay merge behavior, not just Codex.
- Each client has a recorded Gate 1 zero-changed-path (or explicitly reviewed non-zero) comparison
  against its live runtime file.
- Each client has a recorded Gate 2 backup + candidate-parse + rollback-dry-run result before any
  live apply is considered.
- No live runtime client config is modified without a separate, explicit per-client user approval
  step, consistent with the Codex precedent in Goal 01.
- Public hygiene and config doctor findings are re-measured (not assumed) after each client's
  slice, with counts recorded in `plans/` evidence.
- Work proceeds on a branch/worktree per `AGENTS.md`, never directly on `main`.

## Evidence to update

- `plans/active-context.md`, `plans/progress.md`, `plans/decisions.md`
- A dated report under `plans/` (e.g. `plans/2026-07-15-cross-client-config-portability.md`)
  tracking per-client Gate 1/Gate 2 status
- `decisions/0011-agentic-loop-optimization.md` (amend) or a new
  `decisions/NNNN-cross-client-config-portability.md`
- `goals/00-index.md` (row for this goal, updated status)
- Any new/changed files under `ai/config/<client>/` and `scripts/test_portable_config_templates.py`
- Verification outputs: base/overlay parse checks, comparison JSON, backup manifests, rollback
  dry-run results, and re-measured public-hygiene / config-doctor counts per client

## Stop and ask if

- Any proposed change would write to a live runtime config file for any client.
- Any task requires touching secrets, credentials, tokens, private keys, or machine-local sensitive
  files beyond reading them for comparison.
- A client's live runtime file has structural differences from its tracked base large enough that
  a zero-changed-path Gate 1 comparison looks unreachable without a policy decision (e.g. the live
  file carries settings not represented in the base template at all).
- The next step would commit, push, create a PR, merge, or modify `main` directly.
- Any client requires duplicating shared policy instead of delegating to `ai/rules/`/`ai/skills/`.
