# Progress — 2026-06-12

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
