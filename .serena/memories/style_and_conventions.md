# Style and Conventions

## Tool Priority (for AI agents — most important)
Use tools in this order. Stop at the first that works. Never Bash for file ops.

1. Serena (LSP-backed symbols): findSymbol, findReferencingSymbols, getSymbolsOverview, readMemory
2. LeanCtx: ctxSearch, ctxGlob, ctxTree, ctxRead for text/file/tree access
3. Native Claude Code tools: Grep tool (ripgrep), Glob, Read with limit/offset, Edit
4. Bash — ONLY for system commands with no dedicated tool (git, brew, stow, curl, etc.)

NEVER: Bash cat/grep/find/ls for project file operations.

## MCP Architecture
- Each client registers its MCP servers directly; no gateway (decisions/0017)
- Servers: serena, lean-ctx, repomix, graphify
- Serena uses --context claude-code (LSP tools only, no file mutation)
- Verify topology: python3 scripts/mcp_topology_check.py --summary

## Symlink Management
- All agent configs are symlinks pointing into ~/.dotfiles/
- setup.sh creates/updates all symlinks
- Never edit configs in ~/.cursor/, ~/.gemini/, ~/.codex/, ~/.windsurf/ directly
- Edit the dotfiles version; the symlink makes it effective immediately

## Branch Rules
- NEVER commit to main
- Use: stack create <name> main (via Charcoal + stack scripts)
- Branch naming: feat/, fix/, chore/ prefixes
- The pre-tool-gate.sh hook warns on git commit to main

## Batching Rule
Before any tool call accessing the project:
"What else will I need in the next 3 steps?"
- 2+ Serena ops (independent) → fire in parallel (single message)
- 2+ Read/Grep/Glob ops (independent) → fire in parallel (single message)

## Serena API Convention
Serena is a direct MCP server, so tools use native snake_case: find_symbol,
find_referencing_symbols, get_symbols_overview, list_memories, initial_instructions,
write_memory, read_memory.
The claude-code context does not expose list_dir, find_file, or search_for_pattern.
