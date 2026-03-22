# Active Context
We are currently integrating `pctx` (Port of Context) as the centralized MCP gateway to enable "Code Mode" (running Deno-compatible TypeScript scripts for complex multi-step tool calls).

We have successfully set up the worktree (`.trees/pctx-integration`), documented the architecture decision, created the `mcp_config_manager` subagent, added the `pctx-code-mode` skill to `@ai/skills/`, and migrated the local `mcp.json` and `.windsurf/mcp_config.json` to point to `pctx`. 

We have encountered a blocker installing the `pctx` CLI on Darwin x64, as the official npm package only supports `aarch64` (Apple Silicon) on macOS. We need to either build `pctx` from source or use a workaround. The global configs for Cursor, Claude Code, and Codex still need to be migrated once the `pctx` CLI is operational.