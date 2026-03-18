---
name: Context & Token Management Strategy
overview: Comprehensive guide and configuration plan for effective token management across all IDEs (Cursor, Claude Code, Windsurf, Gemini, Codex) to minimize context rot and wastage.
todos:
  - id: install-rtk
    content: Install and verify RTK (rtk-ai/rtk) if not present
    status: pending
  - id: init-rtk-hooks
    content: Initialize RTK global hooks for Claude Code integration
    status: pending
  - id: verify-mcp-config
    content: Verify .cursor/mcp.json and .mcp.json have activtrak-sandbox configured
    status: pending
  - id: update-qmd
    content: Update qmd semantic search index
    status: pending
  - id: create-context-md
    content: Create a Context Management Cheatsheet (CONTEXT.md) summarizing these rules
    status: pending
isProject: false
---

# Context & Token Management Strategy

## 1. The Token Conservation Pyramid

Minimize token usage by following this strict hierarchy of tools:

1.  **Gemini CLI (Free Tier):** Use for *all* large-context read-only tasks (logs, docs, full file analysis). 1M token window at no cost.
2.  **Semantic/Symbolic Search:** Use `qmd` (docs/meaning) and `serena` (code symbols) instead of `grep` + `read`. Returns ranked chunks or specific definitions, saving thousands of tokens.
3.  **Compressed Shell Output:**
    *   **Cursor:** ALways use `rtk` prefix (e.g., `rtk cargo build`).
    *   **Claude Code:** `context-mode` hooks auto-compress output (do NOT use `rtk` prefix).
4.  **Batched MCP Calls:** Use `activtrak-sandbox` to bundle multiple MCP calls into one request, preventing raw JSON responses from flooding context.
5.  **Agent Delegation:** Route complex reasoning to Claude/Cursor Agent; mechanical tasks to Codex.

## 2. IDE-Specific Configurations & Workflows

### Cursor (Primary Editor)
*   **Shell:** Install `rtk` and ALWAYS use `rtk` prefix for `cargo` and `git` commands.
    *   *Setup:* `brew tap rtk-ai/rtk && brew install rtk` (or `cargo install rtk`).
    *   *Usage:* `rtk cargo check`, `rtk git status`. Saves 60-90% context.
*   **MCP:** Use `activtrak-sandbox` for multi-step tool use.
    *   *Pattern:* `search_tools` -> `execute_code` (batch calls) -> return summary.
*   **Reading:** Delegate files >200 lines to Gemini CLI (`cat file | gemini -p "Analyze..."`).

### Claude Code (Orchestrator)
*   **Shell:** Do NOT use `rtk` prefix. `context-mode` hooks automatically intercept and compress output via sandboxed execution.
    *   *Setup:* Run `rtk init --global` once to install the `PreToolUse` hook.
*   **Workflow:**
    1.  **Analyze:** Delegate to `gemini-analyzer` subagent.
    2.  **Plan:** Synthesize in Claude Code.
    3.  **Execute:** Delegate to `cursor-agent` subagent.

### Windsurf (Autonomous)
*   **Shell:** Use `rtk` prefix in the terminal for manual commands.
*   **MCP:** Configure `activtrak-sandbox` in `.windsurf/mcp_config.json`.
*   **Usage:** Best for long-running tasks on separate worktrees to avoid polluting main context.

### Gemini CLI (Analyst)
*   **Role:** Pure read-only analysis.
*   **Context:** 1M token window allows ingesting entire crate documentation or large diffs (`git diff | gemini -p "Review..."`).
*   **Setup:** Ensure `GEMINI_API_KEY` is set.

### Codex (Mechanic)
*   **Role:** Repetitive/mechanical tasks (boilerplate, tests, renames).
*   **Usage:** "Hey Codex, generate unit tests for this file." Zero Claude/Cursor credits used.

## 3. Tooling & Setup Checklist

1.  **Install RTK:** `brew install rtk` or `cargo install rtk`.
2.  **Initialize Hooks:** `rtk init --global` (enables Claude Code integration).
3.  **Update Semantic Index:** Run `qmd update --quiet && qmd embed --quiet` regularly.
4.  **Verify MCP:** Check `.cursor/mcp.json` and `.mcp.json` include `activtrak-sandbox`.

## 4. Context Hygiene Rules

*   **No Large Reads:** Never read `Cargo.lock` or files >100KB in full. Use `rg` or `read` with line ranges.
*   **Hyper-Atomic Commits:** Commit after *every* logical step. This allows clearing context ("forgetting" files) while safe in the knowledge that work is saved.
*   **Summarize Output:** If a tool returns >100 lines, summarize it before proceeding.
*   **Checkpoints:** Before switching tasks or IDEs, create a checkpoint (status, next steps) to allow a fresh start.