# Agent User-Global Defaults

These rules are the user-global baseline for AI coding agents on this machine.

## Scope

- This file is for machine-wide defaults that should apply across repositories.
- Project-specific policy belongs in each repository's `AGENTS.md`, `CLAUDE.md`, or equivalent project docs.
- Tool-specific enforcement belongs in tool settings, hooks, wrappers, and MCP configuration.

## Working Style

- Prefer concise, direct communication.
- Make decisions explicit when tradeoffs matter.
- Prefer concrete verification over assumption when local inspection can answer the question.
- Treat tracked policy documents as higher priority than agent-generated memory.

## Git And Change Safety

- Do not use destructive git commands unless explicitly requested.
- Do not revert unrelated user changes.
- Prefer non-interactive git commands.
- For non-trivial changes, prefer isolated branches and worktrees.

## File And Tool Discipline

- Prefer dedicated tools over shell fallbacks when the client provides them.
- Keep edits minimal and targeted.
- Do not duplicate the same policy across multiple agent-specific instruction files unless a tool requires a loader stub.

## Dotfiles Repositories

When working in a dotfiles repository:

- Distinguish between shared project guidance and tool-specific installation files.
- Treat files under `.claude/`, `.gemini/`, `.codex/`, and similar directories as configuration distribution artifacts unless the file is clearly a project guidance entrypoint.
- Preserve symlink-based setup expectations.

## AI Agent Primitives Configuration

This machine uses a unified AI configuration strategy where common primitives are managed centrally in `~/.dotfiles/ai` and symlinked to each agent's configuration directory.

- **Centralized Source:** `~/.dotfiles/ai/`
- **Linked Agents:** Claude Code, Gemini CLI, Codex, Cursor, Windsurf.
- **Maintenance:** Any changes to rules, skills, commands, or styles should be made in `~/.dotfiles/ai/` and will be automatically reflected across all tools.

## Git Worktree Conventions

Worktrees live at `.trees/<description>/` with branch names `<type>/<description>`.

### Supported branch types
- `feature/` or `feat/`, `bugfix/` or `fix/`, `hotfix/`, `release/`, `chore/`

### Determine branch type from intent
- **feature/feat**: add, implement, create, build, new feature
- **bugfix/fix**: bug, fix, resolve, repair, correct
- **hotfix**: urgent, critical, security, emergency
- **release**: release, version, v1.0, v2.0
- **chore**: docs, cleanup, update dependencies

If unclear, default to `feature/`.

### Branch naming rules
- Use lowercase letters, numbers, and hyphens only (dots allowed for release versions)
- No consecutive, leading, or trailing hyphens or dots
- Use hyphens to separate words (e.g., `feature/add-user-login`)

### When asked to "create a worktree"
1. Sanitize the description (lowercase, spaces→hyphens, strip special chars, collapse hyphens, trim).
2. Ensure `.trees/` exists.
3. Create: `git worktree add -b "<type>/<description>" ".trees/<description>" <base-branch>`
4. Copy essential config files (`.env`, `.vscode/`, `.claude/`, `.serena/`, `.mcp.json`, `.cursor/mcp.json`) — update `--project` paths to point to worktree.
5. Print next steps: `cd .trees/<description>`, `git status`, `git branch --show-current`

### When asked to "remove a worktree"
- Verify clean state first (`git -C <path> status --short`).
- Do NOT remove if uncommitted changes unless explicitly told to proceed.
- Remove with `git worktree remove <path>`, optionally delete branch.

## Unified AI Hub Structure

All AI primitives are managed in the `ai/` directory:
- **Skills**: `ai/skills/`
- **Commands**: `ai/commands/`
- **Styles**: `ai/output-styles/`
- **Rules**: `ai/rules/`
