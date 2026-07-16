# 2026-07-16 — Cross-client config portability (Goal 02 execution)

Goal: `goals/2026-07-15-02-cross-client-config-portability.md`.
Status: `goals/00-index.md` = "In progress".

## User-approved scope (do not re-ask)

1. **Scope** ("All 3 clients, read-only first"): do Steps 1-6 for Gemini, Cursor, and Windsurf
   together, plus the independent Steps 8-9. Stop before any live write (Step 7) regardless.
2. **Security regression** ("Fix it now"): remove `skipDangerousModePermissionPrompt` from
   `.claude/settings.json` — done, see `plans/decisions.md` 2026-07-16 entry.

## Done

- **Step 9**: `.serena/memories/START_HERE.md` created. `Serena.readMemory({ memory_name:
  "START_HERE" })` succeeds.
- **Step 8**: removed `"skipDangerousModePermissionPrompt": true` from `.claude/settings.json`
  (kept `"skipWorkflowUsageWarning": true`). `pytest scripts/ -q` → 85 passed, 39 subtests, zero
  failures.
- **Step 1** (read-only inventory, no writes):

| Client | Live path | SHA-256 | Symlink? |
|---|---|---|---|
| Gemini settings | `~/.gemini/settings.json` | `c6b5d2bd...f869b716` | yes → tracked dotfiles |
| Gemini mcp | `~/.gemini/mcp.json` | `5891bf84...11712ef` | yes → tracked dotfiles |
| Cursor mcp | `~/.cursor/mcp.json` | `b38e4699...5ce2ce46f` | **no**, regular file |
| Windsurf mcp | `~/.windsurf/mcp_config.json` | `61ca6d43...b735a6ec25715fb` | yes → tracked dotfiles |

(Hashes reproduced from prior session's `shasum` output; re-verify with `shasum -a 256` before
Step 6 compare in case any live file has since changed.)

### Live content notes

- **`~/.gemini/settings.json`** (41 lines): `selectedAuthType: "oauth-personal"`,
  `mcpServers.pctx` (hardcoded `/Users/axos-agallentes/.config/pctx/pctx.json`),
  `security.auth.selectedType`, `context.fileName: ["AGENTS.md","GEMINI.md"]`,
  `experimental.enableAgents: true`, `statusLine.command` (uses `~/.claude/...` — portable, no
  literal absolute home path), `model: "Gemini 3.1 Pro (High)"`, `trustedWorkspaces` (3 absolute,
  machine/user-specific paths).
- **`~/.gemini/mcp.json`** (14 lines): only `mcpServers.pctx`, same shape as the existing base
  template — **already portable, no base-template change needed**.
- **`~/.cursor/mcp.json`** (21 lines): `mcpServers.pctx` (full absolute path
  `/Users/axos-agallentes/homebrew/bin/pctx`, args lack `-q` unlike other clients), plus
  `notebooklm` (`/Users/axos-agallentes/.local/bin/notebooklm-mcp`) and `chrome-devtools`
  (`/Users/axos-agallentes/.local/bin/chrome-devtools-mcp-wrapper.sh`) — both **entirely
  unmodeled** by the current base template.
- **`~/.windsurf/mcp_config.json`** (22 lines): `mcpServers.lean-ctx` (command `lean-ctx`, env
  `LEAN_CTX_DATA_DIR: /Users/axos-agallentes/.lean-ctx`, `LEAN_CTX_FULL_TOOLS: "1"`) — **entirely
  unmodeled** — plus `mcpServers.pctx` (bare `pctx` command, matches base already).

### Existing scaffolding read

- `ai/config/manifest.json` — 6 entries (claude, codex, gemini, cursor, windsurf, pctx). Gemini's
  entry only covers `mcp.json` (base=`ai/config/gemini/mcp.base.json`,
  runtime=`~/.gemini/mcp.json`, overlay=`~/.config/dotfiles-ai/gemini.overlay.json`). **No entry
  exists for `.gemini/settings.json`.**
- `ai/config/gemini/mcp.base.json` (16 lines) — models only `pctx` w/ `${PCTX_CONFIG}` —
  matches live shape exactly, no change needed.
- `ai/config/cursor/mcp.base.json` (15 lines) — models only `pctx` w/ bare `"pctx"` command +
  `${PCTX_CONFIG}` — missing `notebooklm`/`chrome-devtools`.
- `ai/config/windsurf/mcp_config.base.json` (15 lines) — models only `pctx` w/ `${PCTX_CONFIG}` —
  missing `lean-ctx`.
- `ai/config/codex/codex.overlay.example.toml` (19 lines) — reference pattern: commented header
  warning against secrets/committing a real overlay, then TOML w/ `${PROJECT_ROOT}`/
  `${MARKETPLACE_CACHE}` placeholders.
- `ai/config/claude/settings.overlay.example.json` (5 lines) — reference pattern: minimal
  `{"model": "sonnet", "advisorModel": "fable"}` — confirms machine/user *preferences* (like
  `model`) belong in the overlay-example, not the base.
- `ai/config/claude/settings.base.json` — confirmed it has **no `model` key at the top level
  intended as a preference override precedent**; actually it DOES have `"model": "sonnet"` baked
  into the base (line 113) as a shared default, while the overlay-example separately shows
  `model`/`advisorModel` as override-able. So: base can carry a sensible shared default for
  `model`, and overlay-example shows how to override it — apply the same pattern to gemini
  settings (base carries no opinionated personal `model` value scoped to this machine; put the
  literal `"Gemini 3.1 Pro (High)"` in the overlay-example instead, since it's this user's specific
  preference, not a repo-wide default).
- `ai/config/README.md` (96 lines) — documents the convention; only has CLI examples for
  Claude/Codex plus one generic gemini `--set` example; no per-client overlay docs yet for
  cursor/windsurf, and doesn't describe the newly-found servers (notebooklm/chrome-devtools/
  lean-ctx).

## Remaining work (Steps 2-6), concrete file list

### Step 2 — base templates

1. **`ai/config/gemini/settings.base.json`** (new). Include (portable, no literal absolute paths):
   `selectedAuthType`, `mcpServers.pctx` (placeholder `${PCTX_CONFIG}`, mirroring
   `mcp.base.json`), `security.auth.selectedType`, `context.fileName`,
   `experimental.enableAgents`, `statusLine.command` (as-is, already `~`-relative). **Exclude**
   `model` and `trustedWorkspaces` from the base — those are personal/machine-specific
   preferences, move to the new gemini-settings overlay-example (Step 5) with placeholder/example
   values, not the real absolute paths.
2. **`ai/config/cursor/mcp.base.json`** (extend). Add `notebooklm` and `chrome-devtools` entries.
   Decide the `pctx` command placeholder to use: live uses a **full absolute path**
   (`/Users/axos-agallentes/homebrew/bin/pctx`) unlike other clients' bare `"pctx"` — introduce an
   overlay-able placeholder (e.g. `${PCTX_BIN}`) for the command itself, defaulting the base to
   the portable bare `"pctx"` (consistent with gemini/windsurf) and letting the overlay override to
   an absolute path only if a given machine's PATH doesn't resolve `pctx`. Also decide whether
   `notebooklm`/`chrome-devtools` binary paths go in base (as `${NOTEBOOKLM_BIN}` /
   `${CHROME_DEVTOOLS_BIN}` placeholders) or overlay-only — prefer base w/ placeholders + overlay
   supplies real paths, consistent with the existing `${PCTX_CONFIG}` pattern.
3. **`ai/config/windsurf/mcp_config.base.json`** (extend). Add `lean-ctx` entry: command
   `"lean-ctx"` (bare, portable), env `LEAN_CTX_DATA_DIR: "${LEAN_CTX_DATA_DIR}"` (placeholder —
   live value `/Users/axos-agallentes/.lean-ctx` is machine-specific), `LEAN_CTX_FULL_TOOLS: "1"`
   (portable literal, keep as-is in base).

### Step 3 — manifest entries

- Add a **new** `ai/config/manifest.json` entry for gemini settings.json, distinct from the
  existing `gemini` (mcp.json) entry — pick a non-colliding `name` (e.g. `gemini-settings`).
  Fields: `base: ai/config/gemini/settings.base.json`, `runtime: ~/.gemini/settings.json`,
  `overlay: ~/.config/dotfiles-ai/gemini-settings.overlay.json` (or similar, follow existing
  naming convention under `~/.config/dotfiles-ai/`).
- No new manifest entries needed for cursor/windsurf (existing `cursor`/`windsurf` entries already
  point at the right base/runtime paths) — just confirm their `base` path still matches after
  Step 2 edits (it will, same filename).

### Step 4 — tests

Add to `scripts/test_portable_config_templates.py`, mirroring the three existing Codex-pattern
tests (portable-and-valid-format w/ specific key assertions; no-mutation-on-generate;
overlay-example-parses-and-generates-correctly) for: gemini `mcp.base.json` (if not already
covered), new gemini `settings.base.json`, extended cursor `mcp.base.json`, extended windsurf
`mcp_config.base.json`.

### Step 5 — overlay-example fixtures + README

- New fixtures: `ai/config/gemini/gemini-settings.overlay.example.json` (or naming consistent w/
  Step 3), `ai/config/cursor/cursor.overlay.example.json`,
  `ai/config/windsurf/windsurf.overlay.example.json` — mirror
  `ai/config/claude/settings.overlay.example.json`'s minimal shape (real-looking but non-sensitive
  placeholder values, e.g. `${PCTX_CONFIG}` resolved to an example path like
  `/home/example/.config/pctx/pctx.json`, per the Codex overlay-example's commented-header
  convention warning against real secrets/paths).
- Update `ai/config/README.md`: describe the newly-modeled servers (notebooklm, chrome-devtools,
  lean-ctx), add per-client CLI examples for gemini-settings/cursor/windsurf mirroring the
  existing Claude/Codex examples.

### Step 6 — Gate-1-equivalent compare

Run `scripts/config_generate.py <base> --overlay <overlay> --compare-against <live-path>` for all
four targets (gemini mcp.json, gemini settings.json, cursor mcp.json, windsurf mcp_config.json)
using a real ignored overlay under `~/.config/dotfiles-ai/` populated with each client's actual
machine-local values (following the Codex Gate 1 precedent — create the overlay file mode `0600`,
never print its contents). Report `changed_paths`/hashes only, per the existing redaction
behavior. Zero-changed-path is the success signal, same as Codex.

### Step 7 — unconditional hard stop

Do not write to any live runtime config. Remains blocked regardless of how much of Steps 2-6
completes, per the goal's explicit non-goal.

## Next-session checklist (TodoWrite this on resume)

- [ ] Write `ai/config/gemini/settings.base.json`
- [ ] Extend `ai/config/cursor/mcp.base.json` (notebooklm, chrome-devtools, `${PCTX_BIN}`)
- [ ] Extend `ai/config/windsurf/mcp_config.base.json` (lean-ctx, `${LEAN_CTX_DATA_DIR}`)
- [ ] Add gemini-settings manifest entry to `ai/config/manifest.json`
- [ ] Add specific tests to `scripts/test_portable_config_templates.py` for all changed/new bases
- [ ] Write 3 new `*.overlay.example.json` fixtures
- [ ] Update `ai/config/README.md`
- [ ] Run `pytest scripts/ -q` — must stay green
- [ ] Create real ignored overlays under `~/.config/dotfiles-ai/` (mode 0600) with actual
      machine-local values for gemini-settings/cursor/windsurf
- [ ] Run `--compare-against` for all four targets, report changed-path counts/hashes
- [ ] Update `plans/active-context.md`, `plans/progress.md`, `plans/decisions.md`,
      `goals/00-index.md` (→ "Completed (bounded read-only slice)" if Steps 1-6+8-9 all land)
- [ ] Draft `decisions/NNNN-cross-client-config-portability.md` durable ADR once the bounded
      subset lands
