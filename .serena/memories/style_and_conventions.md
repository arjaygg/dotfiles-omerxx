# Style and Conventions

## Tool Priority (for AI agents — most important)
Use tools in this order. Stop at the first that works. Never Bash for file ops.

1. Serena (LSP-backed symbols): findSymbol, findReferencingSymbols, getSymbolsOverview, readMemory
2. LeanCtx: ctxSearch, ctxGlob, ctxTree, ctxRead for text/file/tree access
3. Native Claude Code tools: Grep tool (ripgrep), Glob, Read with limit/offset, Edit
4. Bash — ONLY for system commands with no dedicated tool (git, brew, stow, curl, etc.)

NEVER: Bash cat/grep/find/ls for project file operations.

## MCP Architecture
- All MCP traffic routes through pctx gateway
- Gateway config: /Users/axos-agallentes/.config/pctx/pctx.json
- Servers (verified 2026-07-07): serena, qmd, lean-ctx, repomix, graphify
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
All exposed pctx SDK methods use camelCase: findSymbol, findReferencingSymbols,
getSymbolsOverview, listMemories, initialInstructions, writeMemory, readMemory.
Current pctx Serena does not expose listDir, findFile, or searchForPattern.
