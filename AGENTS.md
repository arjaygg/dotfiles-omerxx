# Global agent instructions (this machine, all projects)

Canonical, tool-agnostic instructions for any coding-agent harness (Claude Code,
opencode, Cursor, Copilot, ...). Keep entries short — this loads in every session.

## Local CLIs

- **NotebookLM**: use the `nlm` CLI (installed at `~/.local/bin/nlm`) for any
  Google NotebookLM work — notebooks, sources, notes, queries. Run `nlm --ai`
  for agent-oriented docs of every command; `nlm login` handles auth/profiles.
  Prefer it over registering the notebooklm MCP server (the MCP variant costs
  per-session context; the CLI costs nothing until used).
