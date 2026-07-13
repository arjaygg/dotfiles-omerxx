# Portable configuration proposals

This directory contains tracked, portable configuration bases and examples. It is
not a live runtime directory. `scripts/config_generate.py` merges a base JSON file
with an optional ignored overlay and prints a proposal to stdout; it never writes a
runtime file or adopts runtime drift.

## Claude

- `claude/settings.base.json` is the sanitized, portable snapshot for the current
  tracked Claude settings.
- `claude/settings.overlay.example.json` shows the shape of a local overlay without
  organization names, user paths, or secrets.

## Other clients

- `codex/config.base.toml` is a portable Codex base; it is parser-validated but
  is not wired into runtime generation yet.
- `gemini/mcp.base.json`, `cursor/mcp.base.json`, and
  `windsurf/mcp_config.base.json` contain portable PCTX client definitions.
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

Review the JSON output; do not redirect it to a live configuration path.

Portable client bases use explicit `${NAME}` markers. Supply replacements with
`--set`; the generator never reads process environment variables implicitly:

```sh
python3 scripts/config_generate.py \
  ai/config/gemini/mcp.base.json \
  --set PCTX_CONFIG=/tmp/pctx.json
```

For a content-safe review against an existing JSON target, use
`--compare-against`; it reports only changed JSON paths and SHA-256 values:

```sh
python3 scripts/config_generate.py \
  ai/config/claude/settings.base.json \
  --overlay ai/config/claude/settings.overlay.example.json \
  --compare-against "$HOME/.claude/settings.json"
```
