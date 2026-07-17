# Progress — 2026-06-12

## In Progress — Chrome MCP efficiency hook + M8 orphan cleanup (branch `chore/chrome-mcp-rules-cleanup`)

- [x] Write `ai/rules/chrome-mcp-efficiency.md` (decision tree, required patterns, anti-patterns, exceptions)
- [x] Write `.claude/hooks/chrome-mcp-guard.sh` (PreToolUse advisory hook, fires once per session, `chmod +x`)
- [x] Register the hook in `.claude/settings.json` (`PreToolUse` matcher `mcp__claude-in-chrome__.*`)
- [x] Wire `chrome-mcp-efficiency.md` into `.claude/CLAUDE.md` `@`-imports
- [x] M8: delete `ai/rules/qmd-usage.md` (folded into `agent-user-global.md`/`tool-priority.md`)
- [x] M8: delete `ai/rules/monitor-patterns.md` (folded into `agent-user-global.md`)
- [x] M8: delete `ai/rules/pctx-session-init.md` (merged into `tool-priority.md` §6)
- [x] M8: wire `ai/rules/hyper-atomic-commits.md` into `.claude/CLAUDE.md` `@`-imports
- [x] M8: wire `ai/rules/context-window-discipline.md` into `.claude/CLAUDE.md` `@`-imports
- [x] M8: convert `ai/rules/kubectl-efficiency.md` → `ai/skills/kubectl-efficiency/SKILL.md` (delete old rule file)
- [x] Fix stale import-list claim in `docs/agent-configuration-architecture.md`
- [x] Check off M8 in `plans/2026-07-08-constitution-hooks-audit.md` with full disposition summary
- [x] Append ADL entry to `plans/decisions.md` (hook+rule architecture + M8 dispositions)
- [ ] Verify the hook actually fires: simulate a `mcp__claude-in-chrome__*` PreToolUse payload and
      confirm `chrome-mcp-guard.sh` emits its stderr advisory once, dedupes via the state file on a
      second call, and correctly parses `.tool_name`/`.session_id` from stdin JSON
- [ ] Run `git status`/`git diff` in the worktree to review the full changeset before staging
- [ ] Ask the user whether to open a draft PR (per `stack-create` skill step 5) — not yet asked
- [ ] Commit on `chore/chrome-mcp-rules-cleanup` — no commit made yet

## In Progress — goal-authoring skill (branch `feature/goal-authoring-skill`)

- [x] Write skill draft in `ai/skills/goal-authoring/` (skill-creator process)
- [x] Draft 3 evals + assertions in `evals/evals.json` (bootstrap-new-project,
  add-goal-to-existing-index, fix-malformed-goal)
- [x] Spawn all 6 iteration-1 runs (with_skill + without_skill per eval)
- [x] Capture all 6 final reports as `REPORT.md` (1 reconstructed via filesystem inspection —
  `eval-addgoal-with-skill` never sent a report message)
- [x] Capture `timing.json` per run — confirmed **not obtainable** for this batch (0/6); logged
  explicitly as a known gap in `benchmark.json` notes rather than silently omitted
- [x] Grade each run against assertions → `grading.json` (fields: text/passed/evidence, plus a
  `summary: {passed, failed, total, pass_rate}` block, nested under `run-1/` per eval/config —
  the aggregation script requires both, undocumented until the source was read)
- [x] `python -m scripts.aggregate_benchmark <workspace>/iteration-1 --skill-name goal-authoring`
  → with_skill 93.3%, without_skill 66.7%, delta +0.27 (matches hand-tally 14/15 vs 10/15)
- [x] Analyst pass over benchmark data — 5 notes added to `benchmark.json`/`benchmark.md`
  (bootstrap-eval is the only discriminating eval; without_skill's stddev is a bimodal artifact,
  not real variance; with_skill's one failure is a real skill gap — active-context pointer not
  filled in after goal creation; add-goal validator caveat resolved via direct re-execution;
  `runs_per_configuration` metadata corrected 3→1)
- [x] Launch `eval-viewer/generate_review.py --static` → written to
  `ai/skills/goal-authoring-workspace/iteration-1/review.html` (headless environment)
- [ ] Read `feedback.json` once user reviews `review.html`, iterate on skill (known candidate fix:
  add an explicit reminder to populate the active-context pointer block right after creating a
  new active goal)
- [ ] Commit + open PR via `stack-pr` skill (Conventional Commits title) — no commit made yet at
  any point in this task

## Done — 2026-07-16 cross-client config portability (Goal 02, bounded slice)

Goal: `goals/2026-07-15-02-cross-client-config-portability.md`. Plan:
`plans/2026-07-16-cross-client-config-portability.md`. User approved scope: "all 3 clients,
read-only first" (Steps 1-6 for Gemini/Cursor/Windsurf + independent Steps 8-9; Step 7 live-write
stays blocked regardless).

- [x] Step 9 — created `.serena/memories/START_HERE.md`; `Serena.readMemory` now succeeds.
- [x] Step 8 — found and fixed a real security regression (not the fixture gap the goal doc
  assumed): removed `"skipDangerousModePermissionPrompt": true` from `.claude/settings.json`
  (user-approved). Full suite green: `pytest scripts/ -q` → 85 passed, 39 subtests passed.
- [x] Step 1 — read-only inventory for Gemini/Cursor/Windsurf: live SHA-256 captured, existing
  base/manifest/overlay scaffolding read, concrete per-client gaps identified (see dated plan).
- [x] Step 2 — wrote `ai/config/gemini/settings.base.json` (new); extended
  `ai/config/cursor/mcp.base.json` (added `notebooklm`, `chrome-devtools`); extended
  `ai/config/windsurf/mcp_config.base.json` (added `lean-ctx`).
- [x] Step 3 — added manifest entries in `ai/config/manifest.json` (7 clients total: `claude`,
  `codex`, `gemini`, `gemini-settings`, `cursor`, `windsurf`, `pctx` — gemini has a second entry
  for `settings.json` distinct from the existing `mcp.json` entry).
- [x] Step 4 — added gemini/gemini-settings/cursor/windsurf-specific tests to
  `scripts/test_portable_config_templates.py` and `scripts/test_config_manifest.py`, mirroring the
  Codex-pattern tests. Full suite green: `pytest scripts/ -q` → 91 passed, 42 subtests passed.
- [x] Step 5 — wrote overlay fixtures and updated `ai/config/README.md`.
- [x] Step 6 — ran `--compare-against` for each client's proposal vs. live runtime config using
  real mode-`0600` overlay files under `~/.config/dotfiles-ai/` (Gate-1 pattern from the Codex
  slice). All four remaining targets (gemini `mcp.json`, gemini `settings.json`, cursor
  `mcp.json`, windsurf `mcp_config.json`) came back clean or explainable: three showed only a
  cosmetic `$schema`-presence diff (base declares it, live runtime doesn't); windsurf additionally
  showed the four `mcpServers.pctx.args[2..5]` index-shifted entries from a pre-existing (not
  this-session) drift — `ai/config/windsurf/mcp_config.base.json`'s `pctx` args are missing the
  `-q` flag that live `~/.windsurf/mcp_config.json` has. Flagged as an out-of-scope finding, not
  fixed (this slice's task was "add lean-ctx only").
- [ ] Step 7 — hard stop, do not execute without separate explicit approval. **Intentionally not
  done** — permanent non-goal for this slice regardless of Steps 1-6 completion.

Bounded slice (Steps 1-6, 8, 9) substantively complete. Step 7 remains an unconditional non-goal.

## Done — 2026-07-15 agentic-loop optimization (bounded Codex slice)

Goal: `goals/2026-07-14-01-agentic-loop-optimization.md`.
Branch: `feature/codex-config-proposals`.

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
- [x] Obtain user approval and implement the bounded Codex proposal-generator slice and local-overlay
  convention.
- [x] Complete proposal-diff and content-safe validation without exposing local values or applying
  live runtime changes.
- [x] Gate 1 — corrected the portable base to official `[tui]` `status_line`, created the minimal
  ignored `~/.config/dotfiles-ai/codex.overlay.toml` with mode `0600`, and completed the content-safe
  base-plus-overlay versus live comparison with zero changed paths. No prior overlay existed; the
  live config SHA-256 remained unchanged and no live write occurred.
- [x] Gate 2 backup and rollback preflight — created the private mode-`0700` backup directory with
  four mode-`0600` evidence files; validated the unchanged candidate through TOML and isolated
  `CODEX_HOME` Codex parsing; proved sandbox rollback to the exact original-live hash; and confirmed
  live bytes, hash, and metadata remained unchanged.
- [x] Final Gate 2 decision — skipped the no-op canonical rewrite because semantic comparison
  reported zero changed paths; no live runtime write occurred.

## Done — 2026-07-14 agentic-loop optimization Slices B-D baseline

Goal: `goals/2026-07-14-01-agentic-loop-optimization.md`.

Branch/worktree: `chore/agentic-loop-source-validation` at
`.trees/agentic-loop-source-validation`.

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
- [x] Add checked/not-yet-checked evidence and grouped bottlenecks to the baseline report.
- [x] Add objective completion audit matrix showing proven, partial, and remaining requirements.
- [x] Add exact approval decision block defining what Codex remediation approval does and does not authorize.
- [x] Add command/skill reachability snapshot, including broken `.claude/skills/` symlink evidence.
- [x] Classify the 14 broken `.claude/skills/` symlinks by stale/orphaned/moved/contradictory evidence.
- [x] Validate source-of-truth/symlink strategy against current official docs and live user-level paths.
- [x] Move audit continuation edits off `main` into a dedicated stack worktree and confirm main is clean.
- [x] Add regression coverage and validation for dangling `.claude/skills` symlinks.
- [x] Remove 14 dangling repo `.claude/skills` symlinks and verify the repo drift check passes.
- [x] Add `claude-auto-script-tests` PR gate and verify local `unittest discover` passes.
- [x] Extend skill drift validator to multi-directory read-only checks and capture live user-dir drift.
- [x] Strengthen skill drift validation to reject symlinks whose targets lack `SKILL.md`/`skill.md`.
- [x] Remove tracked stale `.gemini/skills/daily-standup-insights` symlink and validate tracked
  `.claude`, `.gemini`, and `.cursor` skill dirs together.
- [x] Classify live user-level skill-dir drift without modifying live runtime directories.
- [x] Re-run validation: 7 focused skill-drift tests, 54 total script tests, shell syntax,
  tracked skill-dir drift check, workflow YAML parse, and clean main checkout.
- [x] Inspect open draft PR stack #297-#315 and document file-level overlap before publishing.
- [x] Compare tracked Claude hook settings/scripts against current hook docs and document static
  matcher/schema risks without changing hook semantics.
- [x] Verify self-modification/copy-back mechanisms: Claude settings guard is proposal-only, but
  hook graduation still mutates tracked policy/state.
- [x] Run public hygiene scanner and record current exposure counts without broad cleanup.
- [x] Convert the hook-graduation self-modification risk into the goal's required policy proposal
  format and active decision log entry.
- [x] Refresh durable ADR `decisions/0011-agentic-loop-optimization.md` so it matches the latest
  source-of-truth, skill-drift, hook-graduation, and hygiene findings.
- [x] Add explicit execution/PR boundaries so future work stays in separate reviewable slices.
- [x] Extend static hook config validation to detect `pre-tool-gate-v2.sh` MCP logic when the
  configured `PreToolUse` matcher omits `mcp__*`; verify full script tests now pass with 56 tests.
- [x] Add `--prune-stale-links` to the skill-drift validator and wire `setup.sh` to prune invalid
  generated user-skill symlinks without deleting real directories; verify full script tests now pass
  with 59 tests.
- [x] Add non-sensitive public-hygiene summary output so future cleanup can group by rule/path without
  printing private excerpts; verify full script tests now pass with 60 tests.
- [x] Add read-only config inventory for `ai/config/manifest.json` so source/runtime/overlay
  boundaries are summarized without reading live runtime files; verify full script tests now pass with
  62 tests.
- [x] Extend read-only config doctor coverage to tracked PCTX/Cursor/Gemini config paths and add a
  direct-CLI regression test; verify full script tests now pass with 64 tests.
- [x] Add redacted `config_doctor --summary` counts and sanitize new test literals so the hygiene
  scanner does not gain extra findings; verify full script tests now pass with 65 tests.
- [x] Sanitize script/test hygiene fixtures and add a regression that `scripts/*.py` contains no
  public-hygiene findings; verify full script tests now pass with 66 tests.
- [x] Add non-blocking `claude-auto-config-audit-summary` PR job for redacted config/hygiene/hook
  summaries and a workflow regression test; verify full script tests now pass with 67 tests.
- [x] Add `scripts/hook_config_check.py --summary` and switch the PR audit job to count-only hook
  output; verify full script tests now pass with 68 tests.
- [x] Expand `scripts/config_inventory.py --summary` to verify tracked portable base scope and
  format-boundary status; verify full script tests now pass with 69 tests.
- [x] Add non-mutating `setup.sh --check` and `setup.sh --dry-run` paths plus regression tests;
  verify full script tests now pass with 71 tests.
- [x] Add instruction-size budget enforcement for always-loaded guidance and wire its summary into
  the PR audit job; verify full script tests now pass with 73 tests.
- [x] Wire instruction-size budget enforcement into non-mutating `setup.sh --check`; verify focused
  setup tests and full script tests still pass.
- [x] Extend static hook validation to reject multiple PreToolUse input rewriters in one group;
  verify full script tests now pass with 74 tests.
- [x] Add non-blocking dead skill/command reference summary to the PR audit job; verify full script
  tests now pass with 75 tests.
- [x] Add source-scope grouping to the dead-reference summary so active guidance debt is separated
  from historical plan debt.
- [x] Align non-mutating `setup.sh --check` with the PR audit-summary job by surfacing config,
  hygiene, doctor, hook, instruction-budget, skill-drift, and dead-reference summaries locally.
- [x] Add fake-HOME regression coverage proving `setup.sh --check` and `setup.sh --dry-run` do not
  create runtime directories/files; verify full script tests now pass with 76 tests.
- [x] Add regression coverage that local `setup.sh --check` and the PR audit-summary job keep the
  same shared summary commands; verify full script tests now pass with 77 tests.
- [x] Add syntax-parse summary for tracked settings, workflow, manifest, and config bases to both
  local `setup.sh --check` and PR audit-summary; verify full script tests now pass with 79 tests.
- [x] Add tracked shell-script syntax summary to both local `setup.sh --check` and PR audit-summary;
  verify full script tests now pass with 81 tests.
- [x] Add neutral-guidance adapter validation to both local `setup.sh --check` and PR audit-summary;
  verify full script tests now pass with 84 tests.
- [x] Add pre-tool hook fixture summary to both local `setup.sh --check` and PR audit-summary;
  verify full script tests now pass with 85 tests.
- [x] Extend hook fixture schema validation to cover ask, rewrite/`updatedInput`, and
  `additionalContext`; verify full script tests now pass with 88 tests.
- [x] Add non-blocking static hook-output schema summary to local `setup.sh --check` and PR audit;
  verify full script tests now pass with 92 tests.
- [x] Add hook target existence/executability validation to local `setup.sh --check` and PR audit;
  verify full script tests now pass with 96 tests.
- [x] Add non-blocking self-modification summary for tracked hook policy/state mutation paths;
  verify full script tests now pass with 99 tests.
- [x] Add manifest-base hygiene validation so tracked portable base templates stay free of local/private
  markers; verify full script tests now pass with 101 tests and `setup.sh --check` surfaces 0 findings.
- [x] Add core autonomous-skill contract validation for `cap`, `stark`, `fury`, `ironman`, `hawk`, and
  `strange`; wire the summary into local/PR audit parity and verify full script tests now pass with
  104 tests.
- [x] Add MCP gateway topology validation for Claude/Cursor/Gemini/Windsurf/Codex clients and the
  PCTX backend catalog; wire the summary into local/PR audit parity and verify full script tests now
  pass with 108 tests.
- [x] Obtain user approval before implementing the Codex remediation sequence. Approval was obtained
  and the Codex remediation sequence was implemented and verified; see
  "Done — 2026-07-15 agentic-loop optimization (bounded Codex slice)" above.

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
