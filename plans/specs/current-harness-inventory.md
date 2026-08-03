---
status: frozen
retry_count: 0
doubt_cycle_iteration: 0
review_loop_iteration: 0
followup_review_recommended: false
---

# Frozen Spec — current-harness-inventory

<intent-contract>
Produce an activation-aware inventory of the harness from executable/configured sources only, so
the Coordinator can distinguish real mechanisms from unreferenced assets and duplicated policy.
</intent-contract>

## Task

Within the worktree, inventory the current harness control plane and delivery loop: client adapters,
prompt/rule/skill/agent assets, hooks, settings/config generators, MCP registrations, setup/symlink
installation, orchestration, git lifecycle, context/compaction, and policy enforcement. Trace how
each surface is activated. Identify single sources of truth, generated projections, duplicate
implementations, unreferenced/orphan assets, and mechanisms whose declared route has no executable
consumer. Return facts with file-and-line or command evidence.

## Files

- Worktree root: `/Users/axos-agallentes/.dotfiles/.trees/agent-factory-gap-plan`
- In scope: `AGENTS.md`, `CLAUDE.md`, `setup.sh`, `.claude/`, `.codex/`, `.cursor/`, `.gemini/`,
  `.windsurf/`, `.opencode/`, `ai/`, `scripts/`, `evals/`, root config/manifests.
- Excluded as evidence: `docs/`, `decisions/`, `goals/`, and all existing `plans/` except this spec.

## Acceptance

- Returns an activation graph/table: capability → source → loader/consumer → enforcement mode.
- Classifies every major surface as active, generated, dormant, orphaned, duplicated, or unknown.
- Quantifies material duplication and complexity where commands can establish counts.
- Names likely redundancy/obsolescence with evidence and confidence, not filename intuition.
- Reports unresolved questions and the shortest executable check that would answer each.
- Makes no edits and returns a compact synthesis rather than raw listings.

## Constraints

- Read-only: do not edit any file.
- Run Serena `initial_instructions` and LeanCtx task scoping before file access.
- Use LeanCtx/Serena for discovery; exact/raw output for quotes, counts, and line references.
- Operational prompt Markdown under `ai/rules`, `ai/skills`, `ai/agents`, and client adapters counts
  as executable configuration; narrative docs/plans do not.
- Do not spawn nested subagents.

## Spec Change Log

- 2026-08-03: Initial frozen scope.

## Review Triage Log

- None.
