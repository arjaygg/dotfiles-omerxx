****# Goal 01 — Agentic Loop Optimization Baseline

## Goal

Audit and optimize the dotfiles AI control plane so it stays safer, deterministic, portable,
maintainable, context-efficient, and cross-client consistent without silently rewriting policy.

## Verified current state

- Repository guidance still separates policy (`AGENTS.md`, `CLAUDE.md`, `docs/`, `decisions/`,
  `plans/`) from dotfiles distribution (`.claude/`, `.codex/`, `.gemini/`, `.cursor/`,
  `.windsurf/`, `setup.sh`).
- Session-init baseline is loaded:
  - `mcp__pctx__list_functions` returned Serena, Qmd, LeanCtx, Repomix, and Graphify.
  - `Serena.initialInstructions()` succeeded.
  - `Serena.checkOnboardingPerformed()` errored, so onboarding status is not freshly confirmed.
  - `Serena.readMemory({ memory_name: "START_HERE" })` failed because that memory does not exist.
- `goals/2026-07-14-01-agentic-loop-optimization.md` is the tracked active goal prompt;
  `goals/` and `plans/` provide the current handoff surface.
- Current review branch/worktree for this audit continuation is
  `chore/agentic-loop-source-validation` at `.trees/agentic-loop-source-validation`; the main
  checkout was restored clean after the symlink/source-of-truth validation edits were moved here.
- Tracked client configs are present and writable in the repo; the following are tracked and
  exist as regular files, not symlinks:
  - `.claude/settings.json`
  - `.codex/config.toml`
  - `.gemini/settings.json`
  - `.gemini/mcp.json`
  - `.cursor/mcp.json`
  - `.windsurf/mcp_config.json`
  - `setup.sh`
- Exact marker check from the live files:
  - `.claude/settings.json` does **not** contain `/Users/axos-agallentes`, `dangerously-skip-permissions`,
    `skipDangerousModePermissionPrompt`, `pctx.json`, or `settings-symlink-guard`.
  - `.codex/config.toml`, `.gemini/settings.json`, `.gemini/mcp.json`, `.cursor/mcp.json`, and
    `.windsurf/mcp_config.json` do contain `/Users/axos-agallentes` and `pctx.json`.
  - `setup.sh` does not contain `/Users/axos-agallentes`, `dangerously-skip-permissions`,
    `skipDangerousModePermissionPrompt`, `pctx.json`, or `settings-symlink-guard`.
- Architecture docs read this session confirm the intended layering:
  - `AGENTS.md` = neutral repository policy entrypoint
  - `CLAUDE.md` = thin Claude adapter importing `AGENTS.md`
  - `ai/rules/tool-priority.md` = shared tool-priority policy
  - `docs/agent-configuration-architecture.md` = layer separation and distribution model

## Checked and not yet checked

Checked:

- Repository guidance and architecture docs: `AGENTS.md`, `CLAUDE.md`,
  `docs/agent-configuration-architecture.md`, and `ai/rules/tool-priority.md`.
- Session/tool baseline: `mcp__pctx__list_functions`, `Serena.initialInstructions()`,
  `Serena.readMemory({ memory_name: "START_HERE" })`, and `LeanCtx.ctx_intent`.
- Tracked client config presence and path markers for Claude, Codex, Gemini, Cursor, Windsurf,
  and `setup.sh`.
- Parsed high-level config structure for `.claude/settings.json`, `.codex/config.toml`,
  `.gemini/settings.json`, `.gemini/mcp.json`, `.cursor/mcp.json`, and
  `.windsurf/mcp_config.json`.
- Existing Codex base-template, manifest, and generator test coverage.
- Official/current primitive docs for Agent Skills, AGENTS.md, Claude Code skills/hooks, Codex
  skills/hooks, Gemini CLI skills/hooks/extensions, Cursor skills/rules/MCP/plugins, and Windsurf
  Cascade skills/hooks/MCP/rules/workflows.
- Current Claude Code hook reference sections for matcher behavior, MCP tool matching, no-matcher
  events, decision/output shapes, `ConfigChange`, and `WorktreeCreate`.
- Live user-level skill directories and symlink targets for `~/.agents/skills`, `~/.claude/skills`,
  `~/.codex/skills`, `~/.gemini/skills`, and `~/.cursor/skills`.
- Self-modification/copy-back mechanisms: `settings-symlink-guard.sh`, `sessionstart.sh`,
  `hook-graduate.sh`, `hook-graduation-state.json`, `scripts/config_generate.py`,
  `ai/config/README.md`, and `ai/config/manifest.json`.
- Public-hygiene scanner output for current tracked files.

Not yet checked:

- Full live hook runtime behavior for every Claude hook event after the latest pctx/Codex startup fix;
  static schema/matcher risks are documented, but runtime execution proof remains incomplete.
- Rendered runtime proposals for all clients using real ignored overlays.
- Live runtime replacement behavior for `~/.codex/config.toml`, `~/.gemini/*`, `~/.cursor/*`, or
  `~/.windsurf/*`; this remains intentionally held pending approval.
- Runtime hook wire-format compatibility by executing equivalent hooks under each client.
- Whether `goals/` should become tracked project convention or stay a local coordination artifact.
- A reviewed remediation plan for automatic hook graduation and tracked runtime learning state.
- A file-group-by-file-group public-hygiene scrub/migration for the 392 current summary findings.

## Cross-client parity matrix

| Client               | Tracked entrypoint(s)                                  | Shared rules / policy loading                                                                             | MCP / tooling surface                                                                                   | Current drift / note                                                                                            |
| -------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Claude               | `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks/` | `CLAUDE.md` imports `AGENTS.md`; `.claude/settings.json` carries hooks, permissions, and `skillOverrides` | 14 hooks; 46 allows; 49 denies; default permission mode `acceptEdits`; 104 skill overrides set to `off` | Strongest enforcement layer; no tested home-path or bypass marker found in live Claude settings                 |
| Codex                | `.codex/config.toml`                                   | `model_instructions_file = "~/.dotfiles/ai/rules/agent-user-global.md"`                                   | `lean-ctx` and `pctx`; skill list points at `ai/skills/` plus a few local/system skills                 | Most machine-local references: project paths, `pctx.json`, skill paths, and config paths are absolute           |
| Gemini / Antigravity | `.gemini/settings.json`, `.gemini/mcp.json`            | Uses `pctx` gateway only; project guidance comes from repo docs, not a separate hook layer                | `pctx` only                                                                                             | Live config still embeds `/Users/axos-agallentes/.config/pctx/pctx.json`                                        |
| Cursor               | `.cursor/mcp.json`                                     | Uses `pctx` gateway only                                                                                  | `pctx` only                                                                                             | Live config still embeds `/Users/axos-agallentes/.config/pctx/pctx.json`                                        |
| Windsurf             | `.windsurf/mcp_config.json`                            | Uses `pctx` gateway plus LeanCtx env                                                                      | `lean-ctx` and `pctx`                                                                                   | Live config still embeds `/Users/axos-agallentes/.lean-ctx` and `/Users/axos-agallentes/.config/pctx/pctx.json` |

Shared across clients:
- `AGENTS.md` defines the repo policy entrypoint and stack/worktree convention.
- `ai/rules/tool-priority.md` defines shared tool routing and batching rules.
- `setup.sh` is the tracked distribution/bootstrap path for the symlinked runtime layout.

## Open PR overlap snapshot

Checked with `gh pr list --repo arjaygg/dotfiles-omerxx --state open --json ... --limit 50`
and `gh pr view <n> --json files` on 2026-07-14. No GitHub writes were made.

Open stack observed:

- Draft PRs #297-#315 are open and stacked from `main` through
  `feat/proposal-decision-ledger`.
- #297 starts at `main`; #315 is the top of the visible stack.

Overlap with this branch's current dirty files:

| Current file/group | Overlapping open PR | Risk | Recommendation |
|---|---|---|---|
| `.claude/skills/{auc-dev-a,auc-dev-b,auc-dev-c,auc-devintegration-suite,auc-manifest-review,auc-qa,auc-sm,auc-tech-writer,migration-clean,migration-watchdog,migration-watchdog-auto,sqlserver-integration-tester,watchdog-cron-setup,watchdog-remediate}` | #315 `feat(learning): record explicit proposal decisions` | Direct overlap; #315 also deletes/changes these stale skill links. | Before publishing this branch, rebase or restack above #315, or split skill-link cleanup out if #315 lands first. |
| `plans/active-context.md` | #315 | Expected active-plan overlap. | Resolve manually; keep only current handoff facts. |
| `setup.sh` | #311 `feat(setup): add read-only migration modes` | Direct overlap in installer behavior/comments. | Rebase after #311 or keep setup comment change in a tiny conflict-prone patch. |
| `scripts/test_phase0_boundary.py` | #306 `ci(policy): validate every pull request layer` | Direct overlap in script test surface. | Re-run full script tests after restack; avoid broad edits here. |
| `.github/workflows/claude-auto-gates.yml` | None in #297-#315 file lists | No direct overlap found. | Keep local CI-gate change; still verify after restack. |
| `scripts/check-skill-drift.sh`, `scripts/test_skill_drift.py` | None in #297-#315 file lists | No direct overlap found. | Good candidate for independent patch, but it semantically complements #315 stale-link cleanup. |
| `.gemini/skills/daily-standup-insights` | None in #297-#315 file lists | No direct overlap found. | Safe as part of skill-drift cleanup; verify after restack. |

Implication:

- The current branch is reviewable as an audit/validation slice, but PR timing matters: #315 already
  touches the same stale Claude skill links, while #311/#306 touch nearby setup/test surfaces.
- If the user wants lowest-conflict publishing, land or restack against the #297-#315 stack first.
- If the user wants fastest validation, keep this as a small independent branch but expect conflicts
  on `.claude/skills/*`, `plans/active-context.md`, `setup.sh`, and `scripts/test_phase0_boundary.py`.

## Claude hook schema and matcher audit snapshot

Checked against the current Claude Code hooks reference on 2026-07-14 and the tracked
`.claude/settings.json` / `.claude/hooks/*` files. No hook or permission semantics were changed.

Checked:

- Official Claude Code hooks reference for hook lifecycle, matcher behavior, MCP tool matching,
  no-matcher events, `PreToolUse` decision schema, `ConfigChange` decision schema, `WorktreeCreate`
  output rules, and path placeholder behavior.
- Tracked `.claude/settings.json` hook event/group structure.
- Hook scripts that emit decisions or mutate tool input: `pre-tool-gate-v2.sh`, `rtk-rewrite.sh`,
  `scratchpad-reread-guard.sh`, `config-integrity.sh`, `task-gate.sh`, and related dispatcher wrappers.

Findings:

| Finding | Evidence | Risk | Recommended next action |
|---|---|---|---|
| Matcher fields are configured on events where Claude Code ignores matchers. | Docs say `UserPromptSubmit`, `Stop`, `TaskCreated`, `TaskCompleted`, `WorktreeCreate`, and `WorktreeRemove` do not support matchers; settings use `matcher: ".*"` for each. | Low functional risk for `".*"` because they already fire always, but misleading and weakens future review. | Remove ignored matcher fields in a Phase 1 hook-cleanup slice and add static validation. |
| `pre-tool-gate-v2.sh` contains MCP-specific batching logic for `mcp__serena__*` and `mcp__pctx__*`, but the configured `PreToolUse` matcher is `Bash|Read|Edit|Write|MultiEdit|Grep|Glob|Agent`. | Settings omit `mcp__.*`; docs state MCP tool names are regular tool names such as `mcp__server__tool` and require a matcher like `mcp__.*`. | MCP-specific gate branches are unreachable through this matcher. | Add an explicit MCP PreToolUse matcher or move/remove unreachable logic with tests. |
| `rtk-rewrite.sh` is the only active PreToolUse script found that emits `updatedInput`. | Static search found `updatedInput` only in `rtk-rewrite.sh`; it preserves the original `tool_input` and changes only `.command`. | Lower mutation-race risk, but it is separate from `pre-tool-gate-v2.sh`; ordering matters for Bash rewrites vs Bash denials. | Keep one deterministic rewrite owner per tool invocation and add a rewrite fixture proving transformed input is used. |
| `task-gate.sh` Stop blocking output lacks `hookEventName` in `hookSpecificOutput`. | Script emits `{"hookSpecificOutput":{"permissionDecision":"deny",...}}` for `Stop`; current docs describe Stop/TeammateIdle-style blocking via exit code 2 or top-level `{"continue": false, "stopReason": "..."}` rather than PreToolUse-style `permissionDecision`. | Potentially non-blocking or deprecated Stop behavior if `task-gate` is set to block. | Validate with a Stop fixture/live simulation before relying on it; prefer documented Stop schema. |
| `ConfigChange` matcher `.*_settings` intentionally matches user/project/local/policy settings but not `skills`. | Docs enumerate `user_settings`, `project_settings`, `local_settings`, `policy_settings`, and `skills`. | Skill-file changes may bypass `config-integrity.sh`; possibly intentional because skill drift has separate checks. | Decide whether `skills` should be covered by config-integrity or by skill-drift validation only. |
| WorktreeCreate has two handlers. | Settings list both `worktree-create.sh` and `claude-tmux-bridge.sh worktree-enter`; docs say WorktreeCreate command hooks must print the created worktree path as the last non-empty stdout line and replace default git behavior. | Multiple handlers can contaminate stdout or make path ownership ambiguous unless only one prints stdout. | Add a fixture or live dry-run proving stdout path contract is preserved. |

Immediate boundary:

- These are Phase 1 hook-architecture findings, not approved hook changes.
- Do not alter machine-wide hooks, permission semantics, or live runtime config without explicit review.

## Self-modification and public-exposure audit snapshot

Checked current tracked files on 2026-07-14. No runtime files were changed.

### Self-modification mechanisms

| Mechanism | Evidence | Current behavior | Risk | Recommended action |
|---|---|---|---|---|
| `settings-symlink-guard.sh` | Lines 4-7 explicitly say it reports a severed `~/.claude/settings.json` symlink without adopting runtime content. | Proposal-only drift detection; no source update or relink. | Low; aligns with the goal's no-copy-back requirement. | Keep proposal-only; add a test if not already covered by the Phase 0 branch. |
| `scripts/config_generate.py` | Header and README say proposals are printed to stdout; code has no runtime write path, and `compare_proposal` reports changed paths + hashes only. | JSON-only proposal generator; reads base/overlay, validates with public hygiene scanner, and never writes runtime files. | Partial: TOML clients are in manifest, but current generator only loads JSON. | Implement approved Codex/TOML Steps 1-4 before claiming deterministic Codex proposal support. |
| `ai/config/manifest.json` | Lists Claude, Codex, Gemini, Cursor, Windsurf, and PCTX base/runtime/overlay paths. | Describes desired source/base/overlay/runtime separation. | Partial: manifest includes Codex TOML and several clients, but generator support/runtime wiring are incomplete. | Keep manifest as proposal map; do not apply live runtime until reviewed. |
| `sessionstart.sh` → `hook-graduate.sh` | `sessionstart.sh` backgrounds `hook-graduate.sh`; `hook-graduate.sh` edits `hook-config.yaml` and `hook-graduation-state.json` unless `--dry-run`. | Automatic hook-policy graduation/demotion can run once per day at session start. | High: this contradicts the goal's rule that self-improvement may propose patches but must not silently change enforcement/policy. | Stop before changing hook behavior; propose a Phase 3 change to make graduation report-only by default and require explicit promotion. |
| `hook-graduation-state.json` | Tracked state file says it is updated by `hook-graduate.sh`; contains current hook levels and graduation targets. | Runtime learning state is tracked as source. | Medium/high: generated learning state can drift into Git and mutate policy. | Move runtime state to ignored local storage or convert to reviewed proposal artifacts. |

### Public exposure boundary

`python3 scripts/public_hygiene_check.py --json` currently exits 1 with 396 tracked findings:

| Rule | Count |
|---|---:|
| `private-org-name` | 200 |
| `absolute-home-path` | 145 |
| `private-org-url` | 51 |

Representative exposed files include `.claude-global/CLAUDE.md`, `.claude/agents/*`, historical
plans, and agent/skill docs with organization-specific examples. No `secret-assignment` or
`private-key` finding appeared in this run, but the public-repository hygiene acceptance criterion is
not met because organization names, internal URLs, and local absolute paths remain tracked.

Implication:

- Phase 0 is still incomplete as a public-repo hygiene migration.
- The existing scanner gives deterministic evidence, but this branch should not broadly scrub 396
  findings because it would overlap many open PRs and policy docs.
- Next safe slice: choose one high-value boundary file group (for example `.claude-global/CLAUDE.md`
  or tracked client configs) and replace private details with templates/overlays under review.

### Policy proposal — make hook graduation proposal-only

```yaml
id: hook-graduation-proposal-only
problem: >
  The current self-improvement loop can silently mutate tracked hook policy/state during
  SessionStart, which violates the goal requirement that learning systems may propose changes but
  must not edit canonical policy or enforcement without review.
evidence:
  - ".claude/hooks/sessionstart.sh lines 49-56 background hook-graduate.sh once per day"
  - ".claude/hooks/hook-graduate.sh lines 75-78 edit hook-config.yaml and hook-graduation-state.json unless --dry-run"
  - ".claude/hooks/hook-graduation-state.json is tracked and declares it is updated by hook-graduate.sh"
recurrence: "structural; every SessionStart can evaluate the daily marker"
current_behavior: >
  SessionStart can run hook-graduate.sh without --dry-run, causing local metrics to change tracked
  hook-config.yaml and hook-graduation-state.json.
proposed_destination: "hook + CI + docs"
proposed_change: >
  Change SessionStart to run hook-graduate.sh in report-only mode by default; make any promotion emit
  a proposal artifact under an ignored/local or tracked review directory, and require explicit human
  approval before hook-config.yaml or hook-graduation-state.json changes. Add tests proving default
  SessionStart cannot mutate tracked files.
expected_effect: >
  Preserves learning signals while preventing silent policy/enforcement changes.
risks: >
  Useful hook level changes no longer apply automatically; reviewers must process proposal output.
conflicts: >
  ADL-009 describes future hook auto-graduation; this proposal narrows it to governed proposal-only
  graduation rather than deleting the learning loop.
context_cost: "No new always-loaded instruction content required; behavior moves to deterministic tests/docs."
evaluation: >
  Baseline evidence proves mutation path exists. Candidate evaluation should compare dry-run/proposal
  output against the current direct-mutation path and verify tracked files remain unchanged.
review_after: "After the Phase 3 governed self-improvement slice lands, or before enabling any auto-promotion."
```

Approval wording for this separate Phase 3 slice:

> Approve hook-graduation proposal-only remediation. Do not change other hook permission semantics,
> live runtime config, or public-hygiene content in the same slice.

That approval would authorize only:

- tests proving the current default can mutate tracked hook policy/state;
- changing `sessionstart.sh` / `hook-graduate.sh` so default execution is dry-run/proposal-only;
- documentation of where proposal artifacts go and how humans approve promotion;
- validation that `hook-config.yaml` and `hook-graduation-state.json` remain unchanged by default.

That approval would not authorize:

- changing any specific hook level from block/warn/off;
- modifying PreToolUse denial semantics;
- applying live runtime config;
- broad public-hygiene scrubbing;
- committing/pushing/PR creation without a separate request.

## File-level harness map

| Layer                        | Files                                                                                                                                            | Purpose                                                                                              |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| Neutral repo policy          | `AGENTS.md`, `docs/agent-configuration-architecture.md`                                                                                          | Defines the repository as a configuration distribution system and documents the layer boundaries     |
| Claude adapter / enforcement | `CLAUDE.md`, `.claude/settings.json`, `.claude/hooks/`                                                                                           | Thin Claude adapter plus the strongest local enforcement layer (hooks, permissions, skill overrides) |
| Shared tool policy           | `ai/rules/tool-priority.md`                                                                                                                      | Central tool-selection, batching, and Serena/LeanCtx/Qmd routing rules                               |
| Codex runtime config         | `.codex/config.toml`                                                                                                                             | Codex-specific model instructions, skill paths, marketplace config, and MCP gateway wiring           |
| Gemini runtime config        | `.gemini/settings.json`, `.gemini/mcp.json`                                                                                                      | Gemini runtime settings and pctx gateway wiring                                                      |
| Cursor runtime config        | `.cursor/mcp.json`                                                                                                                               | Cursor MCP gateway wiring                                                                            |
| Windsurf runtime config      | `.windsurf/mcp_config.json`                                                                                                                      | Windsurf MCP wiring plus LeanCtx environment setup                                                   |
| Bootstrap / install          | `setup.sh`                                                                                                                                       | Creates the symlinked runtime layout and installs the tracked distribution                           |
| Active session state         | `plans/active-context.md`, `plans/progress.md`, `plans/decisions.md`, `plans/pctx-functions.md`, `plans/2026-07-14-agentic-loop-optimization.md` | Human-visible handoff trail for the current goal                                                     |
| Goal prompt                  | `goals/2026-07-14-01-agentic-loop-optimization.md`                                                                                               | Tracked active goal source                                                                           |

## Command and skill reachability snapshot

Checked sources:

- `ai/commands/`
- `.claude/commands/`
- `.cursor/commands/`
- `ai/skills/`
- `.claude/skills/`
- live standard skill paths: `~/.agents/skills`, `~/.codex/skills`, `~/.gemini/skills`,
  `~/.cursor/skills`
- `.codex/config.toml` skill/marketplace sections

Findings:

| Surface | Evidence | Status |
|---|---|---|
| Shared commands | `ai/commands/` has 9 files. | Canonical source exists. |
| Claude commands | `.claude/commands/` has 11 entries; 9 are symlinks to `ai/commands/`; `context-eval.md` and `migration-clean.md` are real client-specific files. | Mostly shared, with two Claude-local commands to classify. |
| Cursor commands | `.cursor/commands/` has `smart-commit.md` symlinked to `ai/commands/smart-commit.md` plus a `bmad/` directory. | Partial shared reachability. |
| Shared skills | `ai/skills/` has 62 skill directories. | Canonical source exists. |
| Claude skills | `.claude/skills/` has 67 symlinks, but 14 are broken: `auc-dev-a`, `auc-dev-b`, `auc-dev-c`, `auc-devintegration-suite`, `auc-manifest-review`, `auc-qa`, `auc-sm`, `auc-tech-writer`, `migration-clean`, `migration-watchdog`, `migration-watchdog-auto`, `sqlserver-integration-tester`, `watchdog-cron-setup`, `watchdog-remediate`. | Drift found; needs cleanup or documented quarantine. |
| Standard cross-client skills | `~/.agents/skills` is a symlink to `/Users/axos-agallentes/.dotfiles/ai/skills`. | Shared skill standard path works on this machine. |
| Legacy per-client skill dirs | `~/.codex/skills`, `~/.gemini/skills`, and `~/.cursor/skills` exist but are not symlinks. | Needs deeper reachability audit before cleanup. |
| Codex skills / marketplaces | `.codex/config.toml` has a `skills.config` section and one `openai-bundled` marketplace. | Still part of the Codex local-overlay problem. |

Implication:

- The next audit-only task, if implementation remains unapproved, is to classify the 14 broken Claude
  skill symlinks as stale, moved-to-project, local-only, or intentionally quarantined.
- If implementation is approved, this reachability drift should remain out of the Codex TOML overlay
  slice unless it directly affects Codex generation.

### Broken Claude skill symlink classification

All 14 broken entries are symlinks under `.claude/skills/` pointing to missing
`../../ai/skills/<name>` targets. None has a live target under `ai/skills/`.

| Broken symlink | Evidence found | Classification | Proposed next action |
|---|---|---|---|
| `auc-dev-a` | `ai/config/claude/settings.base.json` disables it; historical AUC plan says `auc-dev-a/b/c` are project-specific agent definitions. | Stale AUC/project-specific role symlink. | Remove symlink after confirming AUC project owns any replacement. |
| `auc-dev-b` | Disabled in Claude base settings; only historical plan/current report references found. | Stale AUC/project-specific role symlink. | Remove symlink after confirming no global skill exists. |
| `auc-dev-c` | Disabled in Claude base settings; only historical plan/current report references found. | Stale AUC/project-specific role symlink. | Remove symlink after confirming no global skill exists. |
| `auc-devintegration-suite` | Disabled in Claude base settings; target missing. | Stale disabled AUC role symlink. | Remove or document as project-local outside dotfiles. |
| `auc-manifest-review` | No repo references found outside the current reachability report. | Orphaned stale symlink. | Remove symlink in a cleanup slice. |
| `auc-qa` | Disabled in Claude base settings; historical AUC plan references it as a project role. | Stale AUC/project-specific role symlink. | Remove symlink after confirming AUC project owns any replacement. |
| `auc-sm` | Disabled in Claude base settings; target missing. | Stale disabled AUC role symlink. | Remove or document as project-local outside dotfiles. |
| `auc-tech-writer` | Disabled in Claude base settings; target missing. | Stale disabled AUC role symlink. | Remove or document as project-local outside dotfiles. |
| `migration-clean` | `AGENTS.md` names migration-clean as an agent-specific command example; 2026-06-12 plan says `migration-clean` was missing `SKILL.md`. | Command-vs-skill drift; stale skill symlink. | Keep command path separate; remove broken skill symlink unless a real global skill is restored. |
| `migration-watchdog` | `decisions/0007-migration-watchdog-single-skill.md` says it should be canonical under `ai/skills`, but current target is missing. Later progress says migration watchdog work moved to `auc-conversion`. | Contradictory historical state; likely moved-to-project but not conclusively resolved. | Do not delete blindly; reconcile against AUC project before cleanup. |
| `migration-watchdog-auto` | Historical autonomous-loop docs and upgrade plan reference it; current target missing. | Stale/moved-to-project cron skill reference. | Reconcile with `migration-watchdog` before deleting. |
| `sqlserver-integration-tester` | No repo references found outside the current reachability report. | Orphaned stale symlink. | Remove symlink in a cleanup slice. |
| `watchdog-cron-setup` | `ai/skills/routines-setup/SKILL.md` and `decisions/0008-cloud-routines-scope.md` still point to `/watchdog-cron-setup`; target missing. | Broken live documentation reference, not just stale symlink. | Either restore a global skill or update references to the current local-watch convention. |
| `watchdog-remediate` | `decisions/0007-migration-watchdog-single-skill.md` calls it the active-remediation skill; Claude base settings disables it; target missing. | Broken referenced remediation skill; needs decision before cleanup. | Decide restore-vs-retire before removing symlink/reference. |

Cleanup boundary:

- Removing orphaned symlinks is out of scope for the Codex TOML overlay remediation.
- Any cleanup should be a separate branch because it affects Claude skill routing and historical AUC
  migration/watchdog conventions.

## Grouped bottlenecks

### Client drift

- Codex, Gemini, Cursor, and Windsurf still embed machine-local absolute paths in tracked config.
- Claude has broken skill symlinks in `.claude/skills/`, so command/skill reachability is not fully
  consistent even where shared source exists.
- Claude has stronger hook/permission enforcement than the other clients, so parity depends on shared
  guidance plus generated runtime config rather than equivalent per-client hooks.

### Context bloat and leaks

- Tracked runtime configs still mix portable defaults with local project allowlists, skill paths,
  marketplace/cache paths, and MCP runtime paths.
- `goals/` currently exists outside tracked convention, which can become a competing handoff surface
  if it is not either formalized or kept explicitly local.

### Handoff friction

- `START_HERE` memory is absent, so fresh sessions cannot rely on a single project bootstrap memory.
- The active work spans `goals/`, `plans/`, and `decisions/`; the report now links them, but the
  convention still needs finalization before implementation work scales across agents.

### Tool inefficiency

- The generator currently needs stronger TOML overlay support before Codex can fully use the same
  deterministic base-plus-overlay proposal path as JSON clients.
- Proposal comparison evidence is not yet broad enough to prove idempotent Codex generation with
  ignored local overlays.

## Recommendations

1. Move machine-local path anchors out of tracked client configs into ignored overlays or generator
   inputs, starting with Codex because it has the densest absolute-path surface.
2. Keep Claude’s permission/hook surface as the primary enforcement layer, but continue verifying that
   the config stays free of bypass flags and machine-local runtime anchors.
3. Preserve `AGENTS.md`/`CLAUDE.md`/`ai/rules/tool-priority.md` as the shared source of truth, and keep
   client entrypoints thin so only the runtime-specific wiring remains in `.claude/`, `.codex/`,
   `.gemini/`, `.cursor/`, and `.windsurf/`.
4. Treat `goals/2026-07-14-01-agentic-loop-optimization.md` as a tracked coordination artifact, not
   an alternate policy source.

## Source-of-truth and symlink validation

Recommendation: keep one neutral canonical source under `ai/`, not Claude Code as the canonical source.
Use symlinks only where the target client natively discovers filesystem primitives or documented
aliases. Use generated/adapted client config for hooks, MCP, permissions, and command surfaces whose
schemas differ by client.

Validated facts:

- `Agent Skills` are the strongest cross-agent primitive: the open standard defines `SKILL.md` plus
  optional `scripts/`, `references/`, and `assets/`; OpenAI/Codex, Claude Code, Gemini CLI, Cursor,
  and Windsurf/Cascade all document skills as first-class or compatible primitives.
- The interoperable skill path is real and useful: Codex, Gemini CLI, and Cursor document
  `.agents/skills` / `~/.agents/skills`; this machine has `~/.agents/skills` symlinked to
  `/Users/axos-agallentes/.dotfiles/ai/skills`.
- Claude Code currently needs per-skill symlinks in `~/.claude/skills` because `setup.sh` documents
  that Claude Code does not follow a directory symlink for user-scoped skills across projects.
- Hooks are conceptually compatible but not wire-compatible: Claude uses events such as
  `PreToolUse`/`PostToolUse`; Codex uses similar names but TOML/JSON hook config and trust review;
  Gemini uses `BeforeTool`/`AfterTool` and millisecond timeouts; Windsurf uses Cascade event names
  such as `pre_read_code`/`post_write_code`; Cursor packages hooks through plugins.
- Commands/workflows are not uniformly portable: Claude command markdown can now map to skills;
  Cursor can migrate slash commands to skills or package commands in plugins; Gemini extensions
  package custom commands; Windsurf workflows live under `.windsurf/workflows/`.
- MCP is standard at the protocol layer, but config is client-specific: Cursor uses `mcp.json`;
  Codex uses TOML config layers; Gemini and Windsurf use their own JSON settings/config files.

Local validation findings:

- `ai/README.md` already calls `ai/` the authoritative source for common primitives.
- `docs/agent-configuration-architecture.md` already names `~/.agents/skills` as the cross-tool
  standard skills path and keeps tool-specific entrypoints as adapters.
- `setup.sh` already implements the right broad pattern: canonical `ai/skills`, `~/.agents/skills`
  symlink, Claude per-skill symlinks, Codex legacy per-skill links, Cursor subset links, and
  client-specific config generation/bootstrap.
- User-level drift remains: `~/.codex/skills` has 16 broken symlinks, `~/.gemini/skills` has 2
  broken symlinks, and `~/.claude/skills` has 1 broken user-level symlink. Repo `.claude/skills`
  drift is cleaned in this branch. Symlinks are not the problem; stale generated links are.
- Added targeted regression coverage for `scripts/check-skill-drift.sh` so dangling skill symlinks
  fail validation instead of being skipped by the previous directory-only glob.
- Removed 14 dangling repo `.claude/skills` symlinks after the repo-level test reproduced the
  expected failure: `auc-dev-a`, `auc-dev-b`, `auc-dev-c`, `auc-devintegration-suite`,
  `auc-manifest-review`, `auc-qa`, `auc-sm`, `auc-tech-writer`, `migration-clean`,
  `migration-watchdog`, `migration-watchdog-auto`, `sqlserver-integration-tester`,
  `watchdog-cron-setup`, and `watchdog-remediate`.
- `scripts/check-skill-drift.sh .claude/skills` now returns 0 in this worktree.
- Added `claude-auto-script-tests` to `.github/workflows/claude-auto-gates.yml` so every PR runs
  `python3 -m unittest discover -s scripts -p 'test_*.py'`; before this, the existing coverage gate
  could skip this repo because it has no Python package marker file.
- Added `claude-auto-config-audit-summary` to the same workflow so PR logs expose read-only/redacted
  config inventory, public-hygiene, config-doctor, and hook-config summaries. Known baseline findings
  are intentionally non-blocking via `|| true` until remediated in scoped PRs.
- `scripts/hook_config_check.py --summary` now emits only counts by rule/event, so the PR audit job no
  longer needs hook issue messages to show hook baseline drift.
- `scripts/instruction_budget_check.py` now enforces byte budgets for the always-loaded instruction
  files that most directly affect context cost: `CLAUDE.md`, `AGENTS.md`,
  `ai/rules/agent-user-global.md`, and `ai/rules/tool-priority.md`.
- `scripts/check-skill-drift.sh` now accepts multiple skill directories in one invocation, enabling
  read-only user-level drift audits without mutating live runtime directories.
- Read-only live check of `~/.codex/skills`, `~/.gemini/skills`, and `~/.claude/skills` still reports
  19 dangling symlinks and 4 non-quarantined real directories; live cleanup remains intentionally
  unapplied.
- The validator now also rejects symlinks whose target exists but is not a skill directory
  (`SKILL.md`/`skill.md` missing). This caught a tracked stale `.gemini/skills/daily-standup-insights`
  symlink and live aggregate/client-loop symlinks that were previously invisible to the drift check.

### Live user-level skill drift classification

No live files were changed. The following classifications are from a read-only run of
`scripts/check-skill-drift.sh ~/.codex/skills ~/.gemini/skills ~/.claude/skills ~/.cursor/skills`
after strengthening symlink-target validation.

| Finding group | Evidence | Classification | Proposed next action |
|---|---|---|---|
| Codex stale generated links: `auc-dev-a`, `auc-dev-b`, `auc-dev-c`, `auc-devintegration-suite`, `auc-manifest-review`, `auc-qa`, `auc-sm`, `auc-tech-writer`, `migration-clean`, `migration-watchdog`, `migration-watchdog-auto`, `sqlserver-integration-tester`, `watchdog-cron-setup`, `watchdog-remediate` | Same missing `ai/skills/<name>` targets as the repo `.claude/skills` cleanup slice. | Legacy generated drift; symlink mechanism is fine, targets are stale. | Remove or restore through an explicit live cleanup step only after approval. |
| `~/.codex/skills/auc-prod-db-monitor` | Points at missing `.dotfiles/.claude/skills/auc-prod-db-monitor`; `plans/decisions.md` ADL-014 says this should stay as a quarantined real Claude skill, not a shared `ai/skills` symlink. | Contradicts prior quarantine decision. | Do not recreate under `ai/skills`; reconcile the quarantined Claude-local skill separately. |
| `~/.codex/skills/goal-authoring` and `~/.claude/skills/goal-authoring` | Point at missing `ai/skills/goal-authoring`; no current repo references found outside drift evidence. | Orphaned stale symlink. | Remove in approved live cleanup unless a new canonical skill is intentionally added. |
| `~/.gemini/skills/watchdog-cron-setup` and `~/.gemini/skills/watchdog-remediate` | Point at missing `ai/skills` targets; historical decisions still reference these names. | Stale generated links plus unresolved historical docs. | Decide restore-vs-retire for watchdog skills before live cleanup. |
| `~/.codex/skills/daily-standup-insights-workspace` and `~/.gemini/skills/daily-standup-insights-workspace` | Targets exist under `ai/skills/` but have no `SKILL.md`/`skill.md`. | Invalid skill target, previously missed by validator. | Either add a real skill file or stop linking this directory as a skill. |
| `~/.gemini/skills/ai` and `~/.gemini/skills/skills` | Symlink targets exist but are aggregate/client-loop directories, not individual skills. | Invalid aggregate symlinks inside a skill-discovery dir. | Prefer `~/.agents/skills -> ~/.dotfiles/ai/skills`; remove aggregate Gemini links only with live approval. |
| `~/.codex/skills/codex-primary-runtime` | Real directory with no `SKILL.md`; contains Codex runtime subdirs. | Tool/runtime cache, not a skill. | Exclude or move out of skill-discovery path; do not blindly delete. |
| `~/.codex/skills/lean-ctx` | Real directory with `SKILL.md`; hash matches canonical `ai/skills/lean-ctx/SKILL.md`. | Real copy of canonical skill. | Replace with symlink during approved cleanup. |
| `~/.gemini/skills/daily-standup-insights` | Real directory with `SKILL.md`; contains work/org-specific defaults in its workflow text. | Machine/work-context local skill, not public canonical source. | Keep local or migrate through a sanitized canonical skill; do not commit current content. |
| `~/.claude/skills/graphify` | Real directory with `SKILL.md`; no canonical `ai/skills/graphify` exists, while repo policy references Graphify tooling. | Claude-local/tool-specific skill candidate. | Promote to sanitized `ai/skills/graphify` or keep explicitly Claude-local; decide separately. |

Conclusion:

- Correct pattern: canonical `ai/{skills,commands,rules,output-styles}` plus client adapters.
- Incorrect pattern: make `.claude/` the primary source and point other agents at Claude-specific
  directories.
- Near-term cleanup should remove stale/broken skill symlinks and invalid aggregate skill-dir entries,
  then make `setup.sh` prune or report stale generated links instead of accumulating them.


## Approval-ready implementation checklist

This section records the exact bounded proposal-generator scope that was approved and completed
through the final Gate 2 skip decision. No live runtime write was performed.

### Step 1 — Add TOML overlay rendering

**Files:** `scripts/config_generate.py`, `scripts/test_config_generate.py`

**Accepts:** JSON behavior remains unchanged; TOML base + TOML overlay can render a proposal without
reading process environment variables, mutating inputs, or printing local overlay contents.

- [x] Teach the generator to parse and emit TOML when the base template is TOML.
- [x] Add TOML overlay merge coverage.
- [x] Keep explicit `--set NAME=VALUE` placeholder expansion as the only variable source.

### Step 2 — Make Codex proposal generation complete

**Files:** `ai/config/codex/config.base.toml`, `ai/config/manifest.json`,
`scripts/test_portable_config_templates.py`, `scripts/test_config_manifest.py`

**Accepts:** the tracked Codex base remains portable; the manifest references the Codex base/runtime
and ignored overlay; tests prove the Codex proposal can be generated from portable source plus
explicit local values.

- [x] Verify the current Codex base contains only shared portable defaults.
- [x] Add or adjust tests so Codex generation is covered as TOML, not treated like JSON.
- [x] Keep local project allowlists, local skill paths, marketplace cache paths, and local binary
  paths out of tracked base config.
- [x] Correct the obsolete top-level `[status_line]` table to the official `[tui]` `status_line`
  setting, confirmed by the official config reference and `codex features list`.

### Step 3 — Define the local-only Codex overlay convention

**Files:** `.gitignore`, `ai/config/README.md`, optionally an example overlay under
`ai/config/codex/`

**Accepts:** local Codex-only paths have a documented ignored overlay location, and any tracked
example uses placeholders or fake portable paths only.

- [x] Document `~/.config/dotfiles-ai/codex.overlay.toml`.
- [x] Ensure the overlay path is ignored.
- [x] Provide a non-sensitive example if useful.
- [x] Complete Gate 1 by creating the minimal ignored overlay with mode `0600`; no prior overlay
  existed.

### Step 4 — Add deterministic proposal comparison evidence

**Files:** `scripts/config_generate.py`, `scripts/test_config_generate.py`

**Accepts:** comparison reports changed paths and hashes without exposing raw local values; repeated
generation with unchanged inputs is idempotent.

- [x] Extend comparison support to TOML proposal outputs.
- [x] Add an idempotency assertion for repeated Codex proposal generation.
- [x] Keep printable output strict about local paths; allow compare-only local context solely for
  redacted evidence, while rejecting secrets and private keys in every mode.

### Step 5 — Stop before live runtime apply

**Files:** none unless separately approved.

**Accepts:** no write to `~/.codex/config.toml` or other live runtime config occurs automatically.
The user receives proposal evidence and explicitly approves any runtime update.

- [x] Run the verification gates.
- [x] Summarize proposal deltas without printing sensitive overlay values.
- [x] Ask for separate live-runtime approval.

## Final proposal-slice and Gate 1 verification (2026-07-15)

- The bounded proposal-generator slice is complete on `feature/codex-config-proposals`.
- The portable Codex base was corrected from the obsolete top-level `[status_line]` table to the
  official `[tui]` `status_line` setting. The official config reference and `codex features list`
  confirm the current schema and live parse.
- TOML round-trip handling supports real Codex shapes, including arrays of tables and quoted dotted
  keys.
- Direct proposal output remains portable and strict.
- Compare-only mode can process machine-local path and work context to compute evidence while
  redacting sensitive mapping keys and emitting only redacted paths and hashes. Secrets and private
  keys remain rejected.
- The deterministic printable Codex proposal is valid TOML, repeated output is identical, and its
  SHA-256 is `bf13bdf914a7b28504e262183fd1a65182d560243e524efb44c94dbbdf7db280`.
- Gate 1 created the minimal ignored `~/.config/dotfiles-ai/codex.overlay.toml` with mode `0600`;
  no prior overlay existed.
- The final base-plus-overlay comparison against live `~/.codex/config.toml` reported zero changed
  paths. Both hashes were valid, but the proposal and target byte hashes differed because the
  proposal uses deterministic canonical rendering.
- The live `~/.codex/config.toml` SHA-256 remained unchanged across Gate 1, and the live config was
  not written.
- The plan-defined focused command covering `test_config_manifest`,
  `test_portable_config_templates`, and `test_config_generate` passed 49 of 49 tests.
- Full `scripts/` discovery ran 85 tests with exactly one failure, caused only by the absent ignored
  `.claude/settings.local.json`. The full suite is not green.
- The read-only public hygiene summary reported 390 findings: 142 absolute-home-path,
  197 private-org-name, and 51 private-org-url.
- The read-only config doctor summary reported 65 issues: 6 errors and 59 warnings, comprising
  29 absolute-home-path, 6 blanket-permission-allow, and 30 private-org-name issues.
- The pre-Gate-1 synthetic full-local-shape simulation used the existing tracked
  `.codex/config.toml` as both its local-shape overlay source and target. It reported exactly five
  changed paths, exposed no local values, and produced two structurally valid 64-character hashes.
  This remains historical synthetic evidence and is superseded by the actual Gate 1 zero-path
  comparison.
- Independent final review found no remaining correctness- or security-significant code issue in the
  bounded scope.
- Gate 1, Gate 2 preflight, and the final Gate 2 decision are complete. The final decision was to
  skip the semantically no-op canonical rewrite; no live runtime write occurred.

## Gate 2 preflight verification (2026-07-15)

- Private backup directory
  `~/.config/dotfiles-ai/backups/20260715T002308Z-pre-codex-gate2` has mode `0700`.
- The exact live backup, generated candidate, manifest, and rollback instructions each have mode
  `0600`.
- The backup hash equals the current live hash. The candidate byte hash differs, while the semantic
  changed-path count is zero.
- The candidate TOML parsed successfully, an isolated `CODEX_HOME` Codex parse passed, and the
  candidate remained unchanged.
- A sandbox rollback dry-run restored the candidate to the exact original-live hash.
- Live bytes, hash, and metadata remained unchanged; no runtime apply occurred.
- Because the semantic delta is zero and only deterministic canonical formatting differs, the final
  Gate 2 decision is to skip the no-op live rewrite and close the bounded Codex slice.
- The private backup and generated candidate are retained in the private backup directory; no live
  runtime write occurred.

## Approval decision block

Use this exact approval language if the Codex-first implementation slice should proceed:

> Approve Codex remediation Steps 1-4 from `plans/2026-07-14-agentic-loop-optimization.md`.
> Do not apply live runtime config in Step 5 without a separate approval.

That approval authorizes only:

- generator/test changes needed for TOML base + overlay proposal support;
- portable Codex base/manifest/test adjustments;
- documentation and ignore-rule changes for `~/.config/dotfiles-ai/codex.overlay.toml`;
- deterministic proposal comparison/idempotency evidence.

That approval does **not** authorize:

- writing `~/.codex/config.toml`;
- changing Claude hooks, permissions, or hard-denies;
- changing Gemini, Cursor, Windsurf, or pctx live runtime files;
- committing, pushing, opening a PR, or merging without a separate request.

If approval is withheld, keep the work audit-only: refine handoff evidence, classify remaining live
drift, or split/rebase this branch against the open PR stack before publishing.

## Execution and PR boundaries

Use separate review slices. Do not combine runtime, hook, public-hygiene, and Codex-generator changes
in one PR.

| Slice | Purpose | Files likely in scope | Approval needed | PR ordering / overlap |
|---|---|---|---|---|
| Current audit/validation slice | Document verified architecture, symlink validation, skill drift tests, open-PR overlap, hook/self-improvement/public-hygiene risks. | `plans/*`, `decisions/0011-agentic-loop-optimization.md`, `scripts/check-skill-drift.sh`, `scripts/test_skill_drift.py`, `.github/workflows/claude-auto-gates.yml`, stale tracked skill symlinks. | No live-runtime approval; commit/PR still requires separate user request. | Rebase/restack before publishing; overlaps #315 (`.claude/skills/*`, `plans/active-context.md`), #311 (`setup.sh`), #306 (`scripts/test_phase0_boundary.py`). |
| Codex portable proposal generation | Implement Steps 1-4 above; no live runtime apply. | `scripts/config_generate.py`, config generator tests, `ai/config/codex/*`, `ai/config/manifest.json`, `.gitignore`, `ai/config/README.md`. | Exact Codex approval block above. | Should land after or be reconciled with existing config PRs #298-#305. |
| Live skill-dir cleanup | Remove/replace stale links under `~/.codex/skills`, `~/.gemini/skills`, `~/.claude/skills`; preserve local/tool-managed dirs. | Live user dirs only, plus maybe `setup.sh` pruning/reporting tests. | Explicit live-runtime cleanup approval. | Do after tracked skill validation lands; avoid deleting `codex-primary-runtime`, work-local `daily-standup-insights`, or Claude-local `graphify` without classification decision. |
| Hook graduation proposal-only | Convert auto-graduation from direct mutation to proposal-only. | `.claude/hooks/sessionstart.sh`, `.claude/hooks/hook-graduate.sh`, hook tests/docs. | Explicit hook-behavior approval block in the policy proposal section. | Coordinate with hook fixture/config PRs #297, #307-#310. |
| Public-hygiene migration | Remove private org URLs/names and home paths from tracked source via templates/overlays. | One file group per PR, starting with highest-risk guidance/config files. | Approval per scrub slice because content may change policy/examples. | Avoid broad scrub while #297-#315 stack is open; re-run hygiene scanner per slice. |
| Hook schema/matcher validation | Add static/fixture checks for ignored matchers, MCP matcher reachability, Stop schema, and WorktreeCreate stdout contract. | Hook validation scripts/tests and `.claude/settings.json` only if fixing. | Tests-only may be separate; behavior fixes need hook approval. | Coordinate with #297/#309. |

## Files in scope

- `decisions/0011-agentic-loop-optimization.md`
- `.github/workflows/claude-auto-gates.yml`
- `.claude/skills/*` stale tracked symlinks listed in the command/skill reachability snapshot
- `.gemini/skills/daily-standup-insights`
- `scripts/check-skill-drift.sh`
- `scripts/test_skill_drift.py`
- `scripts/test_phase0_boundary.py`
- `setup.sh`
- `plans/active-context.md`
- `plans/progress.md`
- `plans/decisions.md`
- `plans/2026-07-14-agentic-loop-optimization.md`

Read-only evidence sources also inspected, but not modified in this branch:

- `AGENTS.md`
- `CLAUDE.md`
- `docs/agent-configuration-architecture.md`
- `ai/rules/tool-priority.md`
- `goals/2026-07-14-01-agentic-loop-optimization.md`
- `.claude/settings.json`, `.codex/config.toml`, `.gemini/settings.json`, `.gemini/mcp.json`,
  `.cursor/mcp.json`, `.windsurf/mcp_config.json`
- live `~/.codex/skills`, `~/.gemini/skills`, `~/.claude/skills`, `~/.cursor/skills`

## Changes made

- Refreshed `plans/active-context.md` with the resumed goal and session-init baseline.
- Added a new active section to `plans/progress.md` for the agentic-loop optimization work.
- Added a current decision note to `plans/decisions.md` to keep the session audit trail current.
- Refreshed `plans/pctx-functions.md` for the current day and session-init evidence.
- Implemented the proposal generator and deterministic TOML serializer, including real Codex
  structures and placeholder expansion in mapping keys.
- Added compare-only privacy handling that permits local path/work context for computation while
  emitting only redacted paths and hashes.
- Hardened structured secret, private-key, and path scanning without relaxing strict printable
  proposal validation.
- Added the portable example overlay and usage documentation.
- Expanded generator, portable-template, and public-hygiene test coverage.
- Corrected the portable Codex base to the official `[tui]` `status_line` schema.
- Created the minimal ignored machine-local Codex overlay with mode `0600` and completed the
  content-safe zero-path comparison.
- Completed private Gate 2 backup, candidate validation, and sandbox rollback preflight without
  writing live runtime state.
- Recorded the final Gate 2 skip decision, retained the private backup and candidate, and closed the
  bounded Codex slice without a live runtime write.
- Reconciled the goal, plan, active context, progress, active decision log, and ADR handoff state.
- Used `.codex/config.toml` and live `~/.codex/config.toml` only as read-only comparison inputs;
  neither file was modified.
- Refreshed durable ADR `decisions/0011-agentic-loop-optimization.md` so it now records the neutral
  `ai/` source-of-truth decision, client-adapter boundary, skill-link drift validation slice,
  hook-graduation proposal-only slice, and public-hygiene migration slice.
- Added `## Execution and PR boundaries` to separate the current audit/validation slice from Codex
  generation, live skill-dir cleanup, hook graduation, public-hygiene migration, and hook
  schema/matcher validation.

## Implementation files changed

- `scripts/config_generate.py`
- `scripts/test_config_generate.py`
- `scripts/public_hygiene_check.py`
- `scripts/test_public_hygiene_check.py`
- `scripts/test_portable_config_templates.py`
- `ai/config/README.md`
- `ai/config/codex/codex.overlay.example.toml`
- `goals/00-index.md`
- `goals/2026-07-14-01-agentic-loop-optimization.md`
- `plans/2026-07-14-agentic-loop-optimization.md`
- `plans/active-context.md`
- `plans/progress.md`
- `plans/decisions.md`
- `decisions/0011-agentic-loop-optimization.md`

The tracked `.codex/config.toml` and live `~/.codex/config.toml` were read-only comparison inputs and
were not modified.

## Tests executed

- `mcp__pctx__list_functions`
- `Serena.initialInstructions()`
- `Serena.checkOnboardingPerformed()` → error
- `Serena.readMemory({ memory_name: "START_HERE" })` → error
- `LeanCtx.ctxOverview({ path: "/Users/axos-agallentes/.dotfiles", task: "audit goal for dotfiles agentic loop optimization" })`
- `LeanCtx.ctxCall({ name: "ctx_intent", arguments: { query: "audit goal for dotfiles agentic loop optimization" } })`
- `LeanCtx.ctxShell(...)` marker checks for tracked config files and `setup.sh`
- `git ls-files --error-unmatch` checks for tracked-file status
- Plan-defined focused command:
  `python3 -m unittest scripts.test_config_manifest scripts.test_portable_config_templates scripts.test_config_generate`
  → 49 of 49 passed.
- Full `scripts/` unittest discovery → 85 run, exactly one failure caused only by the absent ignored
  `.claude/settings.local.json`; not green.
- Read-only `public_hygiene_check.py` → 390 findings: 142 absolute-home-path,
  197 private-org-name, and 51 private-org-url.
- Read-only `config_doctor.py` → 65 issues: 6 errors and 59 warnings; rule split recorded above.
- Official Codex config reference plus `codex features list` → `[tui]` `status_line` confirmed as the
  current schema and parsed successfully by the live CLI.
- Deterministic printable Codex proposal parse/repeat/hash verification → valid TOML, identical
  output, SHA-256 `bf13bdf914a7b28504e262183fd1a65182d560243e524efb44c94dbbdf7db280`.
- Pre-Gate-1 synthetic full-local-shape simulation → five changed paths, no exposed local values,
  and two structurally valid 64-character hashes; historical synthetic evidence superseded by the
  actual Gate 1 comparison.
- Actual Gate 1 base-plus-overlay versus live comparison → zero changed paths and two valid hashes;
  differing proposal/target byte hashes are expected from deterministic canonical rendering.
- Live `~/.codex/config.toml` pre/post SHA-256 verification → unchanged; no live write occurred.
- Independent final review → no remaining correctness- or security-significant code issue in the
  bounded scope.
- Gate 2 backup preflight → private directory mode `0700`; exact live backup, generated candidate,
  manifest, and rollback instructions each mode `0600`; backup hash matched current live.
- Candidate validation → TOML parse and isolated `CODEX_HOME` Codex parse passed; candidate bytes
  remained unchanged; semantic comparison reported zero changed paths despite a different byte
  hash.
- Sandbox rollback dry-run → restored the candidate to the exact original-live hash.
- Final live-state verification → live bytes, hash, and metadata unchanged; no runtime apply.

## Results

- The session-init surface is available and documented.
- The active goal prompt is tracked.
- The tracked cross-client configs are not yet portable in the broad sense: Codex, Gemini, Cursor,
  and Windsurf still embed the local home path and/or runtime routing details.
- `setup.sh` is clean of the tested home-path and bypass markers.
- The bounded Codex proposal-generator slice, Gate 1, Gate 2 preflight, and final Gate 2 skip
  decision are complete and verified; live runtime remains untouched.

## Residual risks

- The runtime configs under `.codex/`, `.gemini/`, `.cursor/`, and `.windsurf/` still carry
  machine-specific absolute paths.
- The canonical-byte rewrite was deliberately not adopted because it would change formatting only,
  not semantics; live bytes and hash remain unchanged.
- `START_HERE` memory is absent, so future sessions cannot rely on it for project bootstrap.

## Next recommended step

Human diff review is the only next step for this bounded slice. Commit or create a PR only on a
separate explicit request. Gemini, Cursor, and Windsurf migrations are future scopes and are not part
of this completed Codex slice.
