# AI Agent Primitives

This directory is the authoritative source for common AI Agent primitives (rules, skills, commands, and output-styles) shared across all AI agents on this machine.

## Supported Agents

The following agents are configured to honor these primitives through granular symlinking into their respective home configuration directories:

- **Claude Code:** `~/.claude/`
- **Gemini CLI:** `~/.gemini/`
- **Codex CLI:** `~/.codex/`
- **Cursor:** `~/.cursor/`
- **Windsurf:** `~/.windsurf/`

## Structure

- `commands/`: Shared command definitions (e.g., smart-commit).
- `output-styles/`: Shared personas and formatting styles (e.g., technical-lead).
- `rules/`: Global and project-level constraints.
- `skills/`: Modular, executable agent capabilities.

## Setup & Maintenance

The primitives are linked granularly from this directory into the agent-specific folders. This ensures that a single update to a rule or skill in this repository is immediately reflected across all AI tools.

- **Source:** `~/.dotfiles/ai/`
- **Link Strategy:** Granular symlinking of individual files and directories.
- **Codex Skills:** User-scoped Codex skills live in `~/.codex/skills/`. `setup.sh` links every skill with a `SKILL.md`/`skill.md` manifest from `~/.dotfiles/ai/skills/` into that directory and preserves Codex-managed folders such as `~/.codex/skills/.system`. Any Claude-local skill that has not yet been promoted into `ai/skills/` is linked into Codex only if the name is not already present.

### Cursor Auto-Loading

**Cursor** has automatic rule loading configured through `~/.cursor/rules.md`, which aggregates all dotfiles AI rules into user-level context for every session.

**Setup:**
1. Rules are symlinked: `~/.cursor/rules/` → `~/.dotfiles/ai/rules/`
2. Aggregator file `~/.cursor/rules.md` imports all rules using `@path` syntax
3. Cursor automatically loads `rules.md` as user-level context in each session

**Active Rules:**
- **Tool Priority Stack**: Serena/pctx integration, lean-ctx methods, batching requirements
- **User-Global Defaults**: Concise communication, git safety, file discipline
- **Developer Guidelines**: Git worktree management, parallel development patterns
- **Context Management**: Session artifacts, compaction rules

**Verification:** Start a new Cursor session to activate the updated rule set. The sophisticated tool priority stack (Serena.listDir, execute_typescript batching, etc.) will be enforced automatically.
