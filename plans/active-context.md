# Active Context

## Current Focus: Unified Agent Guidance Architecture (2026-03-23)

Branch `feat/unified-agent-guidance` implements the separation of shared agent guidance from dotfiles distribution files (ADL-002).

### Completed This Branch

1. **AGENTS.md**: New canonical shared guidance file — project purpose, working rules, source of truth, tool priority stack, batching rule, branch workflow, Serena convention, project structure, MCP gateway, plans/ convention.
2. **CLAUDE.md**: Slimmed to thin adapter (`@AGENTS.md` + Claude-specific notes).
3. **ai/rules/agent-user-global.md**: Created — user-global cross-agent defaults in one neutral file.
4. **.claude/CLAUDE.md**: Updated to import global rules via `@` directive.
5. **.gemini/GEMINI.md**: Slimmed to import global rules.
6. **.gemini/settings.json**: Added `context.fileName` block to load AGENTS.md.
7. **.codex/AGENT.md**: Slimmed to import global rules via `model_instructions_file`.
8. **docs/agent-configuration-architecture.md**: New — explains the two-layer model.
9. **docs/decision-records.md**: New — canonical convention for decision records.
10. **decisions/0002-…**: Durable ADR for this architectural separation.
11. **validate-agent-guidance.sh**: Structural validation script (14/14 passing).
12. **plans/decisions.md**: Created (this session) — ADL-001 through ADL-004.
13. **ai/rules/context-and-compaction.md**: Updated to reference durable decisions.

### Validation

All checks pass:
```
bash .claude/scripts/validate-agent-guidance.sh  → 14 PASS, 0 FAIL
```

### Next Steps

- Open PR for `feat/unified-agent-guidance` → `main`
- After merge: verify live adapter imports resolve correctly on machine
- Consider adding `.codex/config.toml` `model_instructions_file` symlink check to validation script
