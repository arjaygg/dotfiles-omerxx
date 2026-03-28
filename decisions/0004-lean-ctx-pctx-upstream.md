# 0004 — Integrate lean-ctx as pctx upstream (agent mode only)

**Date:** 2026-03-28

## Context

The existing token efficiency stack has two layers: rtk (shell output compression via CLI proxy) and post-tool-handler.sh (dumb head/tail truncation for Bash results >300 lines). Neither provides AST-based code skeleton scanning or SessionCache-backed file deduplication.

lean-ctx (yvgude/lean-ctx) is a Context Intelligence Engine offering:
- `ctx_tree`: Tree-sitter AST skeletons for 14 languages (map mode, ~80% token reduction)
- `ctx_read`: MD5-based SessionCache; re-reads cost ~13 tokens on cache hit
- `ctx_shell`: Semantic shell output compression with CEP Compliance Score
- Shell hooks: global aliases wrapping 90+ CLI tools
- MCP server: 21 specialized tools

The system already has rtk for shell compression and pctx as the single MCP gateway. lean-ctx can complement the existing stack or create conflict depending on how it is wired.

## Decision

Integrate lean-ctx as a pctx upstream server in **agent mode only** (`lean-ctx init --agent`). The MCP server (`ctx_tree`, `ctx_read`, `ctx_shell`) is activated. Shell hooks are explicitly disabled.

**Role assignment:**
- **rtk**: sole shell output compressor (pre-tool hook rewrites, command-level compression)
- **lean-ctx**: map-mode exploration (`ctx_tree`) and cached file reads (`ctx_read`) via MCP
- **post-tool-handler.sh**: unchanged; remains fast head/tail safety net for Bash results
- **Serena**: unchanged; primary for LSP symbol lookup, editing, and targeted search
- **lean-ctx CCP**: not activated; existing session-end.sh + pre-compact.sh are the continuity layer
- **context-mode MCP**: unchanged; different purpose (sandbox execution + search indexing)

**pctx.json addition:**
```json
{
  "name": "lean-ctx",
  "command": "lean-ctx",
  "args": ["mcp", "--stdio"],
  "env": { "LEAN_CTX_CACHE_TTL": "300" }
}
```

## Why

- lean-ctx's AST skeleton scanning (`ctx_tree`) fills a genuine gap: no existing tool in the stack produces compressed code skeletons for map-mode first-pass exploration of unfamiliar directories.
- lean-ctx's SessionCache (`ctx_read`) provides sub-second, ~13-token re-reads for repeatedly accessed large files within a session, complementing Serena's symbol-level access.
- Disabling shell hooks avoids a double-compression pipeline (lean-ctx alias → rtk proxy) that would produce output compressed twice with no coordination between engines.
- Adding lean-ctx as a pctx upstream preserves the single-gateway architecture established in 0001.

## Alternatives Rejected

- **`lean-ctx init --global` (shell hooks active)**: Rejected. Creates double-compression with rtk. Two engines compressing the same shell output produce uncoordinated results and make CEP Compliance Scores unreliable.
- **Replace rtk with lean-ctx**: Rejected. rtk is established with analytics history (`rtk gain`), integrated into Claude Code hooks, and referenced in RTK.md. Switching would require rebuilding the hook chain.
- **Replace Serena with lean-ctx for code search**: Rejected. Serena is LSP-backed with zero false positives; lean-ctx is pattern/AST-based. Serena stays primary for editing and symbol search; lean-ctx is the exploration layer.
- **Add lean-ctx as a parallel MCP gateway**: Rejected. 0001 mandates pctx as the single gateway. lean-ctx becomes an upstream.
- **Activate lean-ctx CCP**: Rejected. Would create a parallel session state format diverging from the plans/ artifact system indexed by qmd.

## Assumptions

- lean-ctx's `--agent` init mode does not modify shell rc files (`.zshrc`, `.zprofile`, `.bashrc`). This must be verified post-install.
- lean-ctx's 14-language AST coverage includes the languages actively used (TypeScript, Go, Python, Rust).
- lean-ctx MCP server invocation is `lean-ctx mcp --stdio`. Adjust pctx.json args if the actual command differs (check `lean-ctx --help`).
- pctx remains fault-tolerant if lean-ctx fails to start; other upstreams are unaffected.

## Post-Install Verification

```bash
lean-ctx --version && lean-ctx doctor
alias | grep lean                    # must return nothing
pctx mcp list                        # lean-ctx appears as Connected
lean-ctx gain                        # analytics work independently of rtk gain
```
