# Active Context
We are currently integrating `pctx` (Port of Context) as the centralized MCP gateway to enable "Code Mode" (running Deno-compatible TypeScript scripts for complex multi-step tool calls).

We have successfully:
1.  **AI-Agnostic Subagents:** Created the `mcp_config_manager` subagent across all supported platforms (Claude Code, Gemini CLI, Cursor, Windsurf, OpenCode) to handle configuration migrations safely.
2.  **Built pctx from Source:** Resolved the Darwin x64 installation blocker by successfully building `pctx` v0.6.0 from source and installing it to `~/bin/pctx`.
3.  **Gateway Configuration:** Initialized and configured `pctx.json` with the primary upstream MCP servers (`serena`, `exa`, `sequential-thinking`).
4.  **Cross-Agent Adapter Alignment:** Migrated the repo-managed MCP entrypoints for Claude Code (`.mcp.json`), Cursor (`.cursor/mcp.json`), Gemini (`.gemini/mcp.json`), Windsurf (`.windsurf/mcp_config.json`), the generic workspace adapter (`mcp.json`), and Codex (`.codex/config.toml`) to the same working invocation: `pctx mcp start --stdio -c pctx.json`.
5.  **Migration Template Alignment:** Updated the `mcp_config_manager` templates across Claude, Cursor, Gemini, Windsurf, and OpenCode so future migrations use the same working `pctx` entrypoint.
6.  **Gateway Verification:** Confirmed `pctx mcp list -c pctx.json` successfully connects to `serena`, `exa`, and `sequential-thinking`, and verified via `claude mcp list` that the project-level `pctx` definition connects successfully.
7.  **Code Mode Verification:** Used the official `pctx-client` against a local `pctx start` session server and successfully executed a real TypeScript program that looped over multiple directories via `Serena.listDir`, returning structured results from Code Mode.

Execution rule for the remainder of this plan:
- Repo-tracked config changes must be completed and verified in this worktree before merge.
- Live machine-global MCP registrations that are not sourced from tracked dotfiles are post-merge rollout work, not pre-merge branch blockers.

Next, we will converge the live host state after this branch is merged by removing or replacing any remaining machine-global MCP registrations that still bypass the repo-managed `pctx` setup.
