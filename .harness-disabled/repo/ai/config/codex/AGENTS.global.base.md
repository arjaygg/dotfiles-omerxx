# Codex Agent Instructions

<!--
  TEMPLATE / SOURCE OF TRUTH for the live `~/.codex/AGENTS.md`.

  It lives under ai/config/codex/ rather than at .codex/AGENTS.md because that
  path is an IN-REPO adapter governed by scripts/guidance_adapter_check.py,
  which requires `@../ai/rules/...` imports resolving inside the repo. A
  template needs `@rules/...` paths that resolve in the INSTALLED location, so
  the two roles cannot share one file. Conflating them broke
  test_guidance_adapter_check.py; see decisions/0022.

  setup.sh installs this bootstrap-if-absent — it does NOT symlink it. Until
  2026-08-03 setup.sh ran `ln -sfn .codex/AGENTS.md`, wrong for the same reason
  `settings.json` and `CLAUDE.md` are not symlinked (decisions/0016, 0020): the
  lean-ctx binary regenerates its block in the LIVE file, replacing it and
  breaking the link. The live file had already diverged to 2268 bytes against
  the adapter's 316, so re-running setup.sh would have overwritten it.

  `@rules/...` below resolves against `~/.codex/rules/`, which setup.sh
  populates with per-file symlinks into `ai/rules/`.

  config-integrity.sh warns when live and template diverge. Change both.
-->

This file is the user-global Codex entrypoint for this machine.

## AI Agent Primitives

The rules, skills, commands, and output-styles for Codex CLI are managed centrally in `~/.dotfiles/ai/` and granularly symlinked into `~/.codex/`.

- **Rules:** `@rules/agent-user-global.md`, `@rules/tool-priority.md`, `@rules/context-and-compaction.md`, `@rules/delegation-and-context-admission.md`
- **Source:** `/Users/axos-agallentes/.dotfiles/ai/`

## Delegation & Model Routing (read first)

The main session is the **Coordinator (the brain)** and runs `gpt-5.6-sol`. It owns intent,
plans/specs, architecture and security decisions, review, synthesis, and the final answer. To limit
context bloat and context rot, admit decision-ready facts—not raw search results, whole-file reads,
logs, build output, or repetitive edit history.

**Delegate by default** when work is separable, mechanical, discovery-heavy, verbose, spans 3+
files, or can run independently. Prefer fresh subagents; fork only when conversation-only state is
indispensable. Give each worker a bounded frozen spec and require compact evidence/results rather
than raw material.

Choose the **cheapest model likely to complete and verify the spec**:

- `gpt-5.4-mini`: pure extraction, existence checks, and deterministic trivial work.
- `gpt-5.6-luna`: default worker for searches, mechanical edits, boilerplate, docs, tests, builds,
  and log triage.
- `gpt-5.6-terra`: implementation, debugging, or refactoring that needs real judgement.
- `gpt-5.6-sol`: keep on the Coordinator; use as a worker only for evidenced escalation or genuinely
  frontier-level reasoning.

Accept a modest capability tradeoff for low-risk, machine-verifiable work, never for ambiguous or
high-stakes work. If a cheap worker fails, sharpen the spec and retry once before escalating exactly
one tier.

- **Roles, frozen spec (`plans/specs/<label>.md`), anti-nesting, fresh-vs-fork:**
  `@rules/agent-user-global.md` §§ Orchestrator-Worker Paradigm / Agent Spawning.
- **Tier table and enforcement status:** `~/.dotfiles/ai/skills/model-routing/SKILL.md` § Codex.
- **Context admission, delegation triggers, return contract, escalation ladder:**
  `@rules/delegation-and-context-admission.md`.

A spawn is **denied** on an unsupported model slug or a referenced-but-missing spec file
(`.codex/hooks/pre-agent-gate.sh`); an unset tier and an unreferenced spec produce warnings.

## Project-Specific Notes

- Project-specific guidance should come from each repository via `AGENTS.md`.
- Codex configuration is primarily in `~/.codex/config.toml`.

<!-- lean-ctx -->
<!-- /lean-ctx -->
