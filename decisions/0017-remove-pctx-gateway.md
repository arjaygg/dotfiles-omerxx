# Architecture Decision Record: Remove the pctx MCP Gateway

## 1. Title
Remove pctx and register every MCP server directly

## 2. Status
Accepted (2026-08-03). Supersedes [0001](0001-use-pctx-as-mcp-gateway.md) and
[0004](0004-lean-ctx-pctx-upstream.md).

## 3. Context

Decision 0001 adopted pctx for three reasons: it aggregated MCP servers so client
configs would not drift, it hid a large number of tool schemas behind a single
`execute_typescript` / `list_functions` pair, and its Deno "Code Mode" sandbox let
multi-step tool logic run without each intermediate result entering the context window.

Two of those three no longer hold.

**Schema amortization is now native.** Claude Code defers tool schemas and loads them on
demand via `ToolSearch`. A session lists ~200 tools by name and pays for the schema of
only the ones it uses. That is the same saving the gateway provided — roughly 40–90k
tokens across the four upstreams — without a proxy process.

**Config drift was never actually solved by the gateway.** `.mcp.json`, `.cursor/mcp.json`,
`.gemini/mcp.json`, `.gemini/settings.json`, `.gemini/config/mcp_config.json`,
`.windsurf/mcp_config.json` and `.codex/config.toml` each still needed a hand-maintained
`pctx` stanza, and 0001 accumulated four standalone exceptions (serena, lean-ctx,
notebooklm, chrome-devtools) within nine months. The portable base templates under
`ai/config/`, not the gateway, are what actually prevent drift.

**The cost was concrete.** The indirection generated a standing list of errata in
`ai/rules/tool-priority.md`: camelCase-vs-snake_case tool naming, `find_symbol` failing
*silently* inside dot-directories, `search_for_pattern`/`find_file`/`list_dir` missing from
the claude-code context, and a generated lean-ctx block that misreported which native tools
were denied. Every one of those existed only because calls were proxied.

## 4. Decision

Remove pctx entirely. Register Serena, LeanCtx, Repomix and Graphify as direct MCP servers
in each client config.

Replace `execute_typescript` batching with parallel tool calls in a single message. Serena
executes calls one at a time internally and they cannot race, so the ordering guarantee the
sandbox provided is preserved without it.

`scripts/mcp_topology_check.py` replaces `scripts/mcp_gateway_check.py`. It asserts the
inverse of what the old check asserted: every tracked client must reach Serena, may name
only approved servers, and must **not** contain a `pctx` entry. That last rule is the guard
against silent reintroduction.

## 5. Consequences

- Result-side compression is now solely LeanCtx's job. The gateway could filter a large
  tool result before it entered context; nothing does that automatically anymore, so
  oversized reads must be routed through `ctx_read` modes deliberately.
- Repomix and Graphify were reachable *only* through the gateway. They are now registered
  directly in all six client configs rather than being dropped, so no capability is lost.
- Four tool schemas load per client instead of two. Acceptable given deferred loading.
- `ai/skills/pctx-code-mode/` is retired; `ai/skills/tool-routing/SKILL.md` keeps the
  Qmd-vs-LeanCtx-vs-Serena decision tables, which remain valid.

## 6. Alternatives considered

- **Keep pctx for Cursor only.** Rejected: one client on a different topology reintroduces
  exactly the drift 0001 set out to prevent, and the errata would persist for that client.
- **Drop Repomix and Graphify with the gateway.** Rejected as a silent capability loss; the
  request was to remove the gateway, not the tools behind it.
- **Rewrite history.** The dated files under `plans/` and decisions 0001/0004 are left
  intact. They record why the gateway was adopted, which stays true; this record supersedes
  rather than erases them.
