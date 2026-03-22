# Integration Plan: pctx (Port of Context) for AI Agents

## 1. Background & Motivation
The current AI agent environment (Claude Code, Cursor, Windsurf, Gemini, Codex) relies on bash scripts, custom hooks, and specific Skills to automate workflows. While effective for static tasks, novel multi-step tasks often require sequential, turn-by-turn tool calls which rapidly exhaust the context window and hit rate limits.

[pctx (Port of Context)](https://github.com/portofcontext/pctx) is an open-source Model Context Protocol (MCP) gateway that enables "Code Mode" for AI agents. Rather than making multiple sequential tool calls, agents write a single TypeScript script that `pctx` executes securely within a Deno sandbox. 

**Value Proposition:**
- **Token Efficiency:** Reduces token usage by up to 98% by running logic (loops, conditionals) in a local sandbox rather than in the LLM context.
- **Dynamic Workflows:** Empowers agents to write and execute robust, type-checked scripts dynamically.
- **MCP Aggregation:** Consolidates multiple discrete MCP servers into a single gateway interface.

## 2. Scope & Impact
- **Impacted Systems:** Claude Code, Gemini CLI, Cursor, Windsurf, Codex.
- **Configuration:** Migration of individual MCP server definitions from agent-specific configs into a centralized `pctx` configuration.
- **Capabilities:** Unlocks bulk data processing and complex API orchestration without context bloat.

## 3. Proposed Solution & Architecture
To maximize the efficiency of "Code Mode" and prevent tool duplication, all individual MCP servers must be removed from the AI agents' configurations and migrated into the central `pctx` gateway. The AI agents will then be configured to connect exclusively to `pctx`.

1. **Centralized Gateway:** `pctx` acts as the master MCP gateway, hosting the connections to tools like `context7`, `filesystem`, and `exa`.
2. **Agent Configuration:** Agents connect solely to the `pctx` server. This forces the agents to utilize the `pctx` sandbox for complex operations.
3. **Behavioral Alignment:** A new global rule and skill will instruct agents to default to `pctx` Code Mode for any task involving looping, bulk extraction, or multiple API calls.

## 4. Phased Implementation Plan

### Phase 0: Workspace Isolation & Documentation
- **Isolate Changes:** Utilize the existing Charcoal + Worktree integration to create a dedicated stack branch.
  - Run: `~/.dotfiles/.claude/scripts/stack create feat/pctx-integration main --worktree`
  - Navigate: `cd .trees/pctx-integration`
- **Architectural Documentation:** Generate an Architecture Decision Record (ADR) in `decisions/0001-use-pctx-as-mcp-gateway.md` documenting the transition to a centralized MCP gateway.

### Phase 1: Creation of Specialized Subagents
Before executing the configuration migrations, the necessary specialized subagents must be created to ensure safe and efficient execution.
- **`mcp_config_manager` Subagent:** Create a new subagent specialized in safely parsing, manipulating, and validating JSON configuration schemas for various AI tools (`settings.json`, `mcp.json`, `config.toml`).

### Phase 2: Gateway Installation & Configuration
- **Install `pctx`:** Install the CLI globally (`npm i -g @portofcontext/pctx`).
- **Initialize Gateway:** Run `pctx init` to generate the root configuration.
- **Migrate Servers:** Transfer the existing MCP server definitions from project files and `.cursor/mcp.json` into the central `pctx` configuration.

### Phase 3: Agent Integration & Cleanup
Utilize the newly created `mcp_config_manager` subagent to perform parallel updates across the workspace:
- **Remove** the legacy, individual MCP server entries from the agent configs.
- **Inject** the unified `pctx` server configuration into:
  - Claude Code (`~/.claude/settings.json` or `.mcp.json`)
  - Cursor (`.cursor/mcp.json`)
  - Windsurf (`.windsurf/mcp_config.json`)
  - Codex (`.codex/config.toml`)
  - Gemini (`.gemini/mcp.json`)

### Phase 4: Hub Alignment & Skill Integration
- **Develop Skill:** Create `ai/skills/pctx-code-mode/SKILL.md`.
- **Define Triggers:** Establish triggers such as "process data", "batch process", "run a script".
- **Provide Instructions:** Document the schema of the `pctx` tool call and provide examples of writing Deno-compatible TypeScript for orchestrating downstream MCPs.

## 5. Task Execution & Capability Utilization
This plan leverages native concurrency and specialized delegation to ensure efficiency:
1. **Parallel Execution:** The `mcp_config_manager` subagent will be invoked concurrently to update Cursor, Windsurf, Claude Code, and Gemini configurations simultaneously without bottlenecking the main session.
2. **Background Processes:** The installation of the `pctx` package will run as a background shell command, allowing the main agent to concurrently draft the ADR and generate the `mcp_config_manager` subagent definition.
3. **Codebase Investigation:** The native `codebase_investigator` tool will be utilized at the onset of Phase 2 to accurately map all existing MCP configuration files scattered throughout the workspace.

## 6. Verification & Rollback
- **Verification:** Issue a multi-step data processing prompt (e.g., "Extract all headers from markdown files in the docs directory and compile a summary") and verify the agent utilizes a single TypeScript script via `pctx`.
- **Rollback:** In the event of latency or instability, remove the `pctx` entry from the agent configurations and restore the legacy individual MCP definitions using the `mcp_config_manager`.