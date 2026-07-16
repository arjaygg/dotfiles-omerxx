# Portable configuration proposals

This directory contains tracked, portable configuration bases and examples. It is
not a live runtime directory. `scripts/config_generate.py` parses proposal bases as
JSON or TOML according to their extension, merges an optional ignored overlay, and
prints a proposal to stdout; it never writes a runtime file or adopts runtime drift.

Direct rendering with `build_proposal` or the CLI without `--compare-against`
rejects absolute-home paths, private work context, and secret-like content before
anything reaches stdout. Comparison mode may process ignored local path and work
context, but emits only changed paths—with sensitive mapping keys redacted—and
SHA-256 hashes. Secret assignments and private keys remain rejected in comparison
mode.

## Claude

- `claude/settings.base.json` is the sanitized, portable snapshot for the current
  tracked Claude settings.
- `claude/settings.overlay.example.json` shows the shape of a local overlay without
  organization names, user paths, or secrets.

## Other clients

- `codex/config.base.toml` is the portable Codex proposal base and is wired into
  proposal generation. Applying a proposal to the Codex runtime remains
  intentionally unwired and gated pending separate review.
- `codex/codex.overlay.example.toml` demonstrates non-secret local Codex project,
  skill, and marketplace configuration using explicit path placeholders.
- `gemini/mcp.base.json`, `cursor/mcp.base.json`, and
  `windsurf/mcp_config.base.json` contain portable PCTX client definitions.
- `gemini/settings.base.json` is the portable proposal for `~/.gemini/settings.json`
  (auth type, MCP servers, context file names, status line). Personal preferences
  such as `model` and `trustedWorkspaces` are intentionally left out of the base and
  belong in a local overlay — see `gemini/gemini-settings.overlay.example.json`.
- `cursor/mcp.base.json` also models the `notebooklm` and `chrome-devtools` MCP
  servers using bare, `PATH`-resolved command names; an overlay may replace these
  with absolute paths on machines where the binaries aren't on `PATH` (see
  `cursor/cursor.overlay.example.json`).
- `windsurf/mcp_config.base.json` also models the `lean-ctx` MCP server. Its
  `LEAN_CTX_DATA_DIR` env var is a `${LEAN_CTX_DATA_DIR}` placeholder supplied via
  `--set` or a local overlay (see `windsurf/windsurf.overlay.example.json`).
- `pctx/pctx.base.json` uses executable names resolved by the local `PATH`, rather
  than machine-specific installation paths.

The current `.claude/settings.json` distribution path remains unchanged until a
separate review approves runtime wiring. This keeps the migration reversible while
the generated proposal is validated.

Example:

```sh
python3 scripts/config_generate.py \
  ai/config/claude/settings.base.json \
  --overlay ai/config/claude/settings.overlay.example.json
```

Or generate a Codex TOML proposal:

```sh
python3 scripts/config_generate.py \
  ai/config/codex/config.base.toml \
  --overlay ai/config/codex/codex.overlay.example.toml \
  --set "PCTX_CONFIG=/tmp/proposal-pctx.json" \
  --set "PROJECT_ROOT=/tmp/example-project" \
  --set "MARKETPLACE_CACHE=/tmp/marketplace-cache"
```

The `/tmp` paths above are fake printable-proposal inputs. Placeholder substitution
is literal; this example does not rely on Codex, pctx, or the shell expanding `~`.
Review proposal output only; never redirect it to a live configuration path.

Portable client bases use explicit `${NAME}` markers. Supply replacements with
`--set`; the generator never reads process environment variables implicitly:

```sh
python3 scripts/config_generate.py \
  ai/config/gemini/mcp.base.json \
  --set PCTX_CONFIG=/tmp/pctx.json
```

For a content-safe review against an existing JSON or TOML target, use
`--compare-against`. It reports only changed configuration paths, with sensitive
mapping-key components redacted, and SHA-256 hashes:

```sh
python3 scripts/config_generate.py \
  ai/config/claude/settings.base.json \
  --overlay ai/config/claude/settings.overlay.example.json \
  --compare-against "$HOME/.claude/settings.json"
```

A safe Codex comparison can use an ignored non-secret local overlay without
rendering its private values:

```sh
python3 scripts/config_generate.py \
  ai/config/codex/config.base.toml \
  --overlay "$HOME/.config/dotfiles-ai/codex.overlay.toml" \
  --compare-against "$HOME/.codex/config.toml" \
  --set "PCTX_CONFIG=$HOME/.config/pctx/pctx.json" \
  --set "PROJECT_ROOT=$HOME/git/example-project" \
  --set "MARKETPLACE_CACHE=$HOME/.cache/marketplace"
```

Comparison is read-only. Do not redirect its output to a live file or treat it as a
runtime apply step.
