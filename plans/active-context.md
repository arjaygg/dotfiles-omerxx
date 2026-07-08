# Active Context

plan: plans/2026-07-08-constitution-hooks-audit.md
focus: Phase 1 of constitution-hooks-audit complete (C1, post-tool-analytics flag-matcher, H3, M4) — Phase 0 explicitly skipped by user 2026-07-08; Phases 2-4 still unexecuted, awaiting decision on next step

## Current (2026-07-08) — Phase 1 executed and verified

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
