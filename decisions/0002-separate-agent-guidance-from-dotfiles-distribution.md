# Architecture Decision Record: Separate Agent Guidance from Dotfiles Distribution

## 1. Title
Separate shared agent guidance from tool-specific dotfiles distribution files

## 2. Status
Accepted

## 3. Context
This repository serves two roles at once:

1. It is a dotfiles repository that installs and maintains user-scoped configuration for multiple AI coding agents.
2. It is a project repository that needs shared guidance for how agents should work within it.

Storing shared behavioral policy directly inside tool-specific config directories (`.claude/`, `.gemini/`, `.codex/`) makes the source of truth unclear. It also couples project guidance to installation-specific files and increases duplication across agents.

## 4. Decision
We will separate the repository into two conceptual layers:

- Dotfiles distribution layer: tool-owned config, hooks, and setup files
- Project guidance layer: neutral, human-maintained docs such as `AGENTS.md`, `docs/`, `decisions/`, and `plans/`

User-global cross-agent defaults will live in one neutral markdown file, `ai/rules/agent-user-global.md`. Tool-specific files will become thin adapters that load the shared defaults or point to the project guidance layer.

## 5. Consequences
- **Positive:** One shared user-global rules file can be reused across agents. Project policy becomes easier to locate and review. Tool-specific files stay smaller and more maintainable.
- **Positive:** The dotfiles repo more clearly reflects its purpose as a configuration distribution system.
- **Negative:** Instruction loading now depends on a documented precedence model and adapter files, so validation is required to catch drift.
- **Negative:** Some tools still require their own entrypoint files, so complete elimination of adapters is not possible.
