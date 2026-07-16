# Goal 02 — Cross-client config portability and residual-gap cleanup

## Objective

Extend the overlay-based portable config generator pattern proven for Codex
(`goals/2026-07-14-01-agentic-loop-optimization.md`) to the remaining clients that still embed
machine-local absolute paths, and close the small residual gaps that slice explicitly left open.

## Why

Goal 01 closed a bounded Codex-only slice: `scripts/config_generate.py` now supports TOML base +
ignored local overlay, verified against the live `~/.codex/config.toml` with zero semantic drift
(Gate 1/2, PR #324, merged 2026-07-15). Its own "Residual risks" and the parent goal's "Non-goals"
explicitly deferred three things instead of folding them in:

- Gemini (`.gemini/settings.json`, `.gemini/mcp.json`), Cursor (`.cursor/mcp.json`), and Windsurf
  (`.windsurf/mcp_config.json`) still hardcode `/Users/axos-agallentes/...` and `pctx.json`/
  `.lean-ctx` paths — the same class of problem the Codex generator solved, just not yet applied
  to these clients.
- The full `scripts/` test suite has exactly one failure (85 run), caused only by the absent
  ignored `.claude/settings.local.json` — a fixture/environment gap, not a code defect.
- The Serena `START_HERE` memory does not exist, so `Serena.readMemory({ memory_name: "START_HERE" })`
  fails every session — flagged twice in Goal 01 evidence as a bootstrap gap for future sessions.

Goal 01 is marked "Completed (bounded Codex slice)" in `goals/00-index.md`; this is a new,
separately scoped goal rather than reopening that closed entry.

## Current state

- `scripts/config_generate.py` supports TOML base + TOML overlay merge, `--set NAME=VALUE`
  placeholder expansion, and a compare-only mode that redacts sensitive paths/keys while reporting
  changed-path counts and hashes. This exists today only for the Codex shape.
- `ai/config/codex/config.base.toml` + `ai/config/codex/codex.overlay.example.toml` are the
  reference pair for the pattern to replicate.
- `.gemini/settings.json`, `.gemini/mcp.json`, `.cursor/mcp.json`, and `.windsurf/mcp_config.json`
  are tracked as regular (non-symlinked) files and each embeds `/Users/axos-agallentes/.config/pctx/pctx.json`
  (Windsurf additionally embeds `/Users/axos-agallentes/.lean-ctx`).
- No `ai/config/manifest.json` entries exist yet for Gemini/Cursor/Windsurf (only Codex was added
  in Goal 01, per its Step 2 file list).
- `.claude/settings.local.json` is gitignored and intentionally absent from the tracked repo; the
  one failing test assumes its presence.
- `Serena.listMemories()` returns `cicd-acted-runs`, `project_overview`, `style_and_conventions`,
  `suggested_commands` — no `START_HERE`.

## Non-goals

- Do not touch `.codex/config.toml` or re-open the Gate 1/2 decision already closed in Goal 01 —
  the live Codex config stays hand-edited unless separately approved.
- Do not perform the broader primitive/skill audit from Goal 01 Steps 4-12 (`cap`, `stark`,
  `ironman`, `fury`, `hawk`, `strange`, full loop-inefficiency review) — that remains a distinct,
  larger future goal, not folded into this one.
- Do not weaken any existing hard-deny, permission default, or symlink target while adding new
  overlay/manifest plumbing.
- Do not write to any live runtime config (`~/.gemini/...`, `~/.cursor/...`, `~/.codeium/windsurf/...`)
  without an explicit approval gate mirroring Goal 01's Gate 1 (overlay creation) and Gate 2
  (backup + rollback-verified compare, skip-on-zero-delta) pattern.

## Steps

1. For each of Gemini, Cursor, and Windsurf: confirm the live runtime config path, capture its
   current SHA-256, and identify every machine-local value (absolute home path, `pctx.json` path,
   `.lean-ctx` path) that must move to an ignored overlay.
2. Extract a portable base template per client (`ai/config/<client>/config.base.json` or
   equivalent) containing only shared, non-machine-specific defaults — mirroring
   `ai/config/codex/config.base.toml`.
3. Extend `ai/config/manifest.json` with entries for each new client base/runtime/overlay path,
   following the existing Codex entry shape.
4. Extend `scripts/config_generate.py` / add client-specific test coverage so each new base+overlay
   pair round-trips correctly (JSON for Gemini/Cursor/Windsurf, unlike Codex's TOML), without
   touching the working Codex TOML path.
5. Document the ignored overlay convention for each client in `ai/config/README.md`, with a
   non-sensitive example overlay per client (mirroring `codex.overlay.example.toml`).
6. Run a Gate-1-equivalent comparison (generated base+overlay proposal vs. live runtime config) for
   each client and report changed-path counts and hashes without exposing local values.
7. Stop for explicit approval before any live runtime write (mirrors Goal 01 Step 5) — this goal
   produces proposals and verification evidence only unless separately authorized.
8. Investigate and fix the one residual full-suite test failure (missing ignored
   `.claude/settings.local.json`) — likely a test fixture/skip-condition fix, not new production
   code.
9. Create the missing Serena `START_HERE` memory summarizing project layout, the goals/plans/
   decisions convention, and pointers to `ai/rules/tool-priority.md` and `AGENTS.md`, so future
   sessions can bootstrap via `Serena.readMemory({ memory_name: "START_HERE" })` instead of failing.

## Acceptance criteria

- A portable base template and documented ignored-overlay convention exist for Gemini, Cursor, and
  Windsurf, each verified against its live runtime config with a zero (or fully explained)
  changed-path delta, evidence captured the same way Goal 01 captured Gate 1/2 evidence.
- `ai/config/manifest.json` lists all four clients (Codex plus the three new ones) consistently.
- No live runtime file is modified without a separate explicit approval step, logged the same way
  Goal 01 logged its Gate 1/2 decisions.
- The previously-failing full-suite test either passes or has a documented, justified skip
  condition; the plan-focused suite stays green throughout.
- `Serena.readMemory({ memory_name: "START_HERE" })` succeeds in a fresh session.
- `plans/active-context.md`, `plans/progress.md`, and `plans/decisions.md` are updated as this goal
  moves from proposed to active to whatever bounded subset is actually approved for execution.

## Evidence to update

- `plans/active-context.md`
- `plans/progress.md`
- `plans/decisions.md`
- `plans/<date>-cross-client-config-portability.md` (new dated plan, once execution starts)
- `decisions/NNNN-cross-client-config-portability.md` (durable ADR, once a bounded subset is
  approved)
- `goals/00-index.md` (status transitions: Proposed → In progress → Completed, per bounded slice)
- Any new `ai/config/<client>/*` base/overlay/manifest files
- Verification outputs: per-client changed-path/hash comparison, test suite results,
  `Serena.readMemory({ memory_name: "START_HERE" })` success confirmation

## Stop and ask if

- Any proposed change would write to a live runtime config, permission default, hard-deny, or
  symlink target.
- The bounded subset to execute first is unclear (three clients is likely too much for one
  approval — expect to pick one, same as Goal 01 picked Codex first).
- Scope creeps toward the broader primitive/skill audit explicitly excluded above.
- Fixing the residual test failure would require adding `.claude/settings.local.json` handling
  that changes real permission behavior rather than just satisfying the test fixture.
