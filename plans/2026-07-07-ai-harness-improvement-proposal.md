# AI Harness & Primitives Improvement Proposal — 2026-07-07

**Status: PROPOSAL — awaiting review. No steps below have been executed.**
Consistent with the repo norm set by `plans/2026-06-12-ai-primitives-upgrade.md` (itself still paused), nothing here should be actioned without explicit go-ahead.

## Why this document exists

`/insights` (143 sessions, 2026-06-04 → 2026-07-07) surfaced friction and opportunities. Rather than propose from that report alone, this reconciles it against:
1. The existing paused 19-step audit (`2026-06-12-ai-primitives-upgrade.md`) — much of it has since been executed; re-proposing it would duplicate work.
2. Two newer untracked plans (`2026-06-13-cap-v4-autonomous-rewrite.md`, `2026-06-17-remove-session-handoff.md`).
3. Fresh drift found this session (pctx SDK changes not reflected in docs).
4. Currently uncommitted changes on this branch, which include a live regression.

**Model note:** you asked to switch to Fable — there's no tool for `/model`, so that switch needs to happen on your end (`/model fable`) if you still want it for reviewing this proposal.

---

## 1. Status of the paused 2026-06-12 plan (verified against current repo state)

| # | Step | Status |
|---|------|--------|
| 1 | Repatriate skill symlinks, purge `.bak` | ✅ Done |
| 2 | Fix `read-before-write-guard.sh` | ✅ Done (superseded by `pre-tool-gate-v2.sh` + `hook-config.yaml`) |
| 3 | Hook archive reconciliation, `config-integrity.sh` | ✅ Done |
| 4 | Clean `global-developer-guidelines.md` aliases | ⬜ Unverified |
| 5 | Restore corrupted `ai/commands` | ⬜ Unverified |
| 6 | Skill frontmatter modernization | ⬜ Unverified |
| 7 | De-tax `UserPromptSubmit` chain | 🟡 Partial |
| 8 | `todo-gate` → `task-gate` | ✅ Done |
| 9 | Consolidate CI trio into `/ci` | ✅ Done (router pattern: `ci/SKILL.md` dispatches to ci-watch/ci-status/ci-monitor; ci-watch uses background poller + Monitor, not paid LLM polling) |
| 10–11 | Progressive disclosure; monitor-patterns/qmd-routing → skills | ✅ Done |
| 12 | Promote agents to `ai/agents/` | 🟡 Partial — `ai/agents/` exists, but `.claude/agents/` is a real directory, not a symlink |
| 13 | Kill `--dangerously-skip-permissions` | 🔴 **Not done — regressing** (see §2) |
| 14 | Agent Teams for tech-lead | 🟡 Partial — `teammate-quality-gate.sh` hook exists; uncommitted diff adds `teammateMode: "auto"` but tech-lead SKILL.md rewrite unverified |
| 15–19 | Routines pilot, session-hub hybrid, `~/.agents/skills`, codex sync, Gemini extension | ⬜ Unverified — likely partly superseded by session-handoff removal (§4) |

**Recommendation:** don't re-run the whole plan. Resume only 4, 5, 6, 7, 12 (cheap verification/completion), and re-scope 14–19 against what's actually landed since (Cap v4, session-handoff removal) rather than executing them as originally written.

---

## 2. Critical: fix before anything else

The uncommitted `.claude/settings.json` diff on this branch adds:
```json
"skipDangerousModePermissionPrompt": true
```
This is the exact opposite of paused Step 13, and conflicts with your own standing rule (never enable skip-permissions/don't-ask mode, especially for tmux-launched sessions). Compounding it: `--dangerously-skip-permissions` is still live in `nushell/config.nu:974` (the `hclaude` alias) and `tmux/scripts/claude-worktree-select.sh:58`.

**Proposed fix (before this branch merges):**
- Remove `skipDangerousModePermissionPrompt: true` from the uncommitted settings.json diff, or get explicit confirmation it was intentional and scoped.
- Strip `--dangerously-skip-permissions` from the `hclaude` nushell alias and the tmux worktree-select script.
- The diff also flips `model` to `sonnet` (from `opusplan`) — confirm this is a deliberate temporary debugging override, not an accidental commit candidate.

---

## 3. Drift found this session (not in any existing plan)

pctx's underlying SDK (Qmd, LeanCtx) changed since the 2026-06-12 snapshot; `ai/rules/tool-priority.md` §10 still documents the old shape:

- `Qmd.deepSearch` / `Qmd.search` → now a single `Qmd.query` with typed sub-queries (lex/vec/hyde).
- `LeanCtx.ctxSmartRead` / `ctxMultiRead` (called directly) → now only reachable via `LeanCtx.ctxCall({name, args})` dispatch. (The session-init hook already uses the new shape correctly — only the rule doc is stale.)
- New `Graphify` namespace (`queryGraph`, `listPrs`, `getPrImpact`, `triagePrs`, etc.) is undocumented anywhere in `ai/rules/`, despite being directly relevant to your #1 usage area by session count — Git Workflow & PR Management (24 sessions).
- The `style_and_conventions` Serena memory lists MCP servers (exa, sequential-thinking, notebooklm, markitdown) that no longer exist per live `list_functions` output.

**Proposed fix:** update `tool-priority.md` §10 (Qmd/LeanCtx call shapes), add a Graphify routing entry (especially `listPrs`/`getPrImpact`/`triagePrs` given PR volume), and correct the `style_and_conventions` Serena memory. Small, low-risk, high-signal-to-noise — good first PR on this branch or a follow-up.

---

## 4. Insights findings vs. what already exists

Most of the report's generic suggestions are already solved by existing harness pieces — flagging so effort isn't spent re-building them:

| Insights item | Reality |
|---|---|
| "Standardize branch/worktree/tmux setup into a skill" | Already covered by `stack-create` + `EnterWorktree`/`ExitWorktree` + `agent-user-global.md` worktree conventions |
| "Self-healing CI/CD merge pipeline" | Substantially covered by the `/ci` router + `cicd-auto-retry`/`cicd-monitor` agents (Step 9). Gap: commitlint body-length failures aren't auto-fixed — see below |
| "Parallel forensic investigation swarm" | Cap v4.0 rewrite plan already targets this exact pattern (Workflow-based scope→plan→implement→adversarial-review) for the `cap` skill |
| "Handle model-access errors gracefully" | **Genuine gap** — no session-start check for model/advisor availability |
| "Commit messages must satisfy commitlint body-max-line-length" | **Genuine gap** — no pre-commit hook found enforcing this; repeated CI failures per insights |
| "Files under `.claude/skills/` are gitignored, edit directly" | **Genuine gap** — not stated anywhere in `CLAUDE.md`/`AGENTS.md`; caused a wasted worktree setup |
| "Ask for clarification on ambiguous shorthand before implementing" | **Genuine gap** — behavioral norm, not currently in any rules file |
| "Verify data scope/metrics before presenting analysis" | **Genuine gap** for data-analysis sessions specifically (ADO/team-performance work) |

---

## 5. Proposed plan

**Phase 0 — Safety (do first, blocks nothing else)**
- [ ] Remove/confirm `skipDangerousModePermissionPrompt: true` from uncommitted settings.json
- [ ] Strip `--dangerously-skip-permissions` from `nushell/config.nu` and `tmux/scripts/claude-worktree-select.sh`
- [ ] Confirm `model: sonnet` override in settings.json is intentional/temporary

**Phase 1 — Drift fixes (cheap, high value, no behavior change risk)**
- [ ] Update `ai/rules/tool-priority.md` §10: `Qmd.query`, `LeanCtx.ctxCall` dispatch shape
- [ ] Add Graphify routing table entry, esp. `listPrs`/`getPrImpact`/`triagePrs` for PR workflows
- [ ] Fix stale MCP-server list in `style_and_conventions` Serena memory

**Phase 2 — Close insights-verified gaps**
- [ ] `AGENTS.md`/`CLAUDE.md`: add ".claude/skills/ is gitignored — edit directly, no worktree needed"
- [ ] Pre-commit hook (or extend existing commit-guard) enforcing commitlint body-max-line-length before push, not just at CI
- [ ] `CLAUDE.md` "Communication" note: ask before implementing on ambiguous shorthand (e.g. P0)
- [ ] `CLAUDE.md` "Data Analysis" note: state source counts/metric formulas before computing, for ADO/team-performance work
- [ ] Lightweight session-start check: is the configured model/advisor actually reachable; fail fast with a clear message instead of silent no-response

**Phase 3 — Finish what's partial from the 2026-06-12 plan**
- [ ] Verify/complete steps 4, 5, 6 (cheap checks, likely small or already fine)
- [ ] Symlink `.claude/agents/` → `ai/agents/` (step 12) or confirm why it's intentionally not a symlink
- [ ] Re-scope steps 14–19 against current reality (Cap v4, session-handoff already removed) instead of executing as originally written

**Phase 4 — Scoped-down "on the horizon" items**
- [ ] Wire commitlint auto-fix into `cicd-auto-retry` (incremental, not a new pipeline)
- [ ] Small `stack-create` enhancement: detect gitignored target paths and choose direct-edit vs worktree automatically
- [ ] Consider generalizing Cap v4's adversarial-verify pattern into a reusable skill for non-cap investigations, once Cap v4 itself ships

---

## Not recommended

- Building a new "self-healing CI/CD" system from scratch, or a new "forensic investigation swarm" — both are already substantially covered by existing/in-flight work (`/ci`, Cap v4). Re-proposing them as insights suggests would duplicate effort.
- Adopting Supermemory-adjacent tooling changes beyond what's already decided (per standing memory: file-based memory system was deliberately kept as source of truth).
