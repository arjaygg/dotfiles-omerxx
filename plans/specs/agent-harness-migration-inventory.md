---
status: frozen
retry_count: 0
doubt_cycle_iteration: 0
review_loop_iteration: 0
followup_review_recommended: false
---

# Frozen Spec — agent-harness-migration-inventory

<intent-contract>
Produce a compact, evidence-backed inventory and migration-boundary recommendation for moving the reusable agent harness out of `/Users/axos-agallentes/.dotfiles` into `/Users/axos-agallentes/git/agent-harness`. The result must distinguish harness assets from personal dotfiles/client bootstrap, identify current user-scoped activation and safe temporary-disable points, and propose a project-local adoption boundary compatible with later plugin packaging. Do not edit implementation files.
</intent-contract>

## Task

Inspect the current repository and return decision-ready facts for the Coordinator's implementation plan:

1. Classify harness assets by category: rules/instructions, skills/commands/agents, hooks/enforcement, scripts/tests/evals, generated client config, and session/goal/decision scaffolding.
2. Identify the user-scoped activation/install paths, including `setup.sh`, symlinks, client entrypoints, settings, hooks, and generated config.
3. Identify machine-specific or dotfiles-specific coupling that cannot move unchanged.
4. Recommend the smallest safe temporary-disable mechanism that preserves ordinary Codex/Claude/client usability.
5. Recommend a staged extraction boundary and a future plugin-compatible package layout.
6. Name exact validation commands/tests already present for topology, hooks, config generation, and installation behavior.

Return a concise report with: inventory table, coupling/risks, proposed boundary, disable/rollback sequence, exact evidence paths, and unresolved decisions. Do not paste whole files or long command output.

## Files

- Read-only scope: `/Users/axos-agallentes/.dotfiles/**`
- Destination may be inspected only if it already exists: `/Users/axos-agallentes/git/agent-harness/**`
- No implementation edits.
- The only permitted write is the worker's final response; do not modify this spec or any repository file.

## Acceptance

- Every major harness category has representative exact paths and a move/keep/split recommendation.
- Current activation and temporary-disable paths are explicit and distinguish tracked source from live symlinks/generated state.
- Proposed boundary separates reusable harness core, client adapters, project-local policy, and personal/machine overlays.
- Future plugin packaging is treated as an interface constraint, not implemented now.
- Validation and rollback steps cite existing scripts/tests where available.
- Unknowns are clearly labeled rather than guessed.

## Constraints

- Fresh worker; initialize Serena and LeanCtx before repository access.
- Use LeanCtx/Serena for exploration; admit compact facts, not raw output.
- Do not spawn nested sub-agents.
- Do not edit, commit, branch, create a worktree, install, unlink, or disable anything.
- Planning-only task; preserve current user-scoped behavior.

## Spec Change Log

- 2026-08-03: Initial frozen specification.

## Review Triage Log

- None.
