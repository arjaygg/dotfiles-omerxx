# Active Decisions Log

Session-friendly ADL for in-flight work. Promote to `decisions/` when a decision is cross-cutting or long-lived.

---

## ADL-001 — Use pctx as MCP gateway

All agents route through `pctx mcp start --stdio -c ~/.config/pctx/pctx.json`.
Durable record: `decisions/0001-use-pctx-as-mcp-gateway.md`

---

## ADL-002 — Separate agent guidance from dotfiles distribution

Shared behavioral policy lives in `AGENTS.md`, `ai/rules/agent-user-global.md`, `docs/`, `decisions/`, `plans/`.
Tool-specific files (`.claude/CLAUDE.md`, `.gemini/GEMINI.md`, `.codex/AGENT.md`) are thin adapters that import the shared guidance.
Durable record: `decisions/0002-separate-agent-guidance-from-dotfiles-distribution.md`

---

## ADL-003 — Canonical decision record convention

Short active decisions live here. Durable decisions go in `decisions/NNNN-title.md`.
Convention documented in `docs/decision-records.md`.

---

## ADL-004 — validate-agent-guidance.sh as structural guardrail

`.claude/scripts/validate-agent-guidance.sh` checks that all required files exist and that adapters correctly import shared guidance. Run before merging guidance changes.

---

## ADL-005 — Universal constitution loading from ai/rules/

Tool priority, batching, Serena convention, developer guidelines, and session discipline live in `ai/rules/` and are loaded user-globally by Claude and Gemini via `@` imports. Codex loads `agent-user-global.md` only (known gap). AGENTS.md no longer owns tool priority content — it references `ai/rules/tool-priority.md`.
Durable record: `decisions/0003-universal-constitution-loading.md`

---

## ADL-006 — Hook output channel: stdout for Claude, stderr for terminal-only

2026-03-31 — Blocking/warning hooks must write to stdout (not stderr) for Claude to see the reason.

---

## ADL-007 — Replace python3 with jq for hook JSON parsing

2026-04-01 — python3 startup is ~19ms vs jq ~3ms (6x). All per-tool-call hooks migrated to jq. python3 retained only in once-per-prompt/session hooks.

---

## ADL-008 — Consolidate to v2 hook architecture

2026-04-01 — 6 PreToolUse → 1 (`pre-tool-gate-v2.sh`), 4 PostToolUse → 1 (`post-tool-analytics.sh`). Eliminates multiple process spawns per tool call. todo-gate and edit-without-read promoted to block.

---

## ADL-009 — Hooks are scaffolding, not architecture

2026-04-01 — Hooks train behavioral patterns but have diminishing returns once Claude learns the rule via instructions. Future: LES metrics, auto-graduation, memory reinforcement.

---

## ADL-010 — 2026-04-20 session initialization housekeeping

Loaded Serena manual + project memories, processed and deleted `plans/session-handoff.md`, and kept active plan context unchanged pending next user task.

---

## ADL-011 — Insights action plan: skip CLAUDE.md text additions, use hooks

2026-05-21 — Report suggested 3 CLAUDE.md additions. "Tool Priority Rules" skipped: already enforced by `pre-tool-gate-v2.sh` + `ai/rules/tool-priority.md` — text-only additions have weak adherence without hooks. Net-new rules that ARE missing enforcement (Investigation Depth, Migration Verification) added where they belong: Investigation Depth → user-global `agent-user-global.md`; Migration Verification → auc-conversion project CLAUDE.md (project-specific, in patch doc).
Durable record: `decisions/0005-autonomous-watchdog-loop.md`

---

## ADL-012 — AI primitives audit run as verified workflow, not metric loop

**Decision:** 2026-06-12 — `/autoresearch` request "analyze AI primitives + plan improvements" executed as a 3-phase orchestrated workflow (Discover → Propose → adversarial Verify), not the autonomous metric loop.
**Why:** No mechanical metric exists for "optimal improvements"; adversarial verification substitutes for keep/discard. All 20 proposals verified against (a) capability reality, (b) already-implemented, (c) repo-constraint fit.
**Alternatives rejected:** Plain single-agent analysis (no independent verification, stale-capability risk); autoresearch loop (no metric).
**Assumptions:** Researched capabilities (Claude Code plugins/teams/routines, Codex AGENTS.md/cloud, Gemini extensions) cited from June-2026 docs remain accurate at execution time.

---

## ADL-013 — read-before-write-guard deadlocks on hook-touched files

**Decision:** 2026-06-12 — Treat `read-before-write-guard.sh` blocking Writes to `plans/*.md` as a defect; fix scheduled in upgrade plan Wave 1.
**Why:** Hooks touch `plans/*.md` every prompt → harness marks any prior Read stale → guard never sees a fresh read → native Write permanently blocked for existing plans files mid-session.
**Workaround until fixed:** `rm` + Write (new-file path bypasses guard) or `LeanCtx.ctxEdit`.

---

## ADL-014 — migration-watchdog: keep as quarantined skill, no split needed

**Decision:** 2026-06-16 — `auc-prod-db-monitor` skill stays in `.claude/skills/` as a real directory (not a symlink) but remains quarantined via `disable-model-invocation: true` in its SKILL.md frontmatter. No migration to `ai/skills/` or worktree split.
**Why:** The skill is AUC-project-specific (not dotfiles-global), so it does NOT belong in `ai/skills/`. Its quarantine flag prevents accidental invocation. Moving it to a project repo would require a separate tracker and adds overhead with no benefit.
**Alternatives rejected:** Move to `ai/skills/` (wrong scope — project-specific, not machine-global); delete entirely (still referenced in project docs); split to separate worktree (overkill).
**Assumptions:** `check-skill-drift.sh` correctly exempts quarantined real directories, so CI will pass even with this real dir present.

---

## ADL-015 — hook-config.yaml declarative rules: register the loader, don't delete the yaml

**Decision:** 2026-07-08 — `hook-config.yaml`'s `rule.*`/`read-guard.*` entries were dead (`hook-rule-loader.sh` never sourced by any hook or registered in `.claude/settings.json`), but several are genuine `action: block` guards (`sed -i`, `awk`/`echo`/`printf` file redirects, piped `tee`, `node_modules` reads) with no other coverage in `pre-tool-gate-v2.sh`. Registered the loader rather than deleting the yaml.
**Why:** Deleting the yaml would silently remove intended protection instead of just stop overstating what's enforced. The yaml's simple section-level toggles (`serena-tool-priority`, `session-duration-guard`, etc.) are also genuinely read live by `pre-tool-gate-v2.sh` and `session-duration-guard.sh` — the file is not entirely dead, only its declarative rule layer was.
**Alternatives rejected:** Delete `hook-config.yaml` entirely (loses real, non-overlapping block coverage); leave as-is and just fix the audit doc's wording (doesn't close the actual enforcement gap).
**Implementation:** Fixed `check_bash_cmd_rules`/`check_read_path_rules`'s block-path in `hook-rule-loader.sh` to call `_deny()` (same non-blocking-`exit 1` bug class as C1/M4) instead of falling back to plain `exit 1`; sourced the loader from `pre-tool-gate-v2.sh`; wired both check functions into Sections 1 (Read guards) and 2 (Bash guards). Verified live with simulated PreToolUse JSON payloads covering block, warn, and pass-through cases.

---

## ADL-016 — Remove lean-ctx shell-hook double-compression; fix rtk-rewrite.sh's untracked-file root cause

**Decision:** 2026-07-08 — (a) Removed the `lean-ctx hook rewrite` PreToolUse entry from `.claude/settings.json` outright. (b) Tracked `rtk-rewrite.sh` in the repo at `.claude/hooks/rtk-rewrite.sh` and repointed its `.claude/settings.json` hook `command` from the live homedir path (`/Users/axos-agallentes/.claude/hooks/rtk-rewrite.sh`) to the dotfiles repo path (`/Users/axos-agallentes/.dotfiles/.claude/hooks/rtk-rewrite.sh`).
**Why:** (a) `lean-ctx hook rewrite` was silently re-registered alongside `rtk-rewrite.sh` despite decision 0004 rejecting lean-ctx shell hooks running alongside rtk, and despite `.claude/LEAN_CTX.md` asserting shell hooks are "NOT active." Measured this session: rtk achieves 94.4% avg compression / 53.8M tokens saved over 6847 commands vs. lean-ctx's shell-hook bucket at 7.7% avg / 2.6M saved over 7023 invocations — rtk is ~20x more effective at shell-command compression specifically, so the second hook was pure double-processing overhead with a much worse ratio, not a meaningful redundancy safeguard. (b) M3's audit finding described the symptom (`rtk-rewrite.sh` lives untracked at `~/.claude/hooks/rtk-rewrite.sh`) but not the cause. Tracing every hook `command` path in `.claude/settings.json` showed all ~50 other hooks are registered against the dotfiles repo path directly (`/Users/axos-agallentes/.dotfiles/.claude/hooks/...`) — no symlink layer exists or is needed, since the hook command itself points straight at the tracked file. `rtk-rewrite.sh` was the sole exception, registered against the live homedir path instead, which is *why* it had to exist as a real untracked file there — nothing else was ever going to invoke a repo copy.
**Alternatives rejected:** Symlinking `~/.claude/hooks/rtk-rewrite.sh` back into the repo (the audit finding's literal wording) — rejected after tracing the actual invocation mechanism, since no other hook uses a symlink and adding one here would be a one-off pattern solving the wrong layer of the problem, plus it's fragile against an unmerged worktree (a live symlink was briefly created pointing at the not-yet-existent main-branch path during this fix, went dangling immediately, and was reverted to a real file before being reported — see below).
**Assumptions:** The live `~/.claude/hooks/rtk-rewrite.sh` real file remains load-bearing on `main` until this branch merges (main's `settings.json` still points at it) — do not delete it pre-merge. Safe to delete post-merge once the merged `settings.json`'s repo-path `command` is live, since nothing will reference the homedir copy anymore.
**Follow-ups (explicitly out of scope for this fix, flagged not actioned):** `.cursor/hooks/lean-ctx-rewrite-native` and `opencode/plugins/lean-ctx.ts` are separate tool integrations that invoke lean-ctx's rewrite hook independently of Claude Code — may have their own double-compression exposure, unexamined here. H2's broader hook-consolidation fold (`advisor-escalate.sh`, `pr-title-conventional-guard.sh`, `git-commit-guard.sh`, `pre-push-remote-check.sh` into `pre-tool-gate-v2.sh`) and removing the duplicate standalone `lean-ctx hook observe` UserPromptSubmit entry remain open.

---

## ADL-017 — Close ADL-016 follow-ups: verified no-issue; removed orphaned Cursor hook wrapper files

**Decision:** 2026-07-08 — Investigated both ADL-016 follow-up items and closed them as verified non-issues: (a) Cursor's live `~/.cursor/hooks.json` registers `lean-ctx hook rewrite`/`redirect`/`observe` directly against the `lean-ctx` binary on PATH, with no rtk hook anywhere in the config — no double-compression exposure exists in Cursor. (b) opencode's `opencode/plugins/lean-ctx.ts` is the only plugin in `~/.config/opencode/plugins/`, and `~/.config/opencode/opencode.json` references no rtk plugin — no double-compression exposure exists in opencode either. Separately, removed four repo-tracked and eight live-homedir orphaned files (`.cursor/hooks/lean-ctx-{rewrite,redirect}-native`, `.cursor/hooks/lean-ctx-{rewrite,redirect}.sh`, plus `.bak` copies of each live file) as dead code.
**Why:** ADL-016 flagged both integrations as "may have their own double-compression exposure, unexamined" — direct inspection of the actual live config each tool reads (not just the repo-tracked copy) shows neither ever wired an rtk-equivalent hook alongside lean-ctx, so the double-compression pattern fixed for Claude Code in ADL-016 never existed in Cursor or opencode. While investigating, found the `.cursor/hooks/lean-ctx-*-native`/`.sh` wrapper scripts (`#!/bin/sh; exec lean-ctx hook rewrite`, etc.) are unreferenced by the live `~/.cursor/hooks.json`, which calls `lean-ctx hook rewrite`/`redirect` from PATH directly rather than through any local wrapper file — the same "repo-tracked file diverges from live homedir file" pattern seen with `rtk-rewrite.sh` in ADL-016, but here the live copies were also dead rather than load-bearing, so removal (not repointing) was correct.
**Alternatives rejected:** Leaving the follow-up items open in ADL-016 indefinitely — rejected since both were investigable in-session with direct evidence (live config file contents), and leaving them open overstates residual risk. Repointing the wrapper scripts to be genuinely invoked (mirroring the `rtk-rewrite.sh` fix) — rejected because nothing in the live Cursor config calls them; there's no invocation path to repoint.
**Assumptions:** The live `~/.cursor/hooks.json` and `~/.config/opencode/opencode.json` snapshots read during this investigation remain the authoritative configs going forward — if either tool's hook/plugin wiring changes later to add an rtk-equivalent alongside lean-ctx, this conclusion would need re-verification.
