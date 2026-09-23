# Claude Code Opus 5.5 user-scope rollout

**Status:** Core model-and-agent rollout implemented and live-validated on 2026-09-24. The optional daily-driver skill was removed after an overlap audit; comparable real-task benchmarking, a Fable 5.1 live probe, and an intentionally unsafe negative-mutation test remain deferred.
**Date:** 2026-09-24
**Scope:** Personal native Claude Code configuration on this Mac
**Objective:** Adopt Anthropic's Opus 5.5 daily-driver guidance without reactivating the disabled multi-client agent harness or changing unrelated user settings.

## Authority and constraints

- The operating guidance is Anthropic's [What a task costs on Opus 5.5](https://claude.com/blog/what-a-task-costs-on-opus-5-5).
- Claude Code model configuration, subagent permissions, and usage behavior must be checked against the current official [model configuration](https://code.claude.com/docs/en/model-config), [subagent](https://code.claude.com/docs/en/sub-agents), and [usage](https://code.claude.com/docs/en/costs#using-the-usage-command) documentation at implementation time.
- This is a narrow Claude-only rollout. Do not run setup.sh, use scripts/ai-harness-toggle.sh to enable anything, or restore assets from .harness-disabled/repo. Read-only harness status checks are allowed.
- Do not convert the live settings file into a symlink. Do not alter permissions.defaultMode or skipDangerousModePermissionPrompt without separate approval.
- Do not touch the existing unrelated working-tree changes: hammerspoon/init.lua, .cursor/, and plans/2026-09-23-shunt-integration-analysis.md.

## Verified baseline

| Area | Evidence | Consequence |
|---|---|---|
| Shared harness | setup.sh exits when .harness-disabled exists; archived sources are intentionally parked under .harness-disabled/repo. | Restoring the old templates is out of scope and could reactivate multiple clients. |
| Live settings | ~/.claude/settings.json is a regular mode-600 JSON file; it currently has model opus[1m], top-level effortLevel medium, permissions.defaultMode auto, and skipDangerousModePermissionPrompt true. | Treat it as mutable, user-owned runtime state. Make only narrowly merged changes. |
| Opus review | A read-only Claude Code review requested model alias opus at high effort and resolved to canonical claude-opus-5-5. | Opus 5.5 is available through the direct native CLI. |
| Effort semantics | Current Anthropic documentation says Opus 5.5 ignores the legacy top-level effortLevel setting. | Any persistent medium default for Opus 5.5 must use modelSettings.claude-opus-5-5.effortLevel after live verification. |
| Subagent boundary | Parent defaultMode is auto; subagent permissionMode is not an effective read-only control in this mode. | Search and log agents need an explicit Read, Grep, Glob tool allowlist. Native validation plus a read-only smoke check are required; an intentionally unsafe write probe is optional and was not run. |
| Native launch | zshrc aliases point to the archived, missing .claude/scripts/claude-launch.sh. The installed native binary works directly. | Use the direct native binary during rollout. A shell-alias repair is a separate, explicitly scoped decision. |

## Review receipt

- **Codex review:** GPT-6 Astra, high effort, read-only. It identified the disabled-harness boundary, legacy Opus effort setting, live-file overwrite risk, launch-wrapper drift, and the need for tool-level subagent restrictions.
- **Claude review:** Claude Code canonical claude-opus-5-5, high effort, safe mode, plan-only permissions, and no tools or subagents. It required a full-fidelity private backup, an explicit unchanged-security invariant, a benchmark before changing the default, and a practical rollback rule.

## 2026-09-24 implementation receipt

### Applied

- Preserved `model: "opus[1m]"`; it is the intended Opus 5.5 one-million-context selection, so no default-model replacement was needed.
- Added only `modelSettings.claude-opus-5-5.effortLevel: "medium"` to the live regular mode-600 settings file. `permissions.defaultMode: "auto"` and `skipDangerousModePermissionPrompt: true` are semantically unchanged.
- Created a private mode-600 pre-change backup at `~/.claude/backups/settings.json.before-opus55-rollout-20260924T060000+0800`. Its SHA-256 is `35fe4a818c1b012df5cd0830383f63eda099d61af63c9180d757452406c58a1c`; the expected post-change file SHA-256 is `bca05c2ef10929aca1d6c9e1f36bb8fc8d06d89123a3052904fc1f0c467ba6f0`.
- Removed the optional user-invoked daily-driver skill after a live-reference audit showed that it duplicated the always-loaded workflow guidance in `~/.claude/CLAUDE.md`. No live configuration consumed it beyond Claude's skill discovery.
- Added `~/.claude/agents/search-scout.md` (Haiku, low) and `~/.claude/agents/log-reader.md` (Sonnet, medium). Each has the explicit `Read, Grep, Glob` allowlist and no memory field, shell, edit, network, or MCP tools.
- Left the old harness disabled. No archived asset was restored, and no launcher, permission, hook, status-line, or non-Claude-client setting was changed.

### Live validation

- A fresh normal native session with no `--model` resolved the default to `claude-opus-5-5[1m]`, canonical model `claude-opus-5-5`, with a 1,000,000-token context window.
- `/effort status` in that configuration returned `medium` with zero model-token usage.
- The temporary `/opus55-daily-driver` skill was discoverable in a fresh normal session before removal; it is intentionally no longer available as a slash command.
- `search-scout` successfully performed a read-only file lookup on `claude-haiku-4-5`; `log-reader` successfully performed one on `claude-sonnet-5`.
- The native `claude plugin validate ~/.claude/agents` check passed, all YAML front matter parsed, JSON parsed, trailing-whitespace scan was clean, and the settings semantic diff contains only the intended per-model entry.

### Deferred by design

- No Fable 5.1 request was made: that would consume a separate model entitlement or usage allocation without a real blocked task.
- No comparable real-task benchmark or `/usage` comparison was run: it belongs to the first selected real task with stable acceptance criteria, not a synthetic smoke test.
- No deliberately unsafe write was requested from either read-only agent. The effective boundary evidence is the native-validated explicit tools allowlist plus successful read-only execution; this receipt does not claim a live denied-write test.
- The legacy shell alias, auto-permission posture, skip-dangerous prompt setting, status line, hooks, and disabled shared harness remain separate decisions.

## Decisions to carry into implementation

1. Preserve the disabled harness. This rollout owns no archived harness asset and creates no global projection.
2. Keep the live settings file regular and mode 600. Use a narrowly scoped merge that preserves all unknown keys and detects concurrent runtime edits.
3. Retain `model: opus[1m]`: a fresh native session resolved it to canonical `claude-opus-5-5` with its intended one-million-token context window. Plain `opus` is not an automatic replacement.
4. Configure Opus 5.5 medium effort through modelSettings. `/effort status` confirmed the effective medium setting. Use high deliberately at a natural break; do not claim that a prompt or hook can switch it automatically.
5. Make plan mode a per-task workflow choice for multi-file work, never a global permission default.
6. Keep the existing global `CLAUDE.md` as the sole workflow source. Do not maintain a second daily-driver skill unless it provides non-duplicative behavior and its escalation threshold is reconciled with the global rule.
7. Use named Haiku and Sonnet workers only for bounded search and log analysis. They receive Read, Grep, and Glob only; no Bash, editing tools, mutating MCP tools, or network tools.

## Implementation phases

### Phase 0 — protect the baseline and choose the launch path

**Status: completed.** The private backup, protected-value receipt, direct native launch path, and disabled-harness check are recorded above.

1. Record the file mode, SHA-256 digest, and a full-fidelity private mode-600 backup for every live file that might change.
2. Create a separate redacted review record; it is not a rollback artifact.
3. Record the current JSON values of permissions.defaultMode and skipDangerousModePermissionPrompt as protected invariants.
4. Use the direct installed native Claude binary in a scratch directory. Do not rely on the broken shell aliases.
5. Stop if the live settings file changes after the baseline digest is captured; re-baseline and obtain a new diff before writing.

**Exit criteria:** a restorable backup exists; protected values are recorded; the exact files in scope are named; no archived harness asset has been restored.

### Phase 1 — live capability discovery

**Status: completed for the applied scope.** The default one-million-context Opus resolution, effective effort command, user discovery paths, skill discovery, and agent schema were validated. Fable availability remains deliberately unprobed.

In a fresh scratch session using the direct native binary, record:

1. The canonical resolution and available context option for opus and opus[1m].
2. Availability and canonical names for Fable 5.1, Sonnet, and Haiku.
3. The effective Opus 5.5 effort, supported effort controls, plan-mode entry point, and usage command.
4. Organization policy and any project, environment, or managed-setting override that changes the user setting.
5. The actual user-scope discovery paths and supported schemas for skills and subagents in Claude Code 2.1.281.

**Exit criteria for a scoped write:** every model alias and configuration field that will be changed is verified live. Verify Fable 5.1 immediately before its first real use rather than making a synthetic request solely for this rollout. An unsupported in-scope alias, organization cap, or unexpected project override stops the related write and requires a revised plan.

### Phase 2 — benchmark before selecting a new model default

**Status: deferred.** The existing `opus[1m]` value already resolves to the intended Opus 5.5 variant, so no default change is pending. Run this only against a selected comparable real task.

Use a fixed repository revision and fixed prompt/acceptance criteria. Start each comparison in a fresh session and treat results as directional, not statistically conclusive.

| Scenario | Main model and effort | Required evidence |
|---|---|---|
| Well-scoped implementation | Opus 5.5, medium | Verification command result, elapsed time, iterations, and usage |
| Stalled diagnostic | Opus 5.5, high at a natural break; Fable 5.1 only after the same verification signal fails twice | Failure signal, checkpoint, model transition, resolution, and usage |
| Search or log triage | Planned Haiku or Sonnet worker with a captured read-only input | Returned evidence, configured tool allowlist, child usage, and main-session quality check; capture a denied-write test only if adversarial proof is needed |

Record actual model and effort, input/output/cache-read/cache-write tokens when available, context remaining, verification result, elapsed time, and child-agent usage. Separate cold and warm-cache observations. Subscription dollar estimates are guidance, not billing records.

**Default-selection rule:** retain the current model value if it resolves to the intended Opus 5.5 variant and the benchmark is satisfactory. Otherwise, change only to a verified alias with a recorded rationale and rollback trigger.

### Phase 3 — narrowly update the live settings file

**Status: completed.** Only the documented per-model Opus effort key was added; the semantic invariant, JSON, SHA-256, and file mode were checked.

1. Apply the smallest possible merge to ~/.claude/settings.json; do not use setup.sh or a symlink.
2. If Phase 1 supports it, set modelSettings.claude-opus-5-5.effortLevel to medium.
3. Change the model value only if Phase 2 makes the decision explicit, including whether the one-million-context variant is retained.
4. Preserve every unrelated key, file mode, and file type. Confirm the protected permission values are semantically unchanged.
5. Parse JSON immediately after the write. Compare the planned key-level diff and the before/after digest. If an unexpected change appears, restore only when the live file still matches the expected post-write digest; otherwise stop for manual reconciliation.

**Exit criteria:** JSON is valid; only approved keys changed; the user file remains a regular mode-600 file; the direct native CLI reads the intended effective setting.

### Phase 4 — remove the duplicate daily-driver skill

**Status: completed.** Removed `~/.claude/skills/opus55-daily-driver/SKILL.md` after confirming that no live setting, global instruction, agent, or other active personal skill referenced it. The always-loaded `~/.claude/CLAUDE.md` remains the single workflow source for execution contracts, checkpointing, evidence, compaction, delegation, and escalation discipline.

**Evidence and impact:** the prior temporary skill was discoverable and user-invoked only, so its removal changes no setting, hook, permission, model selection, or agent definition. `/opus55-daily-driver` is no longer invocable; `opus[1m]`, its effective medium effort, and the bounded research workers remain intact.

**Exit criteria:** no duplicate daily-driver skill remains; existing global guidance remains unchanged; no live configuration consumer requires the removed skill.

### Phase 5 — add tool-restricted research subagents

**Status: completed for configured boundary and read-only smoke coverage.** Both personal agents parse, are natively validated, resolve to their intended models, and completed a read-only lookup. A deliberately unsafe mutation request was not made.

1. Add a Haiku search-scout and a Sonnet log-reader using the user-scope custom-agent schema verified in Phase 1.
2. Restrict both agents to Read, Grep, and Glob. Provide captured logs as files; do not grant Bash for collection.
3. Keep model and effort explicit in each agent definition. Keep editing work in the main Opus session as workflow policy.
4. If an adversarial runtime proof is needed later, use a disposable fixture to verify discovery, resolved model, allowed read operations, and denial of an attempted file mutation. Do not make a synthetic write request merely to complete this rollout.

**Exit criteria for this rollout:** both agents can return bounded evidence through the explicit native-validated `Read, Grep, Glob` allowlist and do not expose a configured mutating MCP or shell tool. A fixture-denied-write result is additional evidence, not currently claimed.

### Phase 6 — validate normal behavior and rollback

**Status: completed for the applied scope.** Fresh normal native-session checks passed; rollback remains the private backup plus post-write SHA guard. Do not overwrite a live file if its SHA no longer matches the expected post-change digest.

1. After each write, run a direct JSON validator and a targeted configuration check that fails on error.
2. Validate a fresh normal native session; safe mode is diagnostic only because it disables the customizations being tested.
3. Confirm the effective model, effort, plan-mode workflow, usage command, skill discovery, and agent restrictions in a scratch directory. Validate a real repository with local Claude configuration before claiming project-configuration noninterference; status-line behavior is outside this rollout.
4. Do not use setup.sh --check as acceptance evidence: the disabled-harness guard prevents its checks and many historical checks suppress failures.
5. Exercise rollback in a disposable copy first. On the live file, restore only if no intervening runtime change is detected.

**Current completion boundary:** the disabled harness remains disabled; the explicit on-demand daily-driver skill was removed after a live-reference audit; the configured `opus[1m]` default, effective medium effort, and read-only research workers remain intact; only approved live settings changed; and rollback evidence exists. Comparable-task measurement and a Fable transition remain future real-work evidence, not completed rollout evidence.

## Stop conditions and approvals

- Stop immediately for an unsupported model alias, managed-policy conflict, malformed settings file, unexpected permission change, runtime-file drift, or a subagent that can mutate the fixture.
- Do not change auto permissions, skipDangerousModePermissionPrompt, the legacy multi-provider launcher, any non-Claude client, or the shared harness without a separate user decision.
- The user authorized the scoped implementation after review. That authorization does not extend to a Fable probe, fallback/default-model change, security-posture change, alias repair, or shared-harness activation.
