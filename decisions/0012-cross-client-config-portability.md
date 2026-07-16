# Architecture Decision Record: Cross-Client Config Portability (Gemini, Cursor, Windsurf)

## Status

Completed for the bounded read-only slice. Steps 1-6, 8, and 9 of
`goals/2026-07-15-02-cross-client-config-portability.md` are done. Step 7 (any live runtime write)
is intentionally, permanently out of scope for this slice.

## Decision

Extend the overlay-based portable config generator pattern established for Codex
(`decisions/0011-agentic-loop-optimization.md`) to the three remaining AI-agent clients that still
carried machine-local state in tracked source: Gemini, Cursor, and Windsurf. Do all three together,
read-only, rather than one client at a time — the user explicitly approved "all 3 clients,
read-only first" scope via `AskUserQuestion` earlier in this session.

Concretely: base-template-plus-gitignored-overlay via `scripts/config_generate.py`
(`deep_merge` + `expand_placeholders`, `${NAME}` syntax resolved only from explicit
`--set`/`variables`, never process environment), the same pattern already in place for Claude and
Codex.

## Why

- The repository's control-plane architecture (shared `ai/` source, neutral repo policy, thin
  per-client runtime directories) is unchanged by this slice — it only closes a portability gap for
  three clients that hadn't yet adopted the pattern.
- Gemini, Cursor, and Windsurf tracked configs mixed portable MCP/tool wiring with machine-local
  paths and environment values, the same class of problem Codex had.
- Doing all three together (rather than sequentially) was the user's explicit choice, made once and
  not to be re-asked, on the basis that the pattern is now proven (via Codex) and the read-only
  Gate-1 comparison step carries no live-write risk regardless of how many clients are done in one
  pass.
- Step 7 (writing any live runtime config) was explicitly excluded up front, independent of how much
  of Steps 1-6 completed — this keeps the slice reversible and review-only.

## Accepted implementation

1. Inventory each client's live runtime config against its tracked source to find machine-local
   drift (Step 1).
2. Write/extend portable base templates: `ai/config/gemini/settings.base.json` (new),
   `ai/config/cursor/mcp.base.json` (extended), `ai/config/windsurf/mcp_config.base.json`
   (extended) (Step 2).
3. Extend `ai/config/manifest.json` to a 7-entry manifest covering all clients' base/overlay/target
   triples (Step 3).
4. Extend the test suite (`scripts/test_portable_config_templates.py`,
   `scripts/test_config_manifest.py`) to cover the new bases and manifest entries (Step 4).
5. Extend `ai/config/README.md` with the new clients' overlay conventions (Step 5).
6. Gate 1 per client: create a real ignored overlay file (mode `0600`) under
   `~/.config/dotfiles-ai/` populated with actual machine-local values for that client, then run
   `--compare-against` against the live runtime path. Zero/cosmetic-only changed paths is the
   success signal. Never print overlay contents — only `changed_paths` and SHA-256 hashes, with
   sensitive mapping keys redacted (Step 6).
7. **Not done, by design:** write any live runtime config (Step 7).
8. Independent: fix a security regression in `.claude/settings.json`
   (`skipDangerousModePermissionPrompt: true` removed — this un-weakens, not weakens, a permission
   default) (Step 8, per user decision "fix it now").
9. Independent: create `.serena/memories/START_HERE.md` so `Serena.readMemory({ memory_name:
   "START_HERE" })` no longer fails on a fresh session (Step 9).

## Execution state (2026-07-16)

- Base templates written/extended for all three clients; 7-entry manifest in place.
- Full `scripts/` suite green: 91 passed, 42 subtests, zero failures — re-verified twice this
  session with no regressions.
- Gate 1 overlay fixtures created for all three clients (`gemini-settings.overlay.example.json`,
  `cursor.overlay.example.json`, `windsurf.overlay.example.json`) plus matching real ignored
  overlays under `~/.config/dotfiles-ai/`.
- Gate 1 `--compare-against` results:
  - Gemini and Cursor: clean, aside from a cosmetic `$schema` field difference (assumed non-semantic
    — the field carries no runtime behavior for either client).
  - Windsurf: reported `mcpServers.pctx.args[2..5]` as changed. Root cause: a **pre-existing** drift
    predating this slice — `ai/config/windsurf/mcp_config.base.json`'s `pctx` entry is missing the
    `-q` flag that live `~/.windsurf/mcp_config.json` has, shifting subsequent arg indices. This was
    not introduced by this slice's `lean-ctx`-only base-template change; it is flagged here as a
    finding, not silently fixed, and left out of scope.
- Security regression fixed: `.claude/settings.json`'s `skipDangerousModePermissionPrompt: true`
  removed. `skipWorkflowUsageWarning: true` kept (unrelated, not a permission-safety regression).
- `.serena/memories/START_HERE.md` created; confirmed loadable via `Serena.readMemory` in this
  session.
- Housekeeping: two untracked hook-generated scratch artifacts (`.claude/tdd-guard/`,
  `plans/session-snapshot.md`) surfaced during checkpointing were confirmed to have no git history
  and were added to `.gitignore` (see `plans/decisions.md` 2026-07-16 entry) rather than left as
  perpetual `git status` noise.
- No commit has been made for any of this slice's changes. Per global git-safety rules, committing
  remains a task for whenever the user explicitly requests it.

## Alternatives rejected

- **One client at a time (Codex-style sequential slices).** Rejected for this round because the
  user explicitly chose "all 3 clients, read-only first" — the pattern is proven from Codex, and
  Gate 1 is comparison-only with no live-write risk regardless of batch size.
- **Fix the windsurf `-q` drift as part of this slice.** Rejected — it's a pre-existing gap
  unrelated to this slice's `lean-ctx` base-template change; scope creep here would blur the
  boundary between "add portability for a new client" and "fix an unrelated existing bug."
- **Proceed to Step 7 (live write) since Steps 1-6 came out clean.** Rejected — the user's scope
  decision was unconditional: stop before any live write regardless of how much of Steps 1-6
  completes.
- **Leave `.claude/tdd-guard/` and `plans/session-snapshot.md` untracked indefinitely.** Rejected —
  both are machine-local regenerated artifacts with no git history; `.gitignore` is the correct
  permanent fix, matching the repo's existing convention for hook/tool runtime state.

## Consequences

- Gemini, Cursor, and Windsurf now follow the same base-plus-overlay portability pattern as Claude
  and Codex, closing the last three clients' portability gap.
- The manifest and test suite now cover all clients uniformly, making future drift regressions
  visible via `pytest scripts/`.
- The windsurf `-q` drift remains a known, documented gap for a future slice to fix (update
  `ai/config/windsurf/mcp_config.base.json` to include `-q`, then re-run Gate 1).
- Live runtime configs for all three clients remain completely untouched — this slice produced only
  comparison evidence, never a write.
- `.gitignore` now covers TDD-Guard and pre-compact-snapshot scratch state, so future sessions won't
  re-flag them as unexplained untracked files.

## Verification

- Full `scripts/` suite: 91 passed, 42 subtests, 0 failed (re-confirmed twice this session).
- Gate 1 comparisons for gemini, cursor, windsurf: gemini and cursor clean modulo cosmetic
  `$schema`; windsurf reported the pre-existing `-q`-flag drift only, with no overlay contents
  printed (only `changed_paths` and redacted-key SHA-256 hashes).
- `git check-ignore -v` confirmed `.claude/tdd-guard/data/test.json` and
  `plans/session-snapshot.md` were unignored before this ADR's housekeeping fix, and both have empty
  `git log --oneline -- <path>` history (never committed).

## References

- `goals/2026-07-15-02-cross-client-config-portability.md`
- `plans/2026-07-16-cross-client-config-portability.md`
- `plans/progress.md` (2026-07-16 section)
- `plans/decisions.md` (2026-07-16 entries)
- `decisions/0011-agentic-loop-optimization.md` (Codex slice this pattern is extended from)
- `ai/config/README.md`
