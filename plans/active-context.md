# Active Context

## Current (2026-07-16) — goal-authoring skill: grading + aggregation + viewer done; awaiting user review

**Worktree/branch:** `.trees/goal-authoring-skill` / `feature/goal-authoring-skill`. Task: port the
goal-authoring convention (discovered in `auc-dbprofiling`) into `ai/skills/goal-authoring/` using the
skill-creator process, with evals run to validate before considering it done. No commit has been made yet.

- Skill draft is written. `evals/evals.json` + 3 `eval_metadata.json` files (bootstrap-new-project,
  add-goal-to-existing-index, fix-malformed-goal) are fully populated with prompts + assertions.
- All 6 iteration-1 eval runs (3 evals × with_skill/without_skill) are done.
- **Grading done:** all 6 `grading.json` files written to
  `ai/skills/goal-authoring-workspace/iteration-1/<eval-name>/<with_skill|without_skill>/run-1/grading.json`
  with the exact schema the aggregation script needs — `expectations[]` (`text`/`passed`/`evidence`) plus a
  `summary: {passed, failed, total, pass_rate}` block (the aggregator reads pass_rate from `summary`, not
  computed from `expectations` — this cost a debugging pass, see decisions.md).
  - eval-bootstrap-new-project: with_skill 4/5 (0.8), without_skill 0/5 (0.0)
  - eval-add-goal-to-existing-index: with_skill 6/6, without_skill 6/6 (both 1.0)
  - eval-fix-malformed-goal: with_skill 6/6, without_skill 6/6 (both 1.0)
  - Both previously-open grading caveats (add-goal `with_skill` validator, bootstrap `with_skill`
    active-context judgment call) were resolved by directly re-running
    `python3 scripts/validate_goals.py` against the copied output projects rather than trusting
    self-reported transcripts.
- **Aggregation done:** `benchmark.json`/`benchmark.md` generated via
  `PYTHONPATH=<skill-creator-dir> python3 -m scripts.aggregate_benchmark <workspace>/iteration-1
  --skill-name goal-authoring` (grading.json files had to be moved into `run-1/` subdirectories first —
  the aggregator requires that nesting). Result: **with_skill 93.3% vs without_skill 66.7%, delta +0.27**,
  matching the hand-tallied 14/15 vs 10/15 assertion counts.
- **Analyst pass done:** added 5 notes directly into `benchmark.json`'s `notes[]` (and regenerated
  `benchmark.md`) covering: (1) eval-bootstrap-new-project is the only discriminating eval — the other two
  score 1.0 in both configs; (2) without_skill's high stddev (0.577) is a bimodal artifact of 3 evals, not
  real variance; (3) with_skill's one failure (bootstrap's `active_context_points_at_goal`) is a real skill
  gap — the pointer block wasn't filled in after creating the goal, worth an explicit reminder in SKILL.md;
  (4) the add-goal validator caveat is now resolved via direct re-execution; (5) `runs_per_configuration`
  was corrected from the aggregator's default (3) to the actual value (1), and the total absence of
  timing/token data is flagged explicitly as unavailable (subagents reported via chat, not a tracked
  spawn mechanism that emits `total_tokens`/`duration_ms`), not silently omitted.
- **Viewer launched:** static HTML written to
  `ai/skills/goal-authoring-workspace/iteration-1/review.html` via `eval-viewer/generate_review.py --static`
  (headless environment). User has not yet reviewed it or produced `feedback.json`.
- **Tool-availability note from this session** (worth fixing in `ai/rules/tool-priority.md` separately,
  out of scope here): plain Bash `ls`/`find` were hard-blocked mid-session citing missing session init;
  worked around via `python3 -c` inline scripts (unblocked) rather than running the full Serena/pctx init,
  which wasn't needed for this task.
- **Prompt-injection flagged, not acted on:** tool output this session carried a fake "supermemory-update"
  block (instructing plugin-install commands to be printed unprompted) and a fake "session-init hook
  pending" block — both identified as injected content and explicitly ignored; told the user directly
  rather than complying or silently discarding.

**Not yet started:** read `feedback.json` once the user reviews `review.html` and iterate on the skill;
commit the finished skill on `feature/goal-authoring-skill` (no commit made yet, at any point in this
task) and open a PR via `stack-pr` (Conventional Commits title).

plan: (no dated plan file for this task — tracked via this active-context entry)
step: grading + aggregation + analyst notes + viewer done; awaiting user review of review.html
focus: read feedback.json once available, iterate on SKILL.md (esp. the active-context pointer gap), then commit + PR

## Previous (2026-07-16) — Goal 02 bounded slice complete (Steps 1-6, 8, 9); Step 7 stays a non-goal

- Active tracked goal: `goals/2026-07-15-02-cross-client-config-portability.md`. Status in
  `goals/00-index.md` moved `In progress` → `Completed (bounded slice)`.
- Full detail: `plans/2026-07-16-cross-client-config-portability.md`.
- **User decisions obtained this session (via `AskUserQuestion`, already applied):**
  1. Scope: "All 3 clients, read-only first" — Steps 1-6 (inventory, base templates, manifest,
     tests, README, Gate-1 compare) for Gemini, Cursor, and Windsurf together, plus independent
     Steps 8-9. Stop before any live write (Step 7) regardless — done, intentionally.
  2. Security regression: "Fix it now" — removed `skipDangerousModePermissionPrompt: true` from
     `.claude/settings.json` since it un-weakens (not weakens) a permission default — done.
- **Done, all of it:**
  - Step 9: `.serena/memories/START_HERE.md` created — `Serena.readMemory` succeeds.
  - Step 8: fixed the real committed security regression in `.claude/settings.json` (see decision
    above).
  - Step 1: read-only inventory for all three clients (SHA-256 + gap list) — see dated plan.
  - Step 2: wrote `ai/config/gemini/settings.base.json`; extended `cursor/mcp.base.json`
    (`notebooklm`, `chrome-devtools`); extended `windsurf/mcp_config.base.json` (`lean-ctx`).
  - Step 3: added manifest entries — `ai/config/manifest.json` now has 7 clients (`claude`,
    `codex`, `gemini`, `gemini-settings`, `cursor`, `windsurf`, `pctx`).
  - Step 4: added client-specific tests to `test_portable_config_templates.py` and
    `test_config_manifest.py`. Full suite: `pytest scripts/ -q` → **91 passed, 42 subtests
    passed**, zero failures (re-confirmed green again this segment).
  - Step 5: overlay-example fixtures + `ai/config/README.md` updated.
  - Step 6 (Gate-1 pattern): created real gitignored overlay files (mode `0600`) under
    `~/.config/dotfiles-ai/` for gemini mcp, gemini-settings, cursor, windsurf; ran
    `--compare-against` for all four. Three clean aside from a cosmetic `$schema` diff; windsurf
    additionally shows the four `mcpServers.pctx.args[2..5]` entries from the pre-existing
    (not-this-session) missing `-q` flag in `ai/config/windsurf/mcp_config.base.json` — flagged as
    an out-of-scope finding, not fixed.
- **Step 7 remains untouched** — unconditional non-goal for this slice, per user decision.
- **Resolved this segment:** `.claude/tdd-guard/` (TDD-Guard pytest run history) and
  `plans/session-snapshot.md` (pre-compact.sh regenerated snapshot) were both untracked
  hook-generated scratch state, not user work — added both to `.gitignore` (see
  `plans/decisions.md` 2026-07-16 entry). Neither had any git history.
- **Remaining bookkeeping (not started):** draft `decisions/NNNN-cross-client-config-portability.md`
  durable ADR summarizing Goal 02's bounded slice.

plan: plans/2026-07-16-cross-client-config-portability.md
step: Complete (bounded slice: Steps 1-6, 8, 9)
focus: draft durable ADR; Step 7 (live write) stays out of scope

## Previous (2026-07-15) — bounded Codex slice complete; Slices B–D implemented; live rewrite skipped

- Active tracked goal: `goals/2026-07-14-01-agentic-loop-optimization.md`.
- Current branch/worktree: `chore/agentic-loop-source-validation` at `.trees/agentic-loop-source-validation`.
- Session-init baseline is loaded: `Serena.initialInstructions()` succeeded; `mcp__pctx__list_functions`
  returned Serena/Qmd/LeanCtx/Repomix/Graphify; `Serena.checkOnboardingPerformed()` errored; and
  `Serena.readMemory({ memory_name: "START_HERE" })` failed because no such memory exists.
- Baseline report and completed Codex proposal-generator checklist:
  `plans/2026-07-14-agentic-loop-optimization.md`.
- ADR `decisions/0011-agentic-loop-optimization.md` is complete for the bounded Codex slice.
- The portable Codex base now uses the official `[tui]` `status_line` setting instead of the
  obsolete top-level `[status_line]` table. The official config reference and `codex features list`
  confirm the current schema and live parse.
- Gate 1 created the minimal ignored `~/.config/dotfiles-ai/codex.overlay.toml` with mode `0600`;
  no prior overlay existed.
- The final base-plus-overlay comparison against the live config reported zero changed paths. Both
  hashes were valid, while the proposal and target byte hashes differed because the proposal uses
  deterministic canonical rendering.
- The live `~/.codex/config.toml` SHA-256 remained unchanged, and the live config was not written.
- The plan-focused suite remains 49 of 49. Full discovery remains 85 with exactly one unrelated
  failure caused by the absent ignored `.claude/settings.local.json`.
- Read-only summaries: public hygiene 390 findings (142 absolute-home-path, 197 private-org-name,
  51 private-org-url); config doctor 65 issues (6 errors, 59 warnings; rule split in the plan/ADR).
- The deterministic printable proposal is valid TOML and identical across runs; SHA-256 remains
  `bf13bdf914a7b28504e262183fd1a65182d560243e524efb44c94dbbdf7db280`.
- The earlier pre-Gate-1 five-path comparison remains historical synthetic evidence and is
  superseded by the actual Gate 1 zero-path comparison.
- Independent final review found no remaining correctness- or security-significant code issue in the
  bounded scope.
- Gate 2 preflight created private backup directory
  `~/.config/dotfiles-ai/backups/20260715T002308Z-pre-codex-gate2` with mode `0700`. The exact live
  backup, generated candidate, manifest, and rollback instructions each have mode `0600`.
- The backup hash equals current live. The candidate byte hash differs, but semantic comparison
  reports zero changed paths.
- The candidate TOML parsed, an isolated `CODEX_HOME` Codex parse passed, and the candidate remained
  unchanged.
- The sandbox rollback dry-run restored the candidate to the exact original-live hash.
- Live bytes, hash, and metadata remained unchanged; no runtime apply occurred.
- Final Gate 2 decision: skip the no-op canonical rewrite and close the bounded Codex slice. The
  semantic delta was zero, so no live runtime write occurred.

plan: plans/2026-07-14-agentic-loop-optimization.md
step: Complete
focus: Codex slice + Slices B-D complete; human diff review only, no live apply

## Current (2026-07-14) — Slices B–D (skill-drift, self-improvement governance, public-hygiene) executed

- Branch/worktree: `chore/agentic-loop-source-validation` at `.trees/agentic-loop-source-validation`.
- Active tracked goal: `goals/2026-07-14-01-agentic-loop-optimization.md`; plan
  `plans/2026-07-13-execution-plan.md`.
- Slice B (skill-link drift validation): added and extended `check-skill-drift.sh` plus
  `skill_reference_check.py` to validate tracked skill directories for dangling symlinks and confirm
  symlink targets are real skill directories containing `SKILL.md`/`skill.md`; removed stale skill
  symlinks left over from prior skill reorganization; preserved
  `~/.agents/skills -> ~/.dotfiles/ai/skills` as the cross-tool skill path.
- Slice C (governed self-improvement): added `self_modification_check.py` and
  `hook_target_check.py` to treat `hook-graduate.sh` auto-mutation as a risk until converted to
  proposal-only behavior, and to require explicit approval before hook levels, hook config, or
  tracked learning state change.
- Slice D (public-hygiene migration): added `config_base_hygiene_check.py` and used
  `scripts/public_hygiene_check.py` as deterministic evidence to migrate private org names, internal
  URLs, and machine paths out of tracked files by file group, avoiding broad scrubs in branches that
  already overlap open PR stacks.
- Added supporting checks: `autonomous_skill_check.py`, `config_inventory.py`,
  `guidance_adapter_check.py`, `hook_output_schema_check.py`, `instruction_budget_check.py`,
  `mcp_gateway_check.py`, `syntax_check.py`.
- Extended `config_doctor.py` with the new rule coverage above.
- Ran `setup.sh --check` / `setup.sh --dry-run` to confirm the symlink-distribution invariant holds
  after the skill-symlink cleanup.
- Performed an open-PR-overlap check against #297–#315 before the public-hygiene migration to avoid
  conflicting with in-flight stacks; performed a static hook schema/matcher audit across
  `.claude/hooks/`.
- Refreshed `decisions/0011-agentic-loop-optimization.md` (Slices B–D sections, Execution state,
  Verification) to record this work.
- Evidence: 108 of 108 tests passed in this worktree after adding the skill-drift,
  self-modification-governance, and public-hygiene-migration checks and removing stale skill
  symlinks.
- Codex remediation sequence (Slice A) approval was obtained and executed; see the 2026-07-15 entry
  above for the completed Gate 1/Gate 2 evidence.

plan: plans/2026-07-13-execution-plan.md
step: Complete
focus: Slices B-D executed and verified; superseded by 2026-07-15 entry above

## Current (2026-07-14) — pctx/Codex startup regression fixed

- Branch/worktree: `fix/pctx-codex-startup` at `.trees/pctx-codex-startup`.
- Root cause: Codex 0.144.1 sends newline-delimited JSON, while the tracked
  `pctx-mcp-stdio-shim.py` waited for `Content-Length` framing and never forwarded
  Codex's initialize request.
- The tracked and portable Codex configs now invoke `pctx` directly, and the incompatible
  shim is retired. Runtime generation/link migration remains in its existing plan phase.
- Validation: 47 Python tests pass; direct initialize/tools/list/list_functions probes
  complete in 4.831s and 3.355s; fresh Codex starts complete in 15.567s and 17.446s
  with pctx initialized and three tools listed.
- Existing regular `~/.codex/config.toml` was not replaced. It already invokes direct
  pctx; the currently running pre-fix Codex process still needs a restart to reload MCP config.

## Current (2026-07-13) — Phase 0/1 audit checkpoint

- Approved Phase 0 source changes are implemented on `chore/phase0-config-boundary`:
  sanitized settings, detect-only symlink guard, untracked local overlay, and
  proposal-only client bases/generator.
- Current evidence: 42 Python tests pass, 7 maintained PreToolUse fixtures pass, the
  hygiene scanner reports 369 findings, and the doctor reports 59 residual findings.
- A preflight live-settings backup and SHA-256 manifest are stored outside Git under
  `~/.config/dotfiles-ai/backups/2026-07-13-pre-phase0/`.
- Live apply is held: the runtime symlink still targets the main checkout and its
  installed symlink guard differs from this branch, so applying now could reactivate
  copy-back behavior.
- Live runtime configuration, broad permission allows, canonical instruction hierarchy,
  and ordering-sensitive Phase 1 hooks remain unchanged pending separate review.

## Current (2026-07-09) — Phase 4 checkpoint, session restart required

**Why checkpointing now instead of continuing:** this session has hit its 3rd `/compact` this
session, tripping the standing rule in `ai/rules/context-and-compaction.md` ("Use `/compact` at
most 1-2 times per session — prefer checkpointing to a plan and starting fresh"). Stopping here
and telling the user to resume in a fresh session rather than continuing to implement more items
in this window.

**Standing constraint for every remaining edit (plan doc line 54, verbatim):** "policy unchanged,
scope corrected" — never weaken an existing hard-deny, only fix repetition/scoping/contradiction;
each commit must carry an explicit note to that effect.

**Done this session (applied to working tree, NOT yet committed):**
- N6b: `.claude/hooks/advisor-escalate.py` `is_excluded()` (~line 111) — removed the outright
  exclusion of `"BLOCKED:"` gate denials (previously hid retry-loop cases from the recurrence
  tracker); only genuine "hook additional context" nudges stay excluded now. Confirmed intact via
  re-read this session.

**Not yet started (still need edits in `pre-tool-gate-v2.sh`):**
- N4 — extend the existing 100KB/500KB size guard (Section 1b, ~line 251) beyond `Read` tool_input
  to cover `mcp__pctx__execute_typescript` result size and Bash-redirect target paths. **Unresolved
  mechanism**: `pre-tool-gate-v2.sh` is PreToolUse-only, but the plan's Verification item 3 frames
  the pctx-result case as "(post-fix only)" — i.e. it may require a PostToolUse companion (most
  likely in `post-tool-analytics.sh`, not `advisor-escalate.py`) rather than being achievable purely
  in this file. **Next session must re-read "Phase 2's finding"** in the plan doc (referenced by
  both N4 and N6b as "Depends on Phase 2") before implementing this — that finding text was not
  located again this session (a `grep`-based Bash search for "Phase 2" was blocked by this
  project's own gate hook; needs a `Read`-based section scan of the plan doc instead, or an
  `awk`-based Bash fallback since `awk` is not on the deny list here).
- N4c/N6c — Section 2g line ~615: add `jq|curl` to the pipe-strip whitelist regex
  `^(gh|kubectl|git|argocd|az|docker|helm|aws|rtk)`. Exact, low-risk, ready to implement directly.
- N6a — prefix "every hard-deny (autoresearch dangerous-cmd list, branch-protection edits)" with
  `[HARD-BLOCK — DO NOT RETRY]`; document the marker in `~/.dotfiles/ai/rules/tool-priority.md` §0.
  Scope stated as "Net-new, multi-site" in the plan — broader than an earlier narrow draft that
  scoped it to just 3b (branch-protection)/4a/4b/empty-`TOOL_NAME`. The "autoresearch dangerous-cmd
  list" reference has NOT been located in this file yet — may point to a different file/mechanism.
- N7 — Section 2a/2b/2c (lines ~553-572, grep/find/ls hard-denies): branch on MCP-alternative-
  initialized state — permit-with-warn+output-cap instead of hard-deny when the dedicated tool is
  absent AND uninitialized. Reuse the `${HOME}/.config/pctx/pctx.json`-existence check (Section
  1d/6 precedent) as the "tool absent" signal; the `/tmp/.claude-ctx-loaded-...` flag (Section 6)
  is a candidate "initialized" signal.
- N9a — Section 2f (lines ~594-600, `[MONITOR HINT]`): extend the regex to also match semicolon/
  `&&`-chained `sleep N` outside a `while`-loop: `(^|;|&&)\s*sleep +[0-9]+\s*(;|&&)`.

**Real open discrepancy to reconcile before committing N6b (and possibly part of N4):** the plan
doc's own commit-grouping table names `post-tool-analytics.sh` for the N6b commit, but the actual
`is_excluded()`/recurrence-tracking logic N6b describes lives in `advisor-escalate.py` (confirmed
by direct reads of both files). Check whether `post-tool-analytics.sh` is meant to be the source of
deny signatures N6b "wires into" the tracker, or whether the plan doc's file name is simply stale.

**Explicitly out of scope for this branch:** Phase 5 (`auc-conversion` `.ckignore` fix) — user chose
"Phase 4 only" for this pass; do not touch it here.

**Verification once all Phase 4 edits land:** re-run the plan's own Verification steps 3, 5, 6, 8 to
confirm no existing hard-deny was weakened (ties to the "policy unchanged, scope corrected" rule).

## Previous (2026-07-08) — M7 scrub-references executed

User decision (final, not up for debate): keep `/stark`, `/fury`, `/ironman`, `/hawk`, `/code-health`,
`/monitor-patterns`, `/hyper-commit-setup` disabled via `skillOverrides` in `.claude/settings.json`;
scrub dead docs/hooks references instead of re-enabling. Verified live `skillOverrides` confirms all 7
are `"off"`. Edited: `ai/skills/cap/SKILL.md`, `ai/skills/strange/SKILL.md`, `ai/skills/pr-review/SKILL.md`,
`ai/skills/ci-watch/SKILL.md`, `ai/skills/ci-monitor/SKILL.md`, `ai/rules/monitor-patterns.md`. Flagged
as follow-up (file-overlap with other open PRs, not edited): `ai/rules/agent-user-global.md`,
`ai/rules/tool-priority.md`, `.claude/hooks/plans-healthcheck.sh`. Left alone as historical/aspirational
(not live routing bugs): stale `plans/*.md` files predating 2026-05-21 and
`decisions/0005-autonomous-watchdog-loop.md`'s forward-looking pipeline note. Checked off M7 in the audit
plan. Worked in worktree `.trees/agent-abdac92451e4db8be`; branch renamed to
`fix/scrub-disabled-skill-refs-m7`, PR opened (not merged) for human review.

## Previous (2026-07-08) — Phase 1 executed and verified

Executed Phase 1 of `plans/2026-07-08-constitution-hooks-audit.md` (user: "go"). All 4 items done and independently verified (not just tool-call-success-claimed — each re-checked via `bash -n`, pattern search, `git diff --stat`, or live simulated-payload testing):
1. **C1**: `pre-tool-gate-v2.sh` read `session_id` from a `CLAUDE_SESSION_ID` env var Claude Code never sets — Grep/session-init gating was dead. Now parses `session_id` from the stdin JSON payload via jq with an `EFFECTIVE_SESSION_ID` fallback mirrored from `post-tool-analytics.sh`.
2. Confirmed `post-tool-analytics.sh`'s flag-matcher was already correct (checks `ctx_intent`) — no change needed.
3. **H3**: `hook-config.yaml`'s declarative `rule.*`/`read-guard.*` layer was entirely dead (`hook-rule-loader.sh` never sourced anywhere) despite real `block`-level gaps not caught elsewhere (`sed -i`, `awk`/`echo`/`printf` redirects, piped `tee`, `node_modules` reads). Registered the loader instead of deleting the yaml: fixed its block-path to call `_deny()` instead of a non-blocking `exit 1`, sourced it from `pre-tool-gate-v2.sh`, wired `check_read_path_rules`/`check_bash_cmd_rules` into Sections 1/2. Verified live with simulated hook payloads.
4. **M4**: `session-duration-guard.sh`'s 500-turn hard block used `exit 1` (non-blocking for UserPromptSubmit hooks) — changed to `exit 2`.

Also confirmed (not touched, per explicit Phase 0 skip): `.claude/settings.json`'s `skipDangerousModePermissionPrompt: true` regression is the same already-known Phase 0 item, not new. `.stack-ship/log.jsonl` is an unrelated small artifact from a separate stack-ship run.

Next: Phases 2-4 of the audit (doc conflict resolution, stale API docs, per-tool-call consolidation) remain unexecuted — no user decision yet on whether to proceed.

## Previous (2026-07-08, pre-Phase-1)

Drafted `plans/2026-07-08-constitution-hooks-audit.md` via two parallel Fable subagents (hook-mechanics lens + doc-content lens). Headline findings: (1) `pre-tool-gate-v2.sh`'s session-init enforcement is dead code (keys off an env var never set in hook environments — Grep is never actually blocked despite every doc claiming otherwise); (2) `settings-symlink-guard.sh` blindly copies live settings back into the tracked repo, likely explaining why `skipDangerousModePermissionPrompt`/`model: sonnet` keep reappearing; (3) live `~/.claude/rules/lean-ctx.md` + global `CLAUDE.md`'s lean-ctx block directly contradict `ai/rules/tool-priority.md` on Read/Grep vs. ctx_read/ctx_search — self-verified this session, no precedence rule covers this pair; (4) `~/.claude/CLAUDE.md` (highest-precedence) has a dead import to a deleted file (`global-developer-guidelines.md`) that progress.md #12a's cleanup missed because it only checked the tracked repo. Full ranked findings + 5-phase plan in the doc. Nothing executed yet — supersedes nothing in `2026-07-07-ai-harness-improvement-proposal.md`, which stays open and is folded into Phase 0 here.

## Previous (2026-07-07)

Drafted `plans/2026-07-07-ai-harness-improvement-proposal.md` reconciling the `/insights` report against the paused 2026-06-12 audit. Key finding: uncommitted `.claude/settings.json` diff on branch `fix/session-init-unlock-grep-claim` adds `skipDangerousModePermissionPrompt: true`, regressing paused Step 13 and conflicting with the user's standing rule against skip-permissions/don't-ask mode — flagged as Phase 0 in the proposal, not yet fixed. Also found pctx SDK drift (Qmd/LeanCtx) not reflected in `ai/rules/tool-priority.md` §10, and an undocumented Graphify namespace relevant to PR workflows. Nothing in the new proposal has been executed.

focus (previous): supermemory self-hosted validation — complete (2026-07-04)

## Last Session (2026-07-04)

Re-validated and fixed additional issues found since 2026-06-30 baseline:

1. Launchd `com.supermemory.server` had drifted back to no working `ANTHROPIC_API_KEY` (`~/.supermemory/env` was malformed — key value on its own line, not attached to `ANTHROPIC_API_KEY=`). Rewrote the file correctly; server auto-restarted via launchd and consumed it into `~/.supermemory/env.enc` (plaintext `env` is deleted after consumption — expected, not a bug).
2. Found and patched a real plugin bug: `search-memory.cjs` (and 3 other bundled scripts: `add-memory.cjs`, `context-hook.cjs`, `save-project-memory.cjs` in `~/.claude/plugins/cache/supermemory-plugins/supermemory/0.0.9/scripts/`) map search-result text via `a.content||a.memory||a.context`, but the self-hosted server's `/v4/search` returns text in a `chunk` field — so every result silently mapped to `""` and got filtered by the dedup logic. Patched all 4 files to add `a.chunk` to the fallback chain. Confirmed fix works via the real `/supermemory-search` skill path (not just raw API).
   - **Caveat:** this patch is in the plugin *cache* dir — will be silently overwritten on next plugin auto-update/reinstall.
   - Drafted a GitHub issue for `supermemoryai/claude-supermemory` upstream but user cancelled filing it (2026-07-04) — draft is not saved anywhere; re-draft if revisiting.
3. Confirmed `.zshrc` already correctly exports `SUPERMEMORY_BASE_URL`/`SUPERMEMORY_API_URL`/`SUPERMEMORY_CC_API_KEY` (lines 78-81) — earlier "auth failed" symptom in-session was Claude Code's sandboxed Bash tool not fully re-sourcing `.zshrc` per shell, not a real user-facing gap.
4. Validated Anthropic key in use by supermemory (not just any `$ANTHROPIC_API_KEY` in the shell — those can differ) by round-tripping a save and confirming `status: "done"` on the document — the only reliable proof since `env.enc` can't be read back out in plaintext.

## Carried Forward from 2026-06-12

AI primitives upgrade plan at `plans/2026-06-12-ai-primitives-upgrade.md` (step 0 of 19) is paused — user review pending before Wave 1 execution.
