# Goal 01 — Evaluate and optimize AI agent harness

## Objective

Evaluate and optimize the AI agent harness and primitives implementation in `~/.dotfiles/` so the agentic/loop-engineering system is more effective, efficient, deterministic, and cross-client consistent.

## Why

The repository is the source of truth for user-scoped AI client configuration, shared rules, skills, commands, hooks, MCP gateway setup, and symlinked runtime entrypoints. A rigorous harness audit should reduce configuration drift, context bloat, handoff friction, tool misuse, and ambiguous implementation loops across Claude, Codex, Gemini/Antigravity, Cursor, and Windsurf.

## Current state

- Repo root: `/Users/axos-agallentes/.dotfiles`.
- Existing guidance says shared primitives live under `ai/` and client-specific files should stay thin.
- Active context and progress are tracked in `plans/active-context.md` and `plans/progress.md`.
- Prior related artifacts include `plans/2026-06-12-ai-primitives-upgrade.md`, `plans/2026-07-07-ai-harness-improvement-proposal.md`, `plans/2026-07-08-constitution-hooks-audit.md`, and `plans/2026-07-13-execution-plan.md`.
- Current branch observed while authoring this goal: `main...origin/main [ahead 1]`; do not commit directly to `main`.
- No project-local `goals/README.md` existed when this goal was created, so the repository fallback goal convention was used.

## Execution status (2026-07-15)

- Status: completed for the bounded Codex slice on `feature/codex-config-proposals`.
- The baseline/report, ADR, proposal generator, security hardening, Gate 1 overlay/comparison, and
  Gate 2 backup/rollback preflight are complete and verified.
- The portable Codex base was corrected from the obsolete top-level `[status_line]` table to the
  official `[tui]` `status_line` setting. The official config reference and `codex features list`
  confirm the current schema and live parse.
- Gate 1 created the minimal ignored `~/.config/dotfiles-ai/codex.overlay.toml` with mode `0600`;
  no prior overlay existed.
- The final base-plus-overlay comparison against the live config reported zero changed paths. Both
  hashes were valid, while the proposal and target byte hashes differed because the proposal uses
  deterministic canonical rendering.
- The live `~/.codex/config.toml` SHA-256 remained unchanged, and the live config was not written.
- The deterministic printable proposal remains valid and repeatable at SHA-256
  `bf13bdf914a7b28504e262183fd1a65182d560243e524efb44c94dbbdf7db280`.
- The plan-focused suite remains 49 of 49. Full discovery remains 85 with one unrelated failure
  caused by the absent ignored `.claude/settings.local.json`; public hygiene remains 390 findings,
  and config doctor remains 65 issues.
- The earlier five-path comparison remains historical synthetic evidence and is superseded by the
  actual Gate 1 zero-path comparison.
- Independent review remains clean for the bounded code scope.
- Gate 2 preflight created private backup directory
  `~/.config/dotfiles-ai/backups/20260715T002308Z-pre-codex-gate2` with mode `0700`. Its exact live
  backup, generated candidate, manifest, and rollback instructions each have mode `0600`.
- The backup hash equals the current live hash. The candidate byte hash differs, but the semantic
  changed-path count is zero.
- The candidate TOML parsed, an isolated `CODEX_HOME` Codex parse passed, and the candidate remained
  unchanged.
- A sandbox rollback dry-run restored the candidate to the exact original-live hash.
- Live bytes, hash, and metadata remained unchanged; no runtime apply occurred.
- Final Gate 2 decision: skip the semantically no-op live rewrite and close the bounded Codex slice.
  The zero-path semantic comparison did not justify a canonical-format-only runtime mutation, so no
  live runtime write occurred.

## Non-goals

- Do not implement live runtime, permission, hook, symlink, or machine-wide config changes before the user aligns on the plan.
- Do not weaken existing hard-denies, safety gates, branch protections, credential hygiene, or production/live-action approval requirements.
- Do not duplicate durable policy across multiple tool-specific entrypoints unless the tool requires a loader stub.
- Do not replace shared `ai/rules/`, `ai/skills/`, `ai/commands/`, or `ai/output-styles/` source-of-truth files with unmanaged client-local copies.

## Steps

1. Initialize repository context with the available MCP/context tools and record any unavailable session-init primitives as explicit audit evidence.
2. Map global architecture by reviewing `docs/agent-configuration-architecture.md`, `AGENTS.md`, `ai/rules/agent-user-global.md`, and `ai/rules/tool-priority.md`.
3. Map client-specific entrypoints and symlinked runtime config:
   - Claude: `CLAUDE.md`, `.claude/settings.json`, and `.claude/hooks/`.
   - Codex: `.codex/config.toml` and related configuration.
   - Gemini/Antigravity: `.gemini/settings.json` and `.gemini/mcp.json`.
   - Cursor: `.cursor/mcp.json` and `.cursor/commands/`.
   - Windsurf: `.windsurf/mcp_config.json`.
4. Audit core autonomous primitives and skills, including `cap`, `stark`, `ironman`, `fury`, `hawk`, `strange`, and adjacent orchestrator/review/debug/test skills.
5. Evaluate context gateways and tool routing for `pctx`, LeanCtx, Serena, QMD, Repomix, and Graphify.
6. Produce a cross-client parity matrix showing which constraints, tool priorities, MCP servers, commands, hooks, and shared rules are enforced in each client.
7. Identify loop inefficiencies:
   - client drift;
   - context leaks or unnecessary context loading;
   - weak structured-memory handoff between agents/subagents;
   - role handoff friction between planner, implementer, tester, reviewer, and debugger primitives;
   - raw shell/grep/find fallback where semantic or token-efficient tooling should be used.
8. Recommend concrete enhancements that keep tool-specific entrypoints thin and delegate to shared `ai/rules/` and `ai/skills/`.
9. Draft `decisions/NNNN-agentic-loop-optimization.md` with the proposed structural improvements, alternatives, risks, and migration plan.
10. Present the implementation plan and stop for user alignment before changing live runtime behavior or broad policy.
11. After alignment, implement approved optimizations in focused branches/worktrees, updating primitive scripts, config files, rules, skills, tests, docs, and verification evidence as needed.
12. Verify the optimized loop with concrete evidence: config generation/parsing checks, hook simulations, symlink/source-of-truth checks, rule/skill reachability checks, and documented before/after findings.

## Acceptance criteria

- A harness map exists in a plan or report under `plans/` and covers all files and client categories named in this goal.
- A cross-client parity matrix explicitly compares Claude, Codex, Gemini/Antigravity, Cursor, and Windsurf.
- Findings distinguish verified evidence from inference and list what was checked and not yet checked.
- Bottlenecks are grouped by client drift, context bloat/leaks, handoff friction, and tool inefficiency.
- Recommendations include concrete file-level changes and identify whether each change affects shared source, client entrypoints, hooks, MCP config, skills, commands, or docs.
- `decisions/NNNN-agentic-loop-optimization.md` is drafted before implementation and linked from active-session notes when accepted.
- No implementation begins until the user approves the plan or explicitly authorizes a bounded subset.
- Approved implementation uses branch/worktree workflow rather than committing directly to `main`.
- Verification proves more than command exit status: parsed configs, simulated hooks, symlink/source-of-truth checks, and before/after parity evidence are captured.
- `plans/active-context.md` and `plans/progress.md` are updated if this goal becomes active execution work.

## Evidence to update

- `plans/active-context.md`
- `plans/progress.md`
- `plans/decisions.md`
- `plans/<date>-agentic-loop-optimization.md` or equivalent audit report
- `decisions/NNNN-agentic-loop-optimization.md`
- Any changed shared source files under `ai/rules/`, `ai/skills/`, `ai/commands/`, `ai/output-styles/`
- Any changed client entrypoints under `.claude/`, `.codex/`, `.gemini/`, `.cursor/`, `.windsurf/`
- Verification outputs or summaries for config parsing, hook simulation, symlink checks, and parity checks

## Stop and ask if

- Any proposed change would alter live runtime behavior, permission prompts, hard-denies, branch protection, or symlink targets.
- Any task requires touching secrets, credentials, tokens, private keys, or machine-local sensitive files.
- The audit suggests editing more than three files and scope has not been declared.
- The next step would commit, push, create a PR, merge, or modify `main`.
- Cross-repo changes are needed outside `/Users/axos-agallentes/.dotfiles`.
- A client-specific limitation requires duplicating shared policy instead of delegating to `ai/`.
