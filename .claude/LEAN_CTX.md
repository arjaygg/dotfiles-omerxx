# lean-ctx — Context Intelligence Engine

**Integration mode:** pctx upstream only. Shell hooks are NOT active (rtk handles shell compression).

## Usage

lean-ctx is available via `pctx execute_typescript` alongside Serena:

- `ctx_tree`  — AST skeleton tree for 14 languages; use for map-mode first pass on unfamiliar code
- `ctx_read`  — cached file read with MD5 dedup (F1/F2 shorthand on cache hit, ~13 tokens)
- `ctx_shell` — semantic shell output compression with CEP Compliance Score

## When to Use

**Map mode (exploration):** `ctx_tree` → Serena.getSymbolsOverview → `ctx_read` if repeated
**Edit mode (precision):** Serena.findSymbol → Serena.replaceSymbolBody → Edit

Switch from lean-ctx to Serena once you've identified the edit target.

## What NOT to Use

- `lean-ctx init --global` — **never run**; shell hooks conflict with rtk (double-compression)
- lean-ctx CCP (Context Continuity Protocol) — not activated; existing session-end.sh + pre-compact.sh are authoritative

## Analytics (secondary)

```bash
lean-ctx gain        # cache hit rate and token savings for file reads
lean-ctx discover    # read patterns that would benefit from caching
```

These are separate from `rtk gain` (which covers shell commands). Different scopes, both valid.

## Config

`~/.lean-ctx/config.toml` — cache TTL and other settings
`LEAN_CTX_CACHE_TTL` is set in `~/.config/pctx/pctx.json` env block (not in shell profile)

## Installation

```bash
# Install binary (check https://github.com/yvgude/lean-ctx for installer)
lean-ctx init --agent   # agent mode only — sets up MCP server, NOT shell hooks

# Verify no shell hooks were added:
alias | grep lean       # must return nothing
```

## pctx.json entry

```json
{
  "name": "lean-ctx",
  "command": "lean-ctx",
  "args": ["mcp", "--stdio"],
  "env": { "LEAN_CTX_CACHE_TTL": "300" }
}
```
