# Codex User Instructions

@../ai/rules/agent-user-global.md
@../ai/rules/tool-priority.md
@../ai/rules/context-and-compaction.md
@../ai/rules/delegation-and-context-admission.md

## Codex-Specific Notes

- Project rules belong in each repository's `AGENTS.md` and `.codex/rules/`.
- Hooks and settings enforce policy; this file remains a thin shared-rule adapter.
- The imports above are repo-relative and are asserted by
  `scripts/guidance_adapter_check.py`. Do **not** rewrite them as `@rules/...`:
  that form only resolves in the installed `~/.codex/` location. The template for
  the live user-global file is `ai/config/codex/AGENTS.global.base.md`.
