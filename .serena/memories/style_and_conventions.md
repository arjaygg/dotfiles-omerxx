# Style and Conventions

## Tool Priority (for AI agents — most important)
Use tools in this order. Stop at the first that works. Never Bash for file ops.

1. Serena (LSP-backed, gitignore-aware): listDir, searchForPattern, findSymbol, getSymbolsOverview
2. Native Claude Code tools: Grep tool (ripgrep), Glob, Read with limit/offset, Edit
3. Bash — ONLY for system commands with no dedicated tool (git, brew, stow, curl, etc.)

NEVER: Bash cat/grep/find/ls for project file operations.

## MCP Architecture
- All MCP traffic routes through pctx gateway
- Gateway config: /Users/agallentes/.config/pctx/pctx.json
- Servers: serena, exa, sequential-thinking, notebooklm, markitdown
- Serena uses --context claude-code (LSP tools only, no file mutation)
- Agent configs contain ONLY the pctx entry — nothing else

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
- 2+ Serena ops → batch into ONE pctx execute_typescript call
- 2+ Read/Grep/Glob ops (independent) → fire in parallel (single message)

## Serena API Convention
All methods use camelCase: listDir, searchForPattern, findSymbol, getSymbolsOverview,
listMemories, initialInstructions, writeMemory, readMemory
