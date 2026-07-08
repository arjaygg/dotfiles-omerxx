# Constitution & Hook-Chain Audit — 2026-07-08

**Status: PROPOSAL — awaiting review. No steps below have been executed.**

Requested audit of every doc/hook loaded at SessionStart, UserPromptSubmit, and PreCompact, using two independent Fable subagents (one on hook/runtime mechanics + config-vs-doc drift, one on doc-vs-doc content conflicts), reconciled here. Builds on, and does not duplicate, `plans/2026-07-07-ai-harness-improvement-proposal.md` (still open — Phase 0/#7/#10 there remain unexecuted and are folded into Phase 0 below).

## Headline

Two independent findings converge on the same story: **the enforcement the docs describe and the enforcement that actually runs have diverged**, and **the highest-precedence doc in the chain is itself untracked and stale**. Neither is visible from reading any single file — both only show up by tracing hook execution against live settings and comparing what each doc tells an agent to do against what another doc (or reality) says.

I directly reproduced one of these: this session's own loaded context contains `~/.claude/rules/lean-ctx.md` + the global `CLAUDE.md`'s lean-ctx block instructing "ALWAYS prefer lean-ctx over native: `ctx_read` instead of `Read`, `ctx_search` instead of `Grep`," while `ai/rules/tool-priority.md` — loaded in the same context — explicitly lists "defaulting to lean-ctx for code navigation" as a violation. I resolved it implicitly (followed tool-priority.md) without the conflict ever being flagged. That is exactly the class of problem this audit was asked to find.

---

## Findings (reconciled, re-ranked by actual blast radius)

### Critical

**C1 — Session-init enforcement is dead code.** `pre-tool-gate-v2.sh`'s init-gate Sections 0/0B (and the batching-threshold Section 1B) are all gated on `${CLAUDE_SESSION_ID:-}`, which is never set in hook environments — `session-init-enforcer.sh`'s own comment says the session id arrives in stdin JSON, not as an env var. Verified empirically this session: init was never run, yet no Section-0 block fired. Every doc that says "Grep is blocked until you run init" (`tool-priority.md` §7, `session-init-enforcer.sh`'s injected context every session) is describing enforcement that does not exist — pure token cost, no actual gate. *Fix: read `.session_id` from the JSON already available via jq in the hook, not the env var. Cheap, one hook.*

**C2 — `settings-symlink-guard.sh` auto-adopts privilege-widening runtime settings into the tracked repo file.** It does a blind `cp $LIVE $SRC`, so any in-session change Claude Code persists (skip-permissions prompt, model override) becomes an uncommitted diff in the dotfiles repo automatically. This is very likely *how* `skipDangerousModePermissionPrompt: true` and `model: sonnet` (both flagged 2026-07-07, both still live per `git status`) got there, and why simply reverting them won't stick — the next toggle re-adopts them. You already told me on 2026-07-07 to strip the flag ("skip") — that answer still stands and is folded into Phase 0. *Fix: give the guard a denylist (`skipDangerousModePermissionPrompt`, `permissions.*`, `model`) it surfaces loudly instead of silently folding in.*

**C3 — `~/.claude/CLAUDE.md` (highest-precedence, loaded every session) contains a dead import.** Its "Rules:" line names `@ai/rules/global-developer-guidelines.md` — deleted 2026-06-12 per `decisions/0003`. `progress.md` #12a's "zero live references" sweep only checked the tracked repo, not this untracked private file, so the stale reference survived. It currently no-ops silently (Claude Code skips missing `@`-imports rather than erroring) rather than breaking anything, but it's a live accuracy bug in the one file every session reads first. Separately: whether `~/.claude/CLAUDE.md` *should* be tracked/symlinked is genuinely ambiguous — `AGENTS.md`'s symlink list doesn't actually name this file, so this may be intentionally private rather than drifted. **Needs your call, not mine.** *Fix (independent of that call): delete the dead import line.*

### High

**H1 — Real, live contradiction: lean-ctx "always prefer" vs. tool-priority.md's routing table.** Confirmed directly from this session's own context (see Headline). No precedence note anywhere covers this specific pair — `tool-priority.md`'s "supersedes agent-user-global.md" note doesn't actually name lean-ctx.md, and agent-user-global.md's own lean-ctx content is thin enough that it was never a real conflict (a separate, lower-severity finding, see M-below). *Fix: scope the lean-ctx "always prefer" block to analysis-only reads / non-code text; tool-priority's routing wins for code nav, editing, and shell — one edit to `lean-ctx.md` + the CLAUDE.md block.*

**H2 — ADL-008's hook consolidation has regressed.** One Bash call now spawns ~10 separate hook processes (2 of them full login shells) across PreToolUse/PostToolUse — `pr-title-conventional-guard.sh`, `git-commit-guard.sh`, `pre-push-remote-check.sh`, `rtk-rewrite.sh`, a `lean-ctx hook rewrite` login shell all sit outside `pre-tool-gate-v2.sh`, which ADL-008 explicitly created to eliminate exactly this. `userpromptsubmit.sh` proves the consolidated-dispatcher pattern already works well elsewhere in this repo — it just wasn't kept up as new hooks got bolted on. Compounding: `lean-ctx hook observe` is registered *both* as a standalone UserPromptSubmit entry and inside `userpromptsubmit.sh` — it runs twice per prompt.

**H3 — Declarative hook rules in `hook-config.yaml` are entirely dead.** `hook-rule-loader.sh` (the only thing that reads the yaml) is registered nowhere and sourced by nothing. Every `sed -i`/`echo > file`-blocking rule the yaml claims to enforce, and that `tool-priority.md`'s decision-gate table implies is enforced, isn't. No ADL records retiring it — it just silently stopped being wired up. *Decide: register the loader from `pre-tool-gate-v2.sh`, or delete the yaml so config stops overstating enforcement.*

**H4 — `AGENTS.md` § MCP Gateway is stale and self-contradicting against `tool-priority.md`.** Lists servers as "serena, exa, sequential-thinking, notebooklm, markitdown" (live: Serena/Qmd/LeanCtx/Repomix/Graphify — the 2026-07-07 pass fixed this exact list in the Serena memory but missed `AGENTS.md` itself). Also claims Serena is "no file mutation" — but `tool-priority.md` ranks `Serena.replaceSymbolBody`/`renameSymbol`/etc. as the 1st-priority *editing* tools. Direct doc-vs-doc contradiction on a basic capability question.

**H5 — `agent-user-global.md` contradicts itself on `TaskCreate`.** § TodoWrite Mandate: "Do NOT use TaskCreate — that spawns background agents, not a checklist." § Task Tracking Discipline: "Create the task list first: TaskCreate with all subtasks." Both load in the same doc, same session. Current Claude Code semantics: `TaskCreate` creates task-list entries, doesn't spawn agents — the first section's rationale is also just factually wrong now, not only self-contradictory.

### Medium

- **M1.** `Qmd.query` doc fix (progress.md #4/#5, believed done) landed with wrong field names — docs say `{subqueries: [{type, text}]}`, live schema is `{searches: [{type, query}]}`. The "fix" itself needs a fix.
- **M2.** `LeanCtx.ctxIntent()` referenced directly in `agent-user-global.md`'s fresh-agent init mandate doesn't exist as a top-level call; correct form is `ctxCall({name: "ctx_intent", ...})`. Same class of bug M1 just introduced elsewhere.
- **M3.** `rtk-rewrite.sh` lives only at `~/.claude/hooks/rtk-rewrite.sh` — not in the tracked repo, not a symlink. Confirmed independently by both audits. Violates the repo's own symlink-distribution invariant; breaks on a fresh-machine install.
- **M4.** `session-duration-guard.sh`'s documented "hard block at 500 turns" exits 1, not 2 — for UserPromptSubmit only exit 2 blocks. It doesn't actually block, despite `hook-config.yaml` saying it should.
- **M5.** `plans-healthcheck.sh` silently runs `npm install -g @tobilu/qmd` / `brew install rtk` with no consent on cache miss — and `rtk` is the exact name `RTK.md` itself warns can resolve to the wrong package (`reachingforthejack/rtk`).
- **M6.** `post-tool-analytics.sh` recommends a nonexistent `mcp__context-mode__*` toolset on long output; should point at live LeanCtx equivalents.
- **M7.** Docs/hooks actively route users toward skills disabled in `skillOverrides`: `cap`'s own frontmatter → `/stark`/`/fury`/`/ironman`/`/hawk`; `AGENTS.md` Code Health Routing → `/code-health` + `/hawk`; `agent-user-global.md` → `/monitor-patterns`; `plans-healthcheck.sh` → `/hyper-commit-setup`. (Confirmed NOT a functional problem for `cap` itself — it reads reference prompts directly rather than invoking those as skills — but the standalone entry points the docs advertise are dead ends.) `session-*`/`quarantine-analyst` disables are confirmed-intentional and excluded.
- **M8.** `docs/agent-configuration-architecture.md` claims the project CLAUDE.md chain imports `qmd-usage.md`/`monitor-patterns.md` — neither is imported anywhere. 6 of 9 `ai/rules/*.md` files are orphans (not symlinked, not `@`-imported): `qmd-usage`, `monitor-patterns`, `pctx-session-init`, `hyper-atomic-commits`, `kubectl-efficiency`, `context-window-discipline`.
- **M9.** `context-and-compaction.md` says "lean-ctx CCP is NOT activated — do not run init," while `tool-priority.md` tells agents to use `LeanCtx.ctxSession(action: "load"/"finding")` — which lean-ctx itself documents as the CCP feature. Told it's off and to use it, in the same session.
- **M10.** Global `CLAUDE.md` § Session Artifacts calls `plans/decisions.md`/`progress.md` "ephemeral... archive or delete when starting a new unrelated task" — but `plans/decisions.md` is a live, months-long rolling ADL (001–014) that `AGENTS.md` explicitly governs with promotion rules. A literal reading licenses deleting the ADL log. Scope the delete/archive language to `active-context.md` only.
- **M11.** `plans/pctx-functions.md`'s own "Action needed" callouts (Qmd/LeanCtx drift) are stale — those items were completed per `progress.md` #4/#5 — but see M1: the completion itself has a bug, so this file needs a real update, not just a "done" stamp.

### Low (cleanup, batch into one hygiene pass)

- `log_violation`/`log_operation` calls in `pre-tool-gate-v2.sh` are undefined (only defined in an unsourced archive file) — silent no-ops, fake metrics.
- `settings.json` duplicate keys (`voice.enabled` + legacy `voiceEnabled`; redundant `Read/Write/Edit(*)` alongside `.../dotfiles/**` variants).
- SessionStart still has 5 unconsolidated hook entries — real but low-severity (fires once/session, bounded cost) unlike the per-tool-call regression in H2.
- `/tmp` flag-file litter (134+ files), no session-scoped cleanup.
- `AGENTS.md:73` names `pre-tool-gate.sh` — replaced by `pre-tool-gate-v2.sh` since ADL-008.
- `agent-user-global.md:119` references "the `@plans/active-context.md` include in CLAUDE.md" — no such include exists anywhere in the chain.
- `tool-priority.md`'s "supersedes agent-user-global.md" precedence note names the wrong file — the real conflict is with `lean-ctx.md` (H1), not `agent-user-global.md` (which barely says anything about tool selection).
- Cruft: `~/.claude/rules/lean-ctx.md.bak`, `lean-ctx.md.lean-ctx.bak`.

### Explicitly not flagged (verified intentional)

`skipDangerousModePermissionPrompt`/`model: sonnet` keys themselves (known, deferred, answered by you 2026-07-07 — see Phase 0), `teammateMode`/tech-lead rewrite (separate in-flight work), `session-*` family + `quarantine-analyst` skill disables (confirmed intentional), `permissions.deny` overlapping `pre-tool-gate-v2.sh` §2a/2b (deliberate layering — deny catches fast, hook gives better messages), ADL-014 watchdog quarantine, and the session-artifact global/project layering in general (M10 aside, this is correct per ADL-002 — don't collapse it).

---

## Proposed plan

**Phase 0 — Stop the regression from re-happening — SKIPPED per user decision 2026-07-08, not executed, revisit later**
- [ ] Strip `skipDangerousModePermissionPrompt: true` from `.claude/settings.json` (per your 2026-07-07 "skip" answer)
- [ ] Confirm/revert `model: sonnet` → `opusplan`, or confirm it's a deliberate temporary override
- [ ] Add a denylist to `settings-symlink-guard.sh` (C2) so these can't silently re-appear the moment they're fixed
- [ ] Strip `--dangerously-skip-permissions` from `nushell/config.nu:974` and `tmux/scripts/claude-worktree-select.sh:58` (carried over from 2026-07-07, still unresolved)

**Phase 1 — Fix enforcement that's actively lying about what it does (highest actual risk) — DONE 2026-07-08**
- [x] C1: fix `pre-tool-gate-v2.sh`'s session-id detection (env var → jq-parsed stdin field). Added `EFFECTIVE_SESSION_ID` fallback; Sections 0/0B/1B/3b/6a all switched from `CLAUDE_SESSION_ID` to the real `session_id`. Verified via `bash -n`, pattern search, `git diff --stat`.
- [x] Fix the paired dead flag-matcher in `post-tool-analytics.sh` — confirmed already correct (checks `ctx_intent` via `.tool_input.code`), no change needed.
- [x] H3: decided — **registered `hook-rule-loader.sh`** (not deleted the yaml). The dead `rule.*`/`read-guard.*` layer had genuine `action: block` gaps (`sed -i`, `awk > file`, `echo/printf` redirect, piped `tee`, `node_modules` reads) not covered by `pre-tool-gate-v2.sh`'s existing Section 1/2 checks. Fixed `check_bash_cmd_rules`/`check_read_path_rules`'s block-path to call `_deny()` (same non-blocking-exit-1 bug as C1/M4) instead of falling back to `exit 1`; sourced the loader from `pre-tool-gate-v2.sh` and wired `check_read_path_rules`/`check_bash_cmd_rules` into Sections 1/2. Verified end-to-end with simulated hook payloads: block rules deny correctly, warn rules hint without blocking, benign commands pass silently.
- [x] M4: `session-duration-guard.sh` exit 1 → exit 2 at the 500-turn hard block. Verified `bash -n` and that the 400/300/100 advisory paths still correctly exit 0.

**Phase 2 — Resolve doc-vs-doc contradictions (agents currently make an unstated implicit choice on every one of these)**
- [ ] H1: scope lean-ctx.md's "always prefer" block below tool-priority.md's routing table
- [ ] H4: fix `AGENTS.md` MCP Gateway server list + drop/correct the "no file mutation" claim
- [ ] H5: rewrite `agent-user-global.md`'s TaskCreate sections around current semantics, remove the self-contradiction
- [ ] M9: clarify CCP wording in `context-and-compaction.md` vs. `ctxSession` guidance
- [ ] M10: scope the "ephemeral, archive/delete" language to `active-context.md` only

**Phase 3 — Fix the fixes (M1/M2/M11 — prior drift-remediation introduced new drift)**
- [ ] M1: `Qmd.query` field names — `subqueries/text` → `searches/query`
- [ ] M2: `agent-user-global.md`'s `ctxIntent()` → `ctxCall({name: "ctx_intent", ...})`
- [ ] M11: refresh `plans/pctx-functions.md` to reflect what's actually done vs. still broken

**Phase 4 — Consolidation & hygiene (biggest diff, do last, lowest risk-per-item)**
- [ ] H2: fold `advisor-escalate.sh`, `pr-title-conventional-guard.sh`, `git-commit-guard.sh`, `pre-push-remote-check.sh` into `pre-tool-gate-v2.sh`/`post-tool-analytics.sh`; keep `rtk-rewrite.sh`/`lean-ctx hook rewrite` ordering if merged (they mutate input)
- [ ] Remove the duplicate standalone `lean-ctx hook observe` UserPromptSubmit entry
- [ ] M3: move `rtk-rewrite.sh` into the tracked repo as a real symlinked file
- [ ] M5: gate `plans-healthcheck.sh`'s auto-install behind explicit opt-in
- [ ] M6: point `post-tool-analytics.sh`'s long-output advice at real LeanCtx calls
- [x] M7: decided "scrub references" (skills stay disabled). Rewrote dead `/stark`/`/fury`/`/ironman`/`/hawk`/`/monitor-patterns` mentions in `ai/skills/cap/SKILL.md`, `ai/skills/strange/SKILL.md`, `ai/skills/pr-review/SKILL.md`, `ai/skills/ci-watch/SKILL.md`, `ai/skills/ci-monitor/SKILL.md`, `ai/rules/monitor-patterns.md`. Flagged (not edited, PR-overlap): `ai/rules/agent-user-global.md`, `ai/rules/tool-priority.md` (`/monitor-patterns`, `/hawk`, `/code-health` mentions), `.claude/hooks/plans-healthcheck.sh` (`/hyper-commit-setup` suggestion).
- [ ] M8: wire in or retire the 6 orphaned `ai/rules/*.md` files; fix `docs/agent-configuration-architecture.md`
- [ ] Low-severity batch: delete `.bak` files, dead `log_violation`/`log_operation` calls, duplicate settings keys, stale filenames in AGENTS.md/agent-user-global.md, `/tmp` flag cleanup

**Needs your decision, not mine (Phase-agnostic):**
- [ ] C3: is `~/.claude/CLAUDE.md` intentionally untracked/private, or should it be brought under `ai/` and symlinked? (Fix the dead `global-developer-guidelines.md` import line regardless of the answer.)

---

## Not recommended

- Re-running the full paused 2026-06-12 plan wholesale — most of it (steps 1–3, 8, 9, 10–11, 13-adjacent) is done; only the specific residual items above are worth touching.
- Building new tooling to replace any of this — every fix above is a targeted edit to an existing file, not a new system.
