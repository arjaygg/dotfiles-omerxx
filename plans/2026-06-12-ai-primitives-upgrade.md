# 2026-06-12 — AI Primitives Upgrade Plan

Produced by the `ai-primitives-audit` workflow (32 agents: 5 inventory readers, 3 capability
researchers, 4 gap analysts, 20 adversarial verifiers). All 20 proposals survived verification:
6 **keep**, 14 **modify** (verifier corrections folded into each step below), 0 dropped.

## Executive Summary

Audited 175 components across 5 areas (38 skills, 66 hook-layer items, 26 agents/styles,
18 MCP/cross-tool configs, 27 rules/docs). The architecture is fundamentally sound —
centralized `ai/` hub, pctx gateway, hook enforcement — but has accumulated drift:

- **Live bugs:** `read-before-write-guard.sh` blocks every overwrite with no feedback (Step 2);
  `stack-ship` has no frontmatter so its auto-trigger is dead (Step 6); 4 `ai/commands` files and
  4 agent definitions are lean-ctx-corrupted (Steps 5, 12); `stack-create:115` launches claude
  with `--dangerously-skip-permissions`, violating recorded user feedback (Step 13).
- **Drift:** 4 real dirs shadow `ai/skills` symlinks, 12 symlinks uncommitted (Step 1);
  Codex/Gemini consume a stale or empty skill surface (Steps 17, 19).
- **Unused paid-for capability:** Agent Teams flag is on but unused; Monitor/defer/--bare/
  ConfigChange/TaskCreated events, `~/.agents/skills` standard — all zero usage today.

Three highest-leverage moves: **Step 2** (one-file hook fix ending blind Write-retry loops),
**Step 1** (restores single-source-of-truth invariant), **Step 13** (removes the standing
permission bypass from the headless fleet).

## Current State

**Skills (38 in active inventory; 63 dirs in ai/skills):** Strong coverage and ~95% frontmatter
discipline; stack family and watchdog family well-designed. Issues: 4 non-symlink dirs in
`.claude/skills`, 12 untracked symlinks, 8 `.bak` files, CI trio overlap, `stack-ship` missing
frontmatter, `migration-clean` missing SKILL.md entirely.

**Hooks (27 wired, 28 unwired on disk):** Consolidated v2 gates (pre-tool-gate-v2,
post-tool-analytics) are fast and well-built. Issues: read-before-write-guard misfires on all
overwrites; 11-hook UserPromptSubmit chain spawns login shells + a 3s kubectl call per prompt;
todo-gate re-parses the whole transcript with python3 on every Stop for a tool that is no longer
used; dead-hook graveyard and 5 parallel plan-naming-enforcer implementations.

**Agents/styles:** 7/11 subagents have full frontmatter; 4 are lean-ctx-corrupted with none.
No `ai/agents/` source of truth — agents break the repo's own symlink convention. Runtime litter
(webhook-server.log) inside the agents dir.

**MCP/cross-tool:** pctx gateway healthy, paths verified alive. Issues: Cursor skills/output-styles
symlinks dangle; Gemini sees ~1 of 63 skills; Codex populates a deprecated skills path; tracked
`.codex/config.toml` drifted from live (model pin, hooks key); exa/notebooklm are Claude-only.

**Rules/context:** Always-loaded kernel ≈ 12.6K tokens (~7x a lean kernel); `RTK.md` @-include is
a dead link; `global-developer-guidelines.md` is an alias symlink double-imported everywhere;
monitor-patterns/qmd-usage are reference libraries paying rent in every session.

## Capability Research Highlights

**Claude Code (installed v2.1.175)** — <https://code.claude.com/docs/en/>
- Skills/commands unification + `disable-model-invocation`, `disallowed-tools`, named-argument
  substitution, progressive disclosure — <https://code.claude.com/docs/en/skills>
- Hooks: ~30 events incl. ConfigChange, TaskCreated/TaskCompleted, TeammateIdle; JSON
  permissionDecision deny/defer; `async`/`args` exec-form fields — <https://code.claude.com/docs/en/hooks>
- Subagent frontmatter: `memory: user|project|local` (v2.1.33), `isolation: worktree` (v2.1.49),
  spawn restrictions — <https://code.claude.com/docs/en/sub-agents>
- Agent Teams (experimental; flag already on in settings.json) — <https://code.claude.com/docs/en/agent-teams>
- Monitor tool (zero tokens when silent, v2.1.98); `/loop` + cron tools — <https://code.claude.com/docs/en/scheduled-tasks>
- Headless: `--bare` (v2.1.81, requires API-key auth), PreToolUse `defer` + `-p --resume`
  (v2.1.89) — <https://code.claude.com/docs/en/headless>
- Routines (cloud, cron-only triggers ≥1h; no event triggers on this account) — <https://code.claude.com/docs/en/routines>
- Agent view / `claude agents --json` (research preview) — <https://code.claude.com/docs/en/agent-view>

**Codex (installed CLI 0.130.0)** — <https://developers.openai.com/codex/>
- `~/.agents/skills` (agentskills.io) is the standard skill root; `~/.codex/skills` is deprecated;
  symlinks followed — <https://developers.openai.com/codex/skills>
- Lifecycle hooks GA (2026-05); plugins; AGENTS.md layering — <https://developers.openai.com/codex/hooks>
- `gpt-5.5` is the recommended default; `gpt-5.3-codex` removed Apr 2026 — <https://developers.openai.com/codex/models>

**Gemini CLI (installed 0.42.0; stable is 0.45.0)** — <https://github.com/google-gemini/gemini-cli>
- Extensions bundle MCP + TOML commands + hooks + policies, `gemini extensions link` —
  <https://github.com/google-gemini/gemini-cli/blob/main/docs/extensions/reference.md>
- Hooks with Claude-compat (`gemini hooks migrate`, CLAUDE_PROJECT_DIR alias) —
  <https://github.com/google-gemini/gemini-cli/blob/main/docs/hooks/index.md>
- Policy engine TOML (user tier; workspace tier broken upstream #18186) —
  <https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/policy-engine.md>
- Agent Skills via `~/.agents/skills` alias — <https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/skills.md>
  ⚠ Two verifiers disagreed on whether installed 0.42.0 ships skill support — confirm on-machine
  (or upgrade to ≥0.45) before relying on it (see Cautions).

## Improvement Waves

### Wave 1 — Hygiene & Safety (quick wins)

## Step 1 — Repatriate real skill dirs, commit the 12 symlinks, purge .bak litter
**Files:** `.claude/skills/{migration-watchdog,lean-ctx,migration-clean,auc-prod-db-monitor}/`, `ai/skills/{migration-watchdog,lean-ctx,migration-clean}/`, `.claude/skills/` (12 untracked symlinks), `~/.claude/commands/migration-clean.md`, `.cursor/hooks/*.bak`, `scripts/check-skill-drift.sh` (new), `setup.sh`
**Accepts:** Every entry in `.claude/skills/` is a symlink into `ai/skills/` (check: `find .dotfiles/.claude/skills -maxdepth 1 -type d` returns nothing un-quarantined); `git status` shows no untracked skills or `.bak` files; `check-skill-drift.sh` exits non-zero on a planted real dir.
**Impact/Effort:** high/M  |  **Verdict:** keep
Reconcile `.claude/skills/migration-watchdog` vs `ai/skills/migration-watchdog` — verifier confirmed these are **two different designs** (continuous manager vs one-shot health check), so this is a choose-or-split human decision, not a merge. Promote lean-ctx to `ai/skills/` (install.sh has no hardcoded skill-dir paths — safe). Collapse migration-clean's divergent copies into one `ai/skills/migration-clean/SKILL.md`; replace `~/.claude/commands/migration-clean.md` with a symlink (don't delete a live user file). Quarantine `auc-prod-db-monitor` with `disable-model-invocation: true` (it is tracked, not untracked — see Cautions). Commit the 12 symlinks **normalized to relative `../../ai/skills/...` targets**, and fix `setup.sh ln -sfn` to emit relative links as follow-up. Add `check-skill-drift.sh` so this drift class can't recur.
- [ ] migration-watchdog choose-or-split decision recorded in plans/decisions.md
- [ ] 12 symlinks committed relative; 4 `.cursor/hooks/*.bak` + 2 lean-ctx `.bak` deleted

## Step 2 — Fix read-before-write-guard.sh (blocks ALL overwrites, no model feedback)
**Files:** `.claude/hooks/read-before-write-guard.sh`, `.claude/hooks/pre-tool-gate-v2.sh`, `.claude/settings.json`
**Accepts:** Write to an existing file succeeds after a Read in the same session; a Write without prior Read returns a JSON `permissionDecision: deny` with a visible reason; `test-hook.sh` fixtures pass.
**Impact/Effort:** high/S  |  **Verdict:** keep
The hook does `[ -f "$FILE" ] && echo ... && exit 2` — blocks every overwrite, never consults the read log its own header claims to check, and emits the reason on stdout which exit-2 hooks don't feed back (model retries blindly; this bit the current session repeatedly). Preferred shape per verifier: **fold into pre-tool-gate-v2.sh's Section 3a** (which already reads `/tmp/.claude-read-log-$(id -u)` for Edit) extending it to Write, gated on `-f "$FILE_PATH"` so new-file Writes pass; delete the standalone hook + its settings.json matcher. Uses PreToolUse JSON deny (<https://code.claude.com/docs/en/hooks>).

## Step 3 — Reconcile the hook archive, delete .bak litter, add a ConfigChange integrity hook
**Files:** `.claude/hooks/` (~12 superseded scripts → `archive/`), `.claude/hooks/fixtures/`, `.claude/hooks/ts/plan-naming-enforcer*.ts`, `.cursor/hooks/*.bak`, `.cursor/mcp.json.bak`, `.gitignore`, `.claude/hooks/config-integrity.sh` (new), `.claude/settings.json`, `.claude/hooks/hook-config.yaml`
**Accepts:** No unwired superseded script remains in `hooks/` root; `git status` clean of `.bak`; `*.bak` in .gitignore; ConfigChange event fires config-integrity.sh (verified with a live settings edit) and stays exit-0 advisory.
**Impact/Effort:** medium/S  |  **Verdict:** modify
`archive/` already exists with **stale older copies** of 8 of the 12 scripts — this is a reconciliation (overwrite archive with current versions, delete root copies), not a clean `git mv`. Move matching `fixtures/` dirs too (test-hook.sh silently skips archived hooks). There are **5** plan-naming-enforcer implementations (.sh/.js/.rs + 2 .ts), not 3. All 7 `.bak` files are untracked — plain `rm`. **Do NOT wire drift-guard.sh to ConfigChange** — it's a git branch-drift advisory, deliberately off in hook-config.yaml. Write a new `config-integrity.sh` for the ConfigChange event (v2.1.49; symlink hot-reload fixed v2.1.139/140) checking symlink integrity of `~/.claude/settings.json` etc.; filter `source` to `*_settings` or it fires on every skill edit.

## Step 4 — Clean up the global-developer-guidelines.md alias and double-imports
**Files:** `ai/rules/global-developer-guidelines.md` (symlink — delete), `.claude/CLAUDE.md`, `.gemini/GEMINI.md`, `.cursor/rules.md`, `.cursor/rules/`, `.claude-global/CLAUDE.md`, `.claude/scripts/validate-agent-guidance.sh`, `ai/rules/hyper-atomic-commits.md`, `docs/agent-configuration-architecture.md`, `decisions/0003-universal-constitution-loading.md`, `setup.sh` (rules-symlink loop)
**Accepts:** `global-developer-guidelines` appears nowhere in the repo (`grep -r` count = 0 outside decisions history); `validate-agent-guidance.sh` passes; fresh-session `/context` in Claude and Gemini shows no regression.
**Impact/Effort:** low/S  |  **Verdict:** modify (downgraded from high)
Verifier killed the premise: the file is **already a symlink** to agent-user-global.md (commit 212a9ea), and Claude Code dedupes @-imports by realpath — the claimed 2.5K-token saving is zero. Still worth S effort as confusion-elimination: delete the alias, remove redundant import lines (GEMINI.md:7, .cursor/rules.md:12), update validate-agent-guidance.sh lines 61/72/76 (it hard-requires the file — deleting without this breaks validation), repoint prose references, amend decisions/0003. Only Gemini/Cursor might save tokens, and only if their loaders don't realpath-dedupe — measure, don't assume.

## Step 5 — Restore corrupted ai/commands files; give commands the same symlink discipline as skills
**Files:** `ai/commands/{aside,hookify,instinct-export,silent-failure}.md`, `ai/commands/smart-commit.md`, `.claude/commands/{smart-commit,migration-clean}.md`, `.cursor/commands/smart-commit.md`, `ai/skills/continuous-learning/SKILL.md` (line 92), `setup.sh`, `AGENTS.md`
**Accepts:** No file in `ai/commands/` contains lean-ctx artifacts (`grep -rL 'lean-ctx:' ai/commands/` covers all); smart-commit exists exactly once as source; `setup.sh` has a `link_commands_from_dir` pass; convention documented in AGENTS.md.
**Impact/Effort:** medium/S  |  **Verdict:** modify
aside/hookify/instinct-export contain lean-ctx compression garbage; silent-failure.md is a saved `404: Not Found` body. **Git restore is impossible** — all four were committed already-corrupted (single commit a815be3, sourced from the Everything Claude Code repo). Restore the three from ECC upstream; delete silent-failure.md (likely never existed upstream as a command). The corrupted files are **dormant, not live** — the active defect is the dangling `/instinct-export` reference at continuous-learning/SKILL.md:92. smart-commit is **triplicated** (ai/, .claude/commands, .cursor/commands — Cursor copy genuinely diverged); reconcile to one source. Then pick one convention (commands-as-skills vs ai/commands + frontmatter — the spec merged the two systems) and document it.

### Wave 2 — Modernization (current Claude Code features)

## Step 6 — Skill frontmatter modernization sweep
**Files:** `ai/skills/{stack-ship,watchdog-cron-setup,migration-watchdog-auto,migration-watchdog,watchdog-remediate,hyper-commit-setup,auc-dev-a,auc-dev-b,auc-dev-c,ado-workitem,autoresearch}/SKILL.md`
**Accepts:** stack-ship's loaded description is a real trigger description (not `Skill: stack-ship`); `grep -l disable-model-invocation ai/skills/*/SKILL.md` lists the cron/user-only skills; one live watchdog cron tick completes after the change.
**Impact/Effort:** high/M  |  **Verdict:** modify
Add missing YAML frontmatter to stack-ship (auto-invocation of the flagship merge skill is currently dead). Add `disable-model-invocation: true` to user/cron-only skills to cut always-loaded descriptions (~64 skills load descriptions today). **Mandatory verifier correction:** the CronCreate prompt in watchdog-cron-setup/SKILL.md:74 must be rewritten to a bare leading-slash prompt (`/migration-watchdog-auto ...`) and the cron re-registered — the field blocks Skill-tool invocation, so the current prose prompt **will** break every tick; alternatively stage that flag in a second PR after one verified tick. Audit how auc-dev-a/b/c are invoked before flagging them. Give watchdog-remediate a named `playbook` argument ($playbook substitution — substitution is real, typed/enum/default declaration is NOT; route in the body). Enforce migration-watchdog's READ-ONLY contract with `disallowed-tools: Edit, Write, NotebookEdit` (note: restricts the coordinating session only, not its 4 subagents — partial but better than prose). Spec: <https://code.claude.com/docs/en/skills>.

## Step 7 — De-tax the UserPromptSubmit hook chain
**Files:** `.claude/settings.json` (all hook events), `.claude/hooks/env-preflight.sh`, `.claude/hooks/{qmd-sync,prompt-capture,prompt-score-correction}.sh`
**Accepts:** Zero `bash -lc` wrappers remain in settings.json (was 30); `env-preflight.sh` serves a cached kubectl verdict within 60s TTL (no live `kubectl auth can-i` on consecutive prompts); prompt-to-first-token latency visibly improved on a k8s-keyword prompt.
**Impact/Effort:** high/M  |  **Verdict:** modify
Verifier corrected the premise: matching hooks run in **parallel**, so blocking latency = slowest hook + per-spawn login-profile sourcing, not a serial sum. Therefore: **keep** (a) exec-form conversion — replace every `bash -lc 'bash "$HOME/..."'` with `{"command": "bash", "args": ["<abs path>.sh"]}` (no login shell re-sourcing), and (b) the env-preflight fix — 60s-TTL cache for the 3s `kubectl auth can-i` + narrower keyword regex (it must stay sync; it injects additionalContext). Mark qmd-sync/prompt-capture/prompt-score-correction/tmux-bridge `"async": true` (minor; they already self-background). **Dropped per verifier:** the consolidated dispatcher (would convert max() into sum() — a regression) and `once: true` (ignored in settings files). Fields: <https://code.claude.com/docs/en/hooks>.

## Step 8 — Replace todo-gate transcript scraping with event-driven task-gate
**Files:** `.claude/hooks/todo-gate.sh` (→ `task-gate.sh`), `.claude/hooks/task-event-tracker.sh` (new), `.claude/settings.json`, `.claude/hooks/hook-config.yaml`
**Accepts:** Stop path spawns zero python3 processes; gate reads O(1) state from `/tmp/.claude-task-state-$CLAUDE_SESSION_ID`; stopping with live background tasks or crons produces a warning; runs in `warn` level until counts proven, then `block`.
**Impact/Effort:** medium/M  |  **Verdict:** keep
todo-gate spawns ~5 python3 processes re-parsing the full JSONL transcript on every Stop, gating on TodoWrite — which 0 of the 40 most recent transcripts use (the verifier's empirical justification; the "off by default since v2.1.142" claim was unsupported). Rebuild on TaskCreated/TaskCompleted hook events (verified in installed 2.1.175) + Stop payload's `background_tasks`/`session_crons` fields — the orphaned-background-work warning is genuinely uncovered today and pays regardless of task-list usage. **Capture live payload schemas first; warn-before-block is mandatory** (no TaskUpdated event exists — counter desync on cancellation is real). jq, not python3.

## Step 9 — Consolidate the CI trio into one /ci skill; retire the token-burning poll agent
**Files:** `ai/skills/ci/SKILL.md` + `references/` (new), `ai/skills/{ci-monitor,ci-watch,ci-status}/` (alias stubs → delete next cycle), `.claude-global/CLAUDE.md` (CI Monitoring section — tracked source of `~/.claude/CLAUDE.md`), `ai/skills/claude-auto/SKILL.md` (line 458 ref), `ai/rules/monitor-patterns.md`
**Accepts:** `/ci` routes monitor|watch|status from `$ARGUMENTS` (empty → status); a CI run is watched end-to-end by Monitor with `plans/ci-status.md` written by **shell**, zero LLM polling turns; `/ci-watch` alias still resolves for one deprecation cycle; CLAUDE.md section updated in the final commit of the stack.
**Impact/Effort:** high/M  |  **Verdict:** modify (merges two verified proposals)
Merges the skills-hygiene consolidation and the hooks-automation poll-retirement (they overlap). ci-watch today launches a headless `claude -p` agent polling gh 10× at 90s — ~10 paid LLM turns for work pure shell can do, with `--allowedTools Bash,Read,Write` unattended. Replace with the Monitor primitive (v2.1.98, zero tokens silent) + poll-and-diff shell loop (monitor-patterns Pattern 1/6) writing `plans/ci-status.md` on change. Verifier corrections: **`claude --bg` fallback dropped** (flag absent from the installed CLI's --help — see Cautions); detached watching = pure shell via `Bash(run_in_background: true)`/nohup, every ci-watch reaction is a fixed shell command anyway; if an LLM reaction is ever needed, one `claude -p --bare` call at completion, never per-poll. Argument routing is body-level (`argument-hint:` for display; no frontmatter enum/default exists). Verify Monitor's command can write files; if sandboxed read-only, run the loop via background Bash and keep Monitor as the event channel. Keep `ai/rules/monitor-patterns.md` canonical; the skill's references/ holds only the CI-specific recipe (no-policy-duplication rule).

## Step 10 — Targeted progressive-disclosure splits (scoped down)
**Files:** `ai/skills/watchdog-remediate/SKILL.md` + `references/playbooks/{circuit-breaker,timeout-extend,stale-pods,db-locks}.md` (new), `ai/skills/stack-ship/SKILL.md`, `.claude/scripts/stack-ship.sh`
**Accepts:** A remediation run loads exactly one playbook file (~70% body reduction, ~1.1K tokens/run, measured by body token counts before/after — NOT `/context`, which reflects frontmatter-only loading); stack-ship SKILL.md contains no inline bash duplicating `stack-ship.sh`.
**Impact/Effort:** medium/S  |  **Verdict:** modify (scoped from 4 targets to 2)
Verifier cut the scope: watchdog-remediate is the only true progressive-disclosure win (4 mutually exclusive playbooks). stack-ship: **delete** the ~90-line inline bash (it duplicates the canonical `.claude/scripts/stack-ship.sh`; scripts execute without entering context — strictly better than a reference file); the "conflict-recovery procedure" to move doesn't exist (Phase 2 is a TODO). **Dropped:** migration-watchdog prompt extraction (all 4 prompts dispatch every run — zero savings) and autoresearch (already a router; its references/ symlinks into the upstream plugin). Depends on Step 1 resolving the migration-watchdog duplicate first.

## Step 11 — Convert monitor-patterns and qmd-usage rules into hub skills
**Files:** `ai/rules/{monitor-patterns,qmd-usage}.md` (→ stubs for one release), `ai/skills/monitor-patterns/SKILL.md` (new), `ai/skills/qmd-routing/SKILL.md` (new), `.claude/CLAUDE.md`, `ai/rules/agent-user-global.md` (line 233 pointer), `ai/skills/ci-monitor/SKILL.md` (line 84 ref)
**Accepts:** Neither rule is @-included in `.claude/CLAUDE.md`; fresh-session always-loaded context drops ~2K tokens (`/context` before/after); a "watch the deploy" prompt still triggers monitor knowledge; a team-OKR question still triggers a qmd search.
**Impact/Effort:** medium/M  |  **Verdict:** modify
These are reference libraries needed in ~1 of 10 sessions but paid for in 10 of 10. Skill-ify with **trigger-rich descriptions** (encode the qmd collection→topic table into the description itself — proactive-search regression is the main risk; keep a 2-line kernel pointer and stub the rule files one release). Cross-tool win is **Claude + Codex only** (`~/.codex/skills` already symlinks into ai/skills with `[[skills.config]]` management); the Gemini benefit is unproven on installed 0.42.0 (see Cautions). Repoint ci-monitor's reference alongside.

### Wave 3 — Orchestration & Cross-Tool (bigger bets)

## Step 12 — Promote subagents to ai/agents/ source-of-truth with modern frontmatter
**Files:** `ai/agents/` (new), `.claude/agents/*.md` (11 → symlinks), `.claude/agents/{database-reviewer,go-build-resolver,security-reviewer,silent-failure-hunter}.md` (rebuild), `.claude/agents/webhook-server.{py,sh}` (→ `.claude/scripts/`), `webhook-server.log` (delete), `setup.sh`, `ai/README`
**Accepts:** `.claude/agents/` contains only symlinks into `ai/agents/`; all 11 agents have name/description/model/tools frontmatter; cicd-audit declares `memory: project`; go-build-resolver and cicd-auto-retry declare `isolation: worktree`; cicd-monitor's spawn list restricts to cicd-review/cicd-audit.
**Impact/Effort:** high/M  |  **Verdict:** keep
Mirrors the skills symlink pattern (setup.sh needs a **per-file** loop — agents are flat .md, unlike skill dirs). The 4 lean-ctx-corrupted agents predate all git history (committed corrupted from ECC) — rebuild from scratch or re-source upstream. Frontmatter capabilities: `memory:` scopes (v2.1.33), `isolation: worktree` (v2.1.49 — writes under `.claude/worktrees/`, not `.trees/`; scope to agents that don't touch stack tooling), spawn restrictions — **verify current syntax (`Task(type)` vs `Agent(type)`) against <https://code.claude.com/docs/en/sub-agents> before writing**. Note in ai/README that agents/ is Claude-specific.

## Step 13 — Harden the headless fleet (kill --dangerously-skip-permissions)
**Files:** `ai/skills/stack-create/SKILL.md` (line 115), `ai/skills/claude-auto/SKILL.md`, `.claude/skills/auc-prod-db-monitor/SKILL.md`, `.claude/hooks/pre-tool-gate-v2.sh`, `.claude/settings.json`
**Accepts:** `grep -r dangerously-skip-permissions ai/ .claude/` returns nothing; a headless auc-prod-db-monitor mutation pauses at a PreToolUse `defer` and resumes via `claude -p --resume` after approval; `skipDangerousModePermissionPrompt` removed from settings.json.
**Impact/Effort:** high/M  |  **Verdict:** modify
stack-create:115 launches tmux claude with `--dangerously-skip-permissions` — directly violating the recorded feedback memory ("never add it from tmux keybindings"). Replace with plain `claude` + `autoAllowBashIfSandboxed` + `autoMode.hard_deny` (v2.1.136). Defer queue (v2.1.89): scope to genuinely headless runs only — auc-prod-db-monitor and claude-auto's CI path qualify; **watchdog-remediate does NOT** (in-session CronCreate). Detection via self-exported `CLAUDE_HEADLESS=1` in launcher scripts; pair every defer with a notification + pending-approval lockfile so hourly ticks don't stack. `--bare` (v2.1.81) **requires ANTHROPIC_API_KEY/apiKeyHelper (OAuth disabled)** — gate adoption on key availability, fall back to plain `-p`; restrict --bare to read-only ticks (it skips hooks, i.e. the whole enforcement layer). ci-watch's green-path deploy stays non-deferred (fire-and-forget value) — moot if Step 9 lands first.

## Step 14 — Adopt Agent Teams for tech-lead (lead = main session)
**Files:** `ai/skills/tech-lead/SKILL.md`, `.claude/settings.json` (`teammateMode: "auto"` + hook wiring), `.claude/hooks/teammate-quality-gate.sh` (new), `ai/rules/agent-user-global.md` (Task Tracking Discipline section)
**Accepts:** `/tech-lead` creates a team with the **main session as lead**, spawns named specialists from existing agent definitions, coordinates via the shared task list with blocks/blockedBy; an idle teammate with an incomplete claimed task gets rejected by the gate; no hardcoded project state remains in the skill (reads `plans/active-context.md`).
**Impact/Effort:** high/L  |  **Verdict:** modify
The `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` flag is on (settings.json:5) and entirely unused, while tech-lead hand-rolls what teams provide natively — and has already rotted (hardcoded dead branch/PR at SKILL.md:64-67). Verifier corrections: the lead is fixed to the creating session and **no nested teams** exist, so delete the background-TL + SendMessage-relay shape entirely; `teammateMode: "auto"` not "tmux" (Ghostty doesn't support split panes); **drop the migration-watchdog standing-team adopter** (team state dies with the session — incompatible with cron ticks; its per-tick Agent fan-out is already the right shape); pin teammates to Sonnet (they don't inherit /model — respects opusplan routing). Keep CLAUDE_CODE_TASK_LIST_ID protocol for non-team spawns. Docs: <https://code.claude.com/docs/en/agent-teams>. Experimental — keep the old flow documented as fallback.

## Step 15 — Pilot one cloud Routine; codify the access boundary
**Files:** (pilot first — then) `ai/skills/routines-setup/SKILL.md` (new), `decisions/000N-cloud-routines-scope.md` (new; next free number — 0006 may be taken by Step 17), `ai/skills/watchdog-cron-setup/SKILL.md` (local-only scope note)
**Accepts:** One nightly cron routine runs successfully against a verifiably connectable repo; the decision record documents what cloud routines can/cannot reach (ADO: no; axos-financial EMU: verified yes/no); watchdog skills carry the local-only note.
**Impact/Effort:** low-medium/S  |  **Verdict:** modify (heavily scoped down)
Verifier checked the **live API**: routines support only `cron_expression` (≥1h) or `run_once_at` — no GitHub-event or HTTP triggers on this account, so the flagship claude-auto-via-event idea is dead; claude-auto stays on GitHub Actions. The user's cloud environment binds to the personal arjaygg account with zero connectors; axos-financial is an EMU org — **assume unreachable until proven**. Sequence: verify access → pilot one routine → only then write the setup skill (grounded in the real API: environment_id required, UTC cron, no API delete) + decision record. The watchdog correctly stays local (StrongDM/K8s/DB access). Identity risk: routines act as your GitHub identity with no prompts — the arjaygg-vs-EMU memory applies.

## Step 16 — Hybrid session-hub: add native agent data, migrate dispatch to daemon sessions
**Files:** `tmux/scripts/session-hub.sh`, `tmux/scripts/_session-hub-new.sh`, `tmux/scripts/claude-task-launcher.sh`, `.claude/settings.json` (`worktree.bgIsolation`), `.claude/commands/session-*.md` (NOT deleted)
**Accepts:** session-hub lists daemon-hosted sessions from `claude agents --json --all` alongside tmux and JSONL scans; background dispatches survive terminal close and appear in `/resume`; `worktree.bgIsolation` is explicitly set; all five session-* commands still work.
**Impact/Effort:** medium/L  |  **Verdict:** modify (replacement → augmentation)
Agent view covers **live daemon sessions only** — most of session-hub's value (persisted-session JSONL scan, handoff/defer taxonomy, Cursor integration) has no native equivalent, so augment, don't replace. No PR-status field exists in `agents --json` (verified live: cwd/id/kind/name/sessionId/startedAt/state/waitingFor). **Gate the dispatch migration on verifying `claude --bg` exists in the installed CLI** — verifiers disagreed (see Cautions). Check upstream bug anthropics/claude-code#36205 (EnterWorktree hooks in bg sessions) before migrating any dispatch path; the worktree-create.sh hook redirects to `.trees/` and must keep working. Research preview: <https://code.claude.com/docs/en/agent-view>.

## Step 17 — Adopt ~/.agents/skills as the single cross-tool skill root
**Files:** `setup.sh` (replace lines 77-93: Codex per-skill loop + broken Cursor section), `~/.agents/skills` (live symlink → `ai/skills`), `~/.codex/skills/` (prune links resolving into ai/skills only), `~/.gemini/skills/` (remove nested `ai` + self-referencing `skills` cruft), `docs/agent-configuration-architecture.md`, `decisions/0006-agents-skills-standard-path.md` (new)
**Accepts:** `readlink ~/.agents/skills` → `~/.dotfiles/ai/skills`; Codex discovers hub skills from the standard root (spot-check `codex` skill listing); no dangling `~/.cursor/skills` link; decision record committed.
**Impact/Effort:** high/M  |  **Verdict:** keep
One `ln -sfn` replaces three divergent distribution mechanisms. Verified at source: installed codex-rs 0.130.0 already registers `$HOME/.agents/skills` and follows symlinks — **no CLI bump needed** — and marks `~/.codex/skills` deprecated (setup.sh currently populates a deprecated path with 68 links). Gemini's skillLoader globs only `SKILL.md` and `*/SKILL.md`, so today's nested `~/.gemini/skills/ai` layout yields **zero** discovered skills. Cautions: prune only Codex links resolving into ai/skills — the only-missing pass also linked unpromoted `.claude/skills` locals (keep until Step 1 promotes them); transition is safe (Codex scans both roots, dedupes by precedence); create `~/.agents/skills` via explicit ln in setup.sh, not a tracked `.agents/` stow dir. Codex skills: <https://developers.openai.com/codex/skills>.

## Step 18 — Sync .codex/config.toml to live; defer exa-in-pctx behind key delivery
**Files:** `.codex/config.toml` (tracked ← live), `.mcp.json` (optional `${HOME}` expansion), nushell `env.nu` + zsh profile (EXA_API_KEY, when pursued)
**Accepts:** `diff <(cat ~/.codex/config.toml) .codex/config.toml` clean (model=gpt-5.5, effort=high, `codex_hooks` key, trust entries); no `${env:...}` strings in pctx.json command fields.
**Impact/Effort:** medium/S  |  **Verdict:** modify (2 of 3 parts dropped/deferred)
Verifier empirically killed part 2: pctx 0.6.0 passes `${env:VAR}` in stdio `command` literally (ENOENT) — env substitution is for auth-token strings only; **don't add a templating step that breaks pure stow**. Part 1 deferred: exa was deliberately removed from pctx.json in PR #142, and `EXA_API_KEY` is currently set **nowhere** (env, zsh, nushell, settings) — even Claude's native exa entry likely fails at call time. Before re-adding: export the key in both shells (per user convention), verify pctx propagates env to npx children with a real `Exa.webSearchExa` call, never commit the key plaintext. Part 3 keeps: the tracked config.toml pins `gpt-5.3-codex` (removed from ChatGPT sign-in Apr 2026 — <https://developers.openai.com/codex/models>) while the live file self-mutated to gpt-5.5/high; sync tracked←live per AGENTS.md repo-truth rule (`~/.codex/config.toml` is a regular file, not a symlink).

## Step 19 — Package the Gemini surface as a linked extension (hooks + policies first)
**Files:** `.gemini/extension/gemini-extension.json` (new), `.gemini/extension/hooks/hooks.json` (new), `.gemini/extension/policies/*.toml` (new), `.gemini/extension/commands/` (incremental), `.gemini/settings.json` (dedupe pctx), `setup.sh`, `~/.gemini/**/*.bak` (delete)
**Accepts:** `gemini extensions link ~/.dotfiles/.gemini/extension` installed; commit-on-main and PR-title guards fire in a Gemini session; policy denies match Claude's permissions.deny for tool-level rules; smart-commit works as a TOML command; no `.bak` files under `~/.gemini`.
**Impact/Effort:** medium/L  |  **Verdict:** keep
Gemini is the furthest-behind consumer: zero working commands (the lone `smart-commit.md` symlink is dead config — Gemini commands require TOML), zero enforcement hooks, zero policies, while Codex already has all three. `gemini hooks migrate` converts the two portable guards; the CLAUDE_PROJECT_DIR alias lets `.claude/hooks` scripts run unmodified. Target the **user policy tier** (workspace tier broken upstream #18186). Phase it: hooks+policies first, commands incrementally via a small generator script (avoid a second hand-maintained source of truth). Context-saving from global deny applies only to tool-level rules without argsPattern — don't promise it for Bash prefix denials; commit-on-main blocking comes from the migrated hook, not a static policy. Docs: <https://github.com/google-gemini/gemini-cli/blob/main/docs/extensions/reference.md>.

## Deferred / Cautions

- **auc-prod-db-monitor stays quarantined** (Step 1) — its 8-year hourly headless loop runs
  `claude -p` with hardcoded PROD `CREATE INDEX` instructions, `--allowedTools Bash,Read,Write`,
  and no approval gate, violating the READ-ONLY pattern of every sibling. Do not re-enable until
  it is redesigned on Step 13's defer-queue model. (It is tracked in git, contrary to the
  inventory's "untracked" label.)
- **`claude --bg` existence is disputed** — one verifier found it absent from the installed CLI's
  `--help`; another verified it via changelog (v2.1.140-144) against the same v2.1.175. Resolve
  empirically before Steps 9/16 rely on it; the plan text already routes around it where possible.
- **Gemini skills support on installed 0.42.0 is disputed** — one verifier read skillLoader globs
  in the bundle, another found zero 'skill' strings in it. Confirm locally or upgrade (stable is
  0.45.0) before counting the Step 11/17 Gemini benefit.
- **Agent Teams and agent view are research previews** — API may shift; keep fallbacks documented
  (Steps 14, 16).
- **Routines access boundary** — ADO is unreachable from cloud sandboxes; axos-financial (EMU)
  access unproven; personal-vs-EMU GitHub identity risk applies (Step 15).
- **exa re-add reverses a recorded decision** (PR #142) and lacks a key-delivery story — deferred
  behind explicit key setup + propagation verification (Step 18).
- **Kernel-cache rule** — Steps 9 and 11 edit `CLAUDE.md`-included files; sequence those edits as
  the final commit of their stacks and start a fresh session after merge.
- **Sequencing dependencies:** Step 10 depends on Step 1 (migration-watchdog reconciliation);
  Step 17's Codex prune depends on Step 1 (skill promotion); Step 13's ci-watch note is mooted by
  Step 9. Everything ships via stack branches — never commit to main.
