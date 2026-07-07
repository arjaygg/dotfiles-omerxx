# Active Context

plan: plans/2026-07-07-ai-harness-improvement-proposal.md
focus: harness improvement proposal drafted from /insights + reconciled against paused 2026-06-12 plan — awaiting user review, no execution yet

## Current (2026-07-07)

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
