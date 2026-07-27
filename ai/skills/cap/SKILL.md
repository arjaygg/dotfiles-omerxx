---
name: cap
description: >
  Cap v4.1 — One-shot autonomous orchestrator for Go, Python, and TypeScript. Drives stark
  (plan) → fury (tests) → ironman (implement) → hawk (review). Uses Claude Code
  Workflows when that primitive is available, otherwise runs the same phases through a
  portable sequential fallback for agents such as Codex. Enforces TDD, Lean-Agile, DDD, SOLID,
  Evolutionary Architecture. Auto-detects language from project files (go.mod → Go,
  pyproject.toml → Python, tsconfig.json → TypeScript, multiple → polyglot).
  Use for: "build this feature", "implement end to end", "orchestrate this", "run cap",
  "full TDD cycle", "automate the workflow", "multi-agent workflow". NOT for planning-only,
  tests-only, implementing-only, or review-only requests — cap runs those phases inline
  (the standalone /stark, /fury, /ironman, /hawk skills are enabled per-project via
  skillOverrides — do not assume they are available or disabled; cap does not need them).
triggers:
  - /cap
  - orchestrate
  - subagent driven development
  - multi-agent workflow
  - build this feature
  - implement end to end
  - run the full workflow
  - full TDD cycle
  - build and test
  - implement the whole thing
  - automate the workflow
  - cap workflow
  - do the full feature
  - stark fury ironman hawk
version: 4.1.0
model: sonnet
---

# Cap v4.1 — Adaptive Autonomous Orchestrator

Cap orchestrates the full development pipeline with the best primitive available in the
current coding agent.

- **Claude Code with Workflow support:** use the Workflow path for deterministic orchestration,
  retries, schema-validated handoffs, pipeline Hawk review, adversarial verify, resumability,
  and `/workflows` visibility.
- **Agents without Workflow support, including Codex:** use the portable path. Run the same
  Cap phases directly with the agent's native tools or subagents. Do not call `Workflow`,
  `advisor`, or `PushNotification` when those primitives are not available.

## Activation

Trigger on the phrases and slash command listed in `triggers:` above. NOT for planning-only,
tests-only, implementing-only, or review-only requests — cap runs those phases inline.

## Conventions

Cap's workflow is decomposed into step files, read and executed one at a time — this keeps a
phase-1 invocation's context cost to `SKILL.md` + `step-01.md` rather than the full sequence.
If a step says read fully and follow step-XX, you read and follow step-XX. No exceptions.

- Use the numbered `step-01.md` through `step-05.md` sequence for normal runs.
- Use `step-oneshot.md` instead when the full step-by-step cadence is overkill (small,
  well-understood feature, or a host that cannot hold multi-file skill state).

## Next

Read fully and follow **step-01.md** (Parse Arguments & Select Runtime).
