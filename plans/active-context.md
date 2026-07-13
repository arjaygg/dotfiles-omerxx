# Active Context

plan: plans/2026-07-13-execution-plan.md
step: Phase 5 of 5
focus: Linux/macOS policy-validation matrix

## Current (2026-07-13) — Phase 0/1 audit checkpoint

- Current child branch adds a deterministic, read-only effective-context report for
  repository, Claude, Codex, and Gemini guidance chains. It follows Markdown imports,
  reads canonical client sources, deduplicates aggregate metrics, reports missing or
  out-of-root references, and enforces chain budgets in CI. No hierarchy or runtime
  configuration was changed.

- This child branch adds a conservative dead-reference scanner. It reports 14 existing
  broken Claude skill symlinks, finds no missing explicit command-script references, and
  gates only changes from the reviewed baseline. No stale link is deleted or repaired.

- The current child branch adds `scripts/bootstrap_check.py`, which renders all six
  manifest clients twice, stages them twice in a marked temporary root, validates
  deterministic hashes, and preserves unmanaged cache sentinels. It reports
  `temporary_stage_writes: true` while keeping `writes_performed: false` and
  `runtime_writes: false`; it does not run mutating setup or live migration.

- The current child branch makes marked proposal staging transactional: all rendered
  files are prepared and fsynced before replacement, opt-in backups are retained on
  success, prior replacements are restored if a later target fails, and unmanaged
  client cache sentinels remain unchanged. Symlinked markers, parents, and targets are
  rejected before writes. Tests exercise rollback, cache preservation, and escape
  rejection; live runtime writes remain untouched.

- The current child branch adds `scripts/learning_signal.py`, an explicit external-ledger
  recorder that hashes private references, rejects raw evidence and unknown fields, and
  marks every record review-required/unapplied. It is not wired into runtime hooks or
  promotion.

- The current child branch extends the signal recorder with `--summarize`: candidates are
  grouped by hashed recurrence key, require two independent sessions or strong evidence,
  and remain `review-required`/unapplied. No proposal or canonical policy is generated.

- The current child branch adds a required ShellCheck baseline gate for the 88 governed
  shell files. One existing SC2259 finding is recorded; no shell or hook behavior is
  changed.

- The current child branch extends the maintained PreToolUse fixture runner with
  event-aware structured-decision validation, explicit empty-output/exit-code contracts,
  malformed-payload and sensitive hash-file denial fixtures, plus a safe pipe rewrite.
  Ten fixtures pass; no runtime hook behavior or permission semantics are changed.

- The current child branch adds a read-only always-loaded instruction compliance check
  for transient session sections, dated current-state headings, absolute user paths, and
  reviewed memory-section debt. The baseline records one existing Gemini memory section;
  CI fails on new or disappearing findings without modifying instruction hierarchy.

- The current child branch adds a read-only file-backed hook reference check. All tracked
  settings references currently resolve, so the reviewed baseline is empty; runtime-only
  commands are intentionally skipped and no missing reference is repaired automatically.

- The current child branch adds a maintained representative-payload matrix for all 14
  configured hook events, including a PreToolUse MCP-call payload. Matrix coverage is
  schema-checked in CI but does not execute hooks or claim ordering/platform behavior.

- The current child branch adds an opt-in conservative permission/hook overlap analyzer.
  It reports 62 potential overlaps in the current settings, remains non-blocking and
  un-baselined pending human review, and leaves exact conflict CI behavior unchanged.

- The policy-validation workflow now runs its read-only checks on both
  `ubuntu-latest` and `macos-latest`; no CI result is claimed until a PR record exists.

- Proposal manifest loading now rejects duplicate client names or runtime targets,
  unsafe identifiers, and runtime paths that escape the home-relative `~/` form;
  focused tests pass without touching live runtime files.

- The isolated bootstrap proof now compares all six staged targets against their
  proposals (`staged_compare_clean: true`), covering both JSON and TOML without
  touching live runtime paths.

- Proposals now require a bounded portable owner, carried into review reports and
  decision entries for explicit expiry accountability.

- Decision-ledger appends now validate existing entries and reject malformed history or
  any prior record with `applied: true`.

- The review-only decision ledger rejects dated `accept` decisions after a proposal's
  `review_after` deadline; no proposal or canonical policy is applied automatically.

- Approved Phase 0 source changes are implemented on `chore/phase0-config-boundary`:
  sanitized settings, detect-only symlink guard, untracked local overlay, and
  proposal-only client bases/generator.
- Current evidence: 154 Python tests pass, 10 maintained PreToolUse fixtures pass, the
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
