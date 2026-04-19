---
name: pctx-code-mode
description: Enforce pctx, Serena, Repomix, and batching conventions. Use this for tool-priority guidance, MCP code-mode batching, Serena-first exploration, and avoiding inefficient Bash/Grep/Read usage.
version: 1.0.0
triggers:
  - pctx code mode
  - tool priority
  - serena first
  - batching
  - mcp code mode
---

# pctx Code Mode

Use the shared tool-priority rules as the source of truth:

- `ai/rules/tool-priority.md`

When invoked, read that file and apply its pctx, Serena, Repomix, batching, and Bash-avoidance guidance. Keep this skill as a thin Codex-compatible loader stub so the shared rule remains neutral.
