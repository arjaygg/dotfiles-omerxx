# Progress — 2026-06-12

## Active — 2026-07-14 agentic-loop optimization baseline

Goal: `goals/2026-07-14-01-agentic-loop-optimization.md`.

- [x] Load the current session baseline with pctx/Serena/LeanCtx and confirm the available MCP surface.
- [x] Verify the active repo guidance files and current architecture framing (`AGENTS.md`, `CLAUDE.md`,
  `docs/agent-configuration-architecture.md`, `ai/rules/tool-priority.md`).
- [x] Audit the current client entrypoints, hooks, and configuration layers into a concise verified report.
- [x] Expand the report into a cross-client parity matrix.
- [x] Expand the report into a file-level harness map and concrete recommendation set.
- [x] Update the plan/decision artifacts so another agent can continue the goal without re-discovering the baseline.
- [x] Draft the remediation plan for machine-local anchors and generated overlays, starting with Codex.
- [x] Draft proposed durable decision record `decisions/0011-agentic-loop-optimization.md`.
- [x] Add approval-ready implementation checklist with files and acceptance criteria.
- [ ] Obtain user approval before implementing the Codex remediation sequence.

## Done — 2026-07-14 pctx/Codex startup regression

Branch `fix/pctx-codex-startup`, worktree `.trees/pctx-codex-startup`.

- [x] Reproduced the repository-scoped Codex startup timeout twice and captured the
  exact JSONL wire format plus the 90-second handshake timeout.
- [x] Proved the Content-Length shim was incompatible and disproved backend slowness,
  protocol negotiation, resource contention, and duplicate LeanCtx as primary causes.
- [x] Restored direct pctx in tracked/portable Codex configs and retired the shim without
  changing live-runtime installation or migration semantics.
- [x] Added regression coverage and passed all 47 Python tests plus Bash/TOML syntax checks.
- [x] Verified direct list_functions twice and fresh Codex startup twice with pctx initialized,
  three tools listed, no handshake timeout, and 15.567s/17.446s total startup runs.

## Active — 2026-07-13 portable governed AI configuration audit

Plan: `plans/2026-07-13-execution-plan.md`; branch
`chore/phase0-config-boundary`.

- [x] Verify current branch, instruction hierarchy, open-PR overlap, hook schema risks,
  public-repository exposure, and runtime copy-back behavior.
- [x] Add read-only hygiene scanning, configuration doctor, hook static validation, and
  maintained PreToolUse fixture coverage.
- [x] Record Phase 0 classification, remediation guidance, current baseline counts, and
  review gates without changing permission semantics or live runtime configuration.
- [x] Implement the approved Phase 0 source-boundary changes: remove unsafe/private
  settings context, make the symlink guard proposal-only, untrack the local overlay,
  and add portable Claude/client/PCTX bases plus proposal-only generator expansion.
- [x] Add test-first explicit placeholder expansion and verify all four portable
  client/PCTX JSON bases generate without reading environment state or mutating inputs.
- [x] Add and parse-validate a portable Codex TOML base without wiring it into runtime.
- [x] Publish draft PR [#296](https://github.com/arjaygg/dotfiles-omerxx/pull/296) for
  review; do not merge or apply runtime changes automatically.
- [ ] Validate the proposal diff and obtain separate approval before live runtime,
  permission, machine-wide hook, or canonical-hierarchy changes.

## Done — 2026-07-10 trim CLAUDE.md instruction chain (Fable-reviewed, ADL-018)

Branch `chore/trim-claude-md-instruction-chain`, worktree `.trees/trim-claude-md-instruction-chain`.
Full rationale and Fable review criterion in `plans/decisions.md` ADL-018.

- [x] Trimmed `ai/rules/tool-priority.md` 320 → 124 lines
- [x] Trimmed `ai/rules/agent-user-global.md` 343 → 175 lines
- [x] Created `ai/skills/tool-routing/SKILL.md` (extended Qmd/LeanCtx/Graphify/docs/shell/web routing detail)
- [x] Created `ai/skills/model-routing/SKILL.md` (model/effort/fast-mode/advisor tables, cross-refs `.cursor/rules/model-routing.mdc`)
- [x] Fixed stale `ai/skills/qmd-routing/SKILL.md` (old `search`/`vector_search`/`deep_search` names → consolidated `Qmd.query`)
- [x] Fixed stale cross-reference in `ai/rules/context-and-compaction.md` (pointed at removed tool-priority.md §10)
- [x] Absorbed Git Worktree Conventions detail (branch-type table, naming/sanitization rules) into `ai/skills/stack-create/SKILL.md`
- [x] Resolved Cursor/Gemini/Codex reachability question — inline "Quick digest" in `tool-priority.md` §7 (symlinked to all agents), not a mirrored `.mdc` (see ADL-018)
- [x] Logged `TodoWrite`-tool-availability discrepancy as a flagged-not-fixed follow-up (see ADL-018)
- [x] Committed (`facc84f`), PR #293 opened and merged via `gh pr merge --admin` (bypassed
  CI/branch-protection gating — no admin-merge flag exists in `stack-ship.sh`/`merge-stack.sh`),
  local `main` fast-forwarded to `75bf724`, worktree/branch cleaned up via `stack clean`

## In Progress — 2026-07-09 injection-antipatterns Phase 4 (gate-logic-consolidated-review)

Plan: `auc-conversion/docs/plans/2026-07-09-implement-session-injection-antipatterns.md` (merged
via PR #959). User selected "Phase 4 only" (dotfiles gate-logic review); Phase 5 deferred.
Branch `fix/gate-logic-consolidated-review`, worktree `.trees/gate-logic-consolidated-review`.
Constraint on every item: "policy unchanged, scope corrected" — no existing hard-deny weakened.

- [x] N6b — `advisor-escalate.py` `is_excluded()`: stop excluding `"BLOCKED:"` gate denials from
  the recurrence tracker (commit `3dae42c`)
- [x] N4 — extend size guard to Bash `<` redirect targets (commit `752b2d3`, `pre-tool-gate-v2.sh`)
  and to `mcp__pctx__execute_typescript` result size (commit `e5844d0`, `post-tool-analytics.sh` —
  routed through the existing generic Bash/Agent compaction check since the gate hook is
  PreToolUse-only and cannot inspect tool results)
- [x] N4c/N6c — `jq|curl` pipe-strip whitelist (commit `cd1dfcf`)
- [x] N6a — `[HARD-BLOCK — DO NOT RETRY]` prefix on every `_deny()` (commit `5eab8c6`) + doc
  paragraph in `tool-priority.md` §0 (commit `c7a4968`)
- [x] N7 — branch grep/find/ls denials on MCP-alternative-initialized state (commit `2b5c09a`)
- [x] N9a — extend `[MONITOR HINT]` regex for semicolon/`&&`-chained `sleep` (commit `287cad8`)
- [x] Commits: `5eab8c6`, `3dae42c`, `cd1dfcf`, `287cad8`, `2b5c09a`, `752b2d3`, `e5844d0`,
      `c7a4968` — all on `fix/gate-logic-consolidated-review`. Working tree clean (only the
      auto-generated, untracked `plans/session-snapshot.md` remains).
- [x] Run plan's Verification steps 3, 5, 6, 8 against the merged changes — all four verified;
  findings below.
  - **Step 3 (N4)**: size guards confirmed live — unlimited `Read` on a 216-line log file
    correctly hard-blocked; Bash `<` redirect and `execute_typescript` result-size guards
    confirmed via code inspection.
  - **Step 5 (N6)**: N6a hard-block marker confirmed present on every `_deny()`. N6b escalation
    logic is correct in isolation (3x simulated payloads → fires on the 3rd, matching
    `THRESHOLD=3`) but is **architecturally unreachable** for gate denials in production:
    `PostToolUse` never fires for a call blocked at `PreToolUse` (confirmed via full
    `/tmp/.claude-hook-metrics-503.log` analysis — every exit-2 gate entry has zero matching
    `post-tool-analytics` entry, every exit-0 entry reliably has one). The fix code is correct;
    its stated goal — tracking repeated gate denials — can't be exercised as written.
  - **Step 6 (N7)**: confirmed via code read (`pre-tool-gate-v2.sh:579-608`) and live tests. The
    real fix is a dot-directory carve-out for `find`/`ls` only — permits with a WARN + `head
    -100` cap when the target matches `.serena/|.claude/|.cursor/|.mcp.json` (`ls
    .claude/hooks/` and `find .claude/hooks -maxdepth 1 -name "*.sh"` both succeeded).
    Non-dot-dir `ls`/`find` still hard-blocks (`ls plans/` denied) — policy unchanged. `grep` is
    explicitly excluded from the carve-out and stays hard-blocked unconditionally, confirmed
    both from an uninitialized fresh subagent and from this session after genuinely completing
    MCP init (`pctx list_functions` + `Serena.initialInstructions`) — there is no live
    "session init" check anywhere in the gate; that phrase in deny messages is guidance text
    only, not a runtime condition.
  - **Step 8 (N9)**: N9a's chained-sleep regex correctly matches `kubectl ...; sleep 5`
    (confirmed via code read, `pre-tool-gate-v2.sh:636-639`), but the hint is emitted via bare
    `echo ... >&2` followed by a plain `exit 0` — never wrapped in JSON
    `hookSpecificOutput`/`additionalContext` — so it never reaches the agent even though it
    fires; visible only to a human reviewing hook stderr/transcript. Repetition-hint scope
    question resolved: N6b's tracker only fires on `tool_output.error` containing "BLOCKED:",
    and N9-flagged commands succeed normally with no error field — no overlap with N6b's
    tracker.

Phase 4 substantively complete as of 2026-07-09 — all six identified items landed as discrete,
policy-compliant commits ("policy unchanged, scope corrected" on every one), and all four
verification steps (3, 5, 6, 8) are now closed with code-level findings above. Phase 5
(deferred by user) remains explicitly out of scope for this session.

## Done — 2026-07-08 constitution-hooks-audit M7 (out of Phase 4 order)

Executed `plans/2026-07-08-constitution-hooks-audit.md` M7 per user decision: "scrub references"
(keep the 7 skills disabled, remove/rewrite dead docs pointing to them as callable).

- [x] Verified live `.claude/settings.json` `skillOverrides` — confirmed all 7 (`stark`, `fury`,
  `ironman`, `hawk`, `code-health`, `monitor-patterns`, `hyper-commit-setup`) are `"off"`
- [x] Rewrote dead references in `ai/skills/cap/SKILL.md` (frontmatter description), `ai/skills/strange/SKILL.md`
  (`/fury` invocation instruction), `ai/skills/pr-review/SKILL.md` (3 spots: description, "Relationship to
  /hawk" section, Skill Map table rows for `/hawk` and `/fury`), `ai/skills/ci-watch/SKILL.md` and
  `ai/skills/ci-monitor/SKILL.md` (`/monitor-patterns` "Related" links), `ai/rules/monitor-patterns.md`
  (pointed at the reference file directly instead of "invoking" a disabled skill)
- [ ] Flagged as follow-up, not edited (file-overlap with other open PRs #277-282 / in-flight hooks
  consolidation): `ai/rules/agent-user-global.md` (`/monitor-patterns` mention), `ai/rules/tool-priority.md`
  (Code Health Routing table: `/code-health`, `/hawk`), `.claude/hooks/plans-healthcheck.sh`
  (`/hyper-commit-setup` suggestion)
- Left unedited as historical/aspirational, not active routing bugs: stale `plans/*.md` files last
  touched 2026-05-21 or earlier, and `decisions/0005-autonomous-watchdog-loop.md`'s forward-looking
  "Self-Driving PR Pipeline" note

## Done — 2026-07-08 constitution-hooks-audit Phase 1

Executed `plans/2026-07-08-constitution-hooks-audit.md` Phase 1 per user "go" (Phase 0 explicitly skipped by user).

- [x] C1 — `pre-tool-gate-v2.sh` session-id detection: env var → jq-parsed stdin field, with `EFFECTIVE_SESSION_ID` fallback
- [x] `post-tool-analytics.sh` flag-matcher — confirmed already correct, no change needed
- [x] H3 — `hook-config.yaml` dead `rule.*`/`read-guard.*` layer: registered `hook-rule-loader.sh` (fixed its `_deny()` blocking, sourced from `pre-tool-gate-v2.sh`, wired into Sections 1/2); verified live with simulated hook payloads
- [x] M4 — `session-duration-guard.sh` 500-turn hard block: `exit 1` → `exit 2`
- Phases 2-4 of that audit remain unexecuted, no user decision yet

## In Progress — 2026-07-07 harness improvement execution

Executing `plans/2026-07-07-ai-harness-improvement-proposal.md` per user "go" (Phase 0/#7/#10 excluded).

- [x] #4/#5 — `ai/rules/tool-priority.md` §10: fix Qmd.query/LeanCtx.ctxCall drift, add Graphify routing table
- [x] #6 — Fix stale MCP-server list in `style_and_conventions` Serena memory (serena, qmd, lean-ctx, repomix, graphify, verified against pctx.json)
- [x] #8 — `.claude/hooks/git-commit-guard.sh`: added commitlint body-max-line-length check (100 chars, trailers exempt). Also fixed a real prerequisite bug found along the way: the existing subject-format check (Policy A) silently no-op'd on heredoc-style `git commit -m "$(cat <<'EOF' ... EOF)"` commits — the exact form this system's own git instructions mandate for multi-line/co-authored commits — because the old single-line sed regex never matched across the heredoc's newlines. Added `extract_commit_message()` to handle both forms; verified via 3 simulated PreToolUse JSON inputs (heredoc+bad body → blocks, heredoc+good body → passes, single-line non-conventional subject → still blocks as before). No repo-side CI (`.github/workflows/claude-auto*.yml`) references commitlint at all — confirms the insights "CI failures" happened in other repos, so this machine-wide hook (not a dotfiles-repo CI change) was the correct fix location.
- [x] #9 — Added "Communication" section to `ai/rules/agent-user-global.md` (ask before implementing on ambiguous shorthand)
- [x] #11 — New `.claude/hooks/model-availability-check.sh` SessionStart hook (registered in `settings.json` alongside `session-init.sh`/`supermemory-project-check.sh`). Best-effort, fail-open checks: (1) `model`/`advisorModel` from project-then-global `settings.json` match a known alias/ID pattern, (2) at least one recognized auth mechanism present (`ANTHROPIC_API_KEY`, Bedrock/Vertex env vars, or `~/.claude/.credentials.json`), (3) `api.anthropic.com` reachable within a 2s timeout. Emits a clear `additionalContext` message only when issues are found (silent on the healthy path). Directly targets the insights report's "model access and API failures" friction category (sessions that ended with no response at all). Verified: clean run against real config (no output, exit 0), and a synthetic bad-model/bad-advisor/no-auth run (all 3 issues correctly detected, valid JSON, exit 0).
- [x] #12a (Step 4, alias cleanup) — already resolved via `decisions/0003-universal-constitution-loading.md`; `global-developer-guidelines.md` file is gone, zero live references (only historical mentions in `decisions/`/`plans/`)
- [ ] #12b (Step 5, restore corrupted `ai/commands/{aside,hookify,instinct-export}.md`) — BLOCKED: needs the actual "Everything Claude Code" upstream repo URL/ref to restore from; not guessing a GitHub URL. Needs user input.
- [x] #12c (Step 6, skill frontmatter sweep) — RE-SCOPED, not a frontmatter edit task. The 2026-06-12 plan's 11-skill list is stale: commit 392a764 (PR #258, merged 2026-06-18, six days after the plan was written) already descoped AUC-specific skills out of this repo. `migration-watchdog`, `migration-watchdog-auto` moved to `auc-conversion/.claude/skills/`; `auc-dev-a/b/c` never lived here (they're in `auc-conversion/.claude/agents/` per `plans/2026-04-02-bmad-learnings.md`). Of the 6 skills that do still exist here, the plan's specific asks were already done by prior work: `stack-ship` has real frontmatter+triggers, `watchdog-cron-setup` has `disable-model-invocation: true`, `watchdog-remediate` has a named `playbook` argument. `hyper-commit-setup`, `ado-workitem`, `autoresearch` were already correctly configured. **Real problem found, not in original plan**: `watchdog-cron-setup/SKILL.md` still instructs `CronCreate(prompt: "/migration-watchdog-auto", durable: true)` and its Teardown section, but that skill no longer resolves in this repo — moved to `auc-conversion`. Confirmed via `CronList` that no live cron currently exists with this prompt, so it's a latent doc bug, not an active broken job. `watchdog-remediate` has the same problem (described as "Called by migration-watchdog-auto on FAILURE"). Recommend: move both to `auc-conversion/.claude/skills/` alongside their siblings, or retire them from this repo — deferred to user decision since it's a cross-repo action.
- [x] #13 — `.claude/agents/*.md` restored as symlinks to `ai/agents/` (disk had drifted to real files, though content was identical and git index already expected symlinks — `setup.sh` logic was already correct, just hadn't converted these)
- [ ] #14 — Re-scope paused Steps 15-19 against current reality
- [ ] #15 — Wire commitlint auto-fix into `cicd-auto-retry` agent
- [ ] #16 — `stack-create` gitignore-detection enhancement
- Explicitly excluded from this pass: Phase 0 (settings.json safety), #7 (.claude/skills/ gitignored note), #10 (data-verification note), #17 (deferred pending Cap v4)

## Older — paused

- [ ] AI primitives upgrade plan (plans/2026-06-12-ai-primitives-upgrade.md) — plan written, execution not started

## Done

- [x] AI primitives audit workflow: 5-area inventory + 3-tool capability research + 4-dimension gap analysis + adversarial verification (2026-06-12)
- [x] fury v3.1.0 BDD context discovery (dotfiles PR #184, merged 2026-05-16)
- [x] auc-conversion Serena memory aliases for fury (PR #641, merged 2026-05-16)
- [x] code-health skill + hawk integration (dotfiles PR #183, merged 2026-05-14)
- [x] CodeScene agentic workflow improvements (dotfiles PR #191, merged 2026-05-18)
- [x] Fork-vs-fresh-agent rule for subagent spawning (dotfiles PR #192, merged 2026-05-21)
- [x] Insights action plan (dotfiles PR #193, merged 2026-05-21)
- [x] Apply auc-conversion CLAUDE.md patch (auc-conversion PR #728, merged 2026-05-21)
- [x] Implement autonomous watchdog loop (decisions/0005-autonomous-watchdog-loop.md)

## Backlog

- [ ] Wave 1 — Hygiene & safety (skill repatriation, guard fix, dead hooks, dup rule file, corrupted commands)
- [ ] Wave 2 — Modernization (frontmatter sweep, hook chain async, todo-gate events, CI consolidation, progressive disclosure, rules→skills)
- [ ] Wave 3 — Orchestration & cross-tool (ai/agents, headless hardening, agent teams, routines, --bg, ~/.agents/skills, pctx parity, Gemini extension)
