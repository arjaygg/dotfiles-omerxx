# Architecture Decision Record: Use pctx as Central MCP Gateway

## 1. Title
Use pctx (Port of Context) as the Central MCP Gateway

## 2. Status
Accepted

## 3. Context
We currently use multiple AI agents (Claude Code, Cursor, Windsurf, Gemini, Codex) and multiple MCP servers (context7, directory-tree, filesystem, exa, etc.). Managing these configurations individually across all IDEs and CLI tools leads to configuration drift. Furthermore, when agents execute multi-step logic by calling tools sequentially, it rapidly consumes the context window and is prone to errors.

pctx (Port of Context) introduces a "Code Mode" that executes TypeScript within an isolated Deno sandbox, preventing context bloat by returning only final results. It also acts as an aggregator for MCP servers.

## 4. Decision
We will migrate all standalone MCP server definitions out of the individual agent config files (`.cursor/mcp.json`, `~/.claude/settings.json`, `.windsurf/mcp_config.json`, etc.) and define them centrally within `pctx`. 
All AI agents will be reconfigured to connect solely to the `pctx` MCP server, forcing the usage of Code Mode for complex tasks.

## 5. Amendment (2026-08-01): approved standalone exceptions

The "connect solely to pctx" rule has two recorded exceptions, enforced by
`scripts/mcp_gateway_check.py`:

- **serena** — approved as a standalone fallback server for clients that need symbolic editing
  even when the gateway is down (see commits 9868f75, 220ee63).
- **lean-ctx** — approved as a direct server for Windsurf (matches the portable base template
  `ai/config/windsurf/mcp_config.base.json`) and for opencode/VS Code exposure, because these
  clients need the lean-ctx `instructions` payload and native-tool routing that the
  gateway-aggregated LeanCtx backend does not inject.

All other direct servers remain unapproved; the gateway stays the default path.

## 6. Consequences
- **Positive:** Massive reduction in token consumption for complex, multi-step tasks. Single source of truth for MCP configurations. Type-safe and sandboxed execution environment for agent scripts.
- **Negative:** Agents must learn to write Deno-compatible TypeScript to interface with the `pctx` sandbox, adding a slight learning curve (mitigated by custom Skills). Any failure in `pctx` impacts all connected agents.
