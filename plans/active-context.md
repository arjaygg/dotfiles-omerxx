# Active Context

## Current (2026-08-02) — read-before-edit gate reworked

status: committed on `fix/read-before-edit-gate` (3a64c5a), worktree `.trees/read-before-edit-gate`.
  NOT pushed, no PR — arjaygg personal-account billing gate. NOT live: `~/.claude/hooks` symlinks
  to the main checkout, so the fix takes effect only once merged to main.
focus: `pre-tool-gate-v2.sh` §3a blocked Edit unless the path was in a uid-lifetime read log that
  only native Read ever wrote. In lean-ctx replace-mode sessions native Read has no schema, so no
  compliant action could clear it. Dropped the Edit/MultiEdit arm (harness Edit contract +
  `old_string` matching already cover it); rebuilt the Write arm session-scoped, realpath-
  canonicalized, `grep -qxF`, with best-effort ctx_read literal-path parity.
verification: `scripts/test_read_before_overwrite_gate.py` 12/12; shell-syntax, hook-output-schema,
  hook-config, hook-target, executable-bits, self-modification suites green.
in flight: nothing. Awaiting a human decision on merging (control-plane change —
  `lifecycle_adapter.py` refuses to bind a run owning `.claude/hooks`, by design).
next candidates:
  - Upstream `lean-ctx` feature request: have the MCP server append resolved ctx_read paths to the
    session read log, replacing the regex extractor in `post-tool-analytics.sh` §1.
  - Unfixed by design: a ranged `Read(limit: 1)` still exempts a whole-file Write.

## Historical (2026-08-01) — Config-sync session: 0015 + 0016 shipped

status: goal 05 closed (#395 merged 2026-07-28). No open goal; this session was dotfiles
  config-sync and hygiene work.
focus: Shipped today (all ff-merged to main, pushed):
  - **0015** — Codex Headroom provider removed from tracked configs; Codex connects direct.
    0013 §2 superseded (persistent proxy premise was dead: no Docker, no hcodex, port 8787
    unserved). Headroom 0.33 runs per-session for Claude only via `hclaude`.
  - **0016** — `.claude/settings.json` untracked (runtime-managed projection). Source of truth =
    `ai/config/claude/settings.base.json`; `setup.sh` bootstraps via `config_generate --write`.
    The perpetual settings-churn loop is structurally dead.
  - Config-sync batch (9 commits): lean-ctx client guidance, codex user-prompt hook aggregator
    (+10 tests), windsurf/opencode portable configs, gateway approvals, VS Code tool fix.
  - Housekeeping: retired sanitize-staged-settings pre-commit hook (dead after 0016); tmux-side
    dual-monitor script committed.
verification: full sweep green — setup.sh --check exit 0, all config-adjacent suites OK.
in flight: nothing. Working tree clean.
next candidates:
  - Step 19 (pre-action A2 enforcement) — still not started, not authorized. Blocker stands:
    `skipDangerousModePermissionPrompt: true` in live settings + settings.local.json may defeat
    `permissions.ask` as an A2 checkpoint. Resolve before Step 19 relies on it.
  - #349 (regenerates at session init — likely closeable) and the 19-draft 2026-07-13 cluster.
  - Wave-2 branch triage: 14 no-PR branches with unlanded work remain (13 .trees worktrees),
    incl. agent-cost-review skill, ccusage-statusline-cost, ancient karpathy-skills-support,
    phase2-portable-generation (94 dirty files). Wave-1 cleanup done 2026-08-01: 36 merged/stale
    branches + 5 remote refs + 26 worktrees removed after blob-level content verification.

## Historical (2026-07-28) — Goal 05 closeout notes

plan: plans/2026-07-27-native-agent-orchestration.md — durable design reference for all 18 steps.
Steps 1-18 shipped as PRs #361-#395. Per-step detail and evidence live in plans/progress.md.

Live consequence of Step 18 to carry forward: `auto_ship`/`auto_clean` now *resolve* to effective
A0 (no eval evidence exists for any pipeline leg, and the A2 cap applies). Nothing consults the
resolver yet, so behaviour is unchanged today — Step 19 turns that into enforcement and will stop
unattended merges.

Superseded note: the 2026-07-28 paragraph about `.claude/settings.json` vs `settings.base.json`
byte-parity (enforced via sanitize-staged-settings.sh) is obsolete — the file is untracked and
the hook retired per decisions/0016.

Carried forward from Step 15, still needs a decision:
- The plan's §20 says schemas.md requires per-finding `severity` and Step 15 removes it. Step 10
  already did, so that criterion passes vacuously. The plan text itself is stale.
- §15's "kill a run mid-flight" cannot be met for SIGKILL in-process; covered from the other side
  (frontmatter still `running` with no terminal status = crashed run). Judge if that suffices.

Open, unrelated to goal 05:
- The ~55-60k static context baseline is ~75% fixed Claude Code overhead — measured, judged not
  worth trimming. Whether #381's autocompact fix holds is unverified (needs elapsed sessions).
