# Project-Scoped Agent Harness Migration Plan

**Date:** 2026-08-03
**Status:** Draft for human approval; planning only
**Source:** `/Users/axos-agallentes/.dotfiles`
**Destination:** `/Users/axos-agallentes/git/agent-harness`
**Outcome:** The reusable agent harness is owned and executed by the destination repository. Project scope is the default; user scope is turned off only after migration and parity validation complete, and remains a supported, explicit, reversible mode backed by the same destination source.

## Recommendation

Make `agent-harness` the sole source of truth for reusable agent behavior. Keep `.dotfiles` responsible only for personal workstation/bootstrap configuration and repository-specific guidance. Do not leave always-on cross-repository links as the default. A later explicit user-scope enable may generate manifest-owned projections from `agent-harness`, but it must not restore duplicate canonical sources to `.dotfiles`.

Use a manifest-driven, reversible cutover:

1. Inventory every currently delivered asset and classify it as `move`, `keep-personal`, `split`, `retire`, or `runtime-state`.
2. Extract the reusable source, tests, client adapters, and validation authority into `agent-harness` without changing behavior.
3. Prove project-local activation, client isolation, clean-room installation, and rollback while the existing user scope remains active.
4. Add receipt-backed `enable-user-scope` and `disable-user-scope` commands that operate from the destination source and preserve unrelated user configuration.
5. Cut over canonical ownership, then disable live user scope only after all migration acceptance criteria pass.
6. Prove one enable → disable cycle so temporary reactivation remains supported without becoming the default.

This sequence makes disablement reversible, avoids two active sources of truth, and preserves a future plugin path without prematurely publishing a plugin.

## Assumptions and Decision Gates

- The destination may already contain `docs/The_Agent_Factory.md`; migration must preserve all pre-existing destination content and history.
- “All agent harness” means reusable rules, skills, commands, agents, hooks, orchestration, policy, validation, evals, and client adapters. Shell/editor/tmux configuration, secrets, credentials, caches, logs, local overlays, and client-owned runtime state remain outside the package.
- Existing historical plans and decisions stay in `.dotfiles`; the destination receives new architecture/migration records rather than copied session history.
- Project-local configuration is the default. A client that cannot load a capability at project scope must be declared unsupported or assist-only; it must not silently fall back to a global install.
- The later plugin is out of scope. This migration creates stable manifests and adapter boundaries that a plugin can package without reorganizing the core again.
- No live user-scope change occurs until the destination passes parity, project-isolation, installation, and rollback tests.
- Removing migrated source from `.dotfiles` does not remove user-scope capability; explicit reactivation is generated from the destination manifest.
- Human approval is required before Step 8 changes canonical ownership and before Step 9 turns off the live user scope.

## Scope

### Move or split into the destination

| Current source | Destination responsibility |
|---|---|
| `ai/rules/`, `ai/skills/`, `ai/commands/`, `ai/agents/`, `ai/output-styles/`, `ai/prompts/`, `ai/references/` | Reusable instruction and capability catalog |
| `ai/context/`, reusable portions of `ai/config/`, `ai/hooks/` | Context routing, project adapter templates, hook components |
| `.claude/hooks/`, `.claude/workflows/orchestrate.js`, `.claude/scripts/` | Claude adapter, enforcement, orchestration, and supporting scripts; runtime logs/state excluded |
| Reusable `.claude/agents/`, `.claude/commands/`, `.claude/output-styles/`, `.claude/skills/` projections | Generated adapter projections, not duplicate canonical sources |
| `.codex/`, `.cursor/`, `.gemini/`, `.windsurf/` harness-facing config | Project-local client adapters and conformance fixtures |
| `scripts/ai/`, harness validators/generators/checkers under `scripts/`, their `scripts/test_*.py` files, and hook fixtures | Trusted controller, policy checks, installation checks, and regression tests |
| `evals/`, `.claude-atomic.yaml`, `lensed-review.yaml`, and other harness policy/schema inputs proven by the inventory | Evaluation, autonomy, review, and policy assets |

### Keep in `.dotfiles`

- `setup.sh` as the workstation bootstrap, after removing harness installation and regeneration behavior.
- `.claude-global/CLAUDE.md` and `ai/config/codex/AGENTS.global.base.md` as personal global templates after reusable harness policy is removed; their project-local equivalents live in the destination adapters.
- Personal shell/editor/tmux/application configuration and unrelated scripts.
- Credentials, machine overlays under `~/.config/dotfiles-ai/`, and client-owned mutable files.
- Repository-specific `AGENTS.md`, `docs/`, `decisions/`, and historical `plans/`.
- A short migration notice naming the destination and its user-scope enable/disable procedure; no executable compatibility shim remains enabled by default.

### Never package

- `.claude/hooks/.logs/`, `.claude/hooks/.state/`, `pipeline-log.jsonl`, caches, `__pycache__/`, webhook logs, plugin caches/marketplaces, live settings overlays, tokens, credentials, session transcripts, or user-specific absolute paths.

## Target Architecture

```text
agent-harness/
├── AGENTS.md                         # project-local coordinator entrypoint
├── README.md                         # adoption, disable, restore, and support contract
├── harness.manifest.json             # versioned assets, ownership, clients, lifecycle
├── core/
│   ├── rules/                        # client-neutral policy/instructions
│   ├── skills/                       # canonical skills + registry
│   ├── commands/                     # canonical shared commands
│   ├── agents/                       # canonical worker/reviewer definitions
│   ├── prompts/                      # reusable prompt assets
│   ├── references/                   # reusable references
│   └── schemas/                      # intent, evidence, review, event schemas
├── adapters/
│   ├── claude/                       # project settings, hooks, workflows, projections
│   ├── codex/                        # project config, hooks, loaders, projections
│   ├── cursor/                       # project rules/config
│   ├── gemini/                       # project config/loaders
│   ├── windsurf/                     # project config/loaders
│   └── user-scope/                   # optional explicit global projections; off by default
├── controller/                       # client-neutral lifecycle/policy code
├── scripts/                          # install, uninstall, doctor, generate, validate
├── tests/                            # unit, fixture, clean-room, conformance tests
├── evals/                            # cases, runner inputs, retained report schema
├── policy/                           # autonomy/review/trust configuration
├── docs/                             # architecture, migration, plugin contract
└── .claude-plugin/                   # reserved; absent until plugin work is approved
```

The canonical source lives under `core/`, `controller/`, and `policy/`. Client directories are generated or thin adapters. `harness.manifest.json` is the packaging contract: every installed path declares its source, destination, allowed scope (`project` or explicit `user`), lifecycle (`copy`, `generate`, or client-native discovery), and uninstall ownership. Project scope is always the default; user scope requires a direct operator command.

## Reversible User-Scope Mode Contract

There is no current global kill switch: `.claude/hooks/hook-config.yaml` controls only sections of one Claude pre-tool hook and does not disable the other Claude, Codex, Cursor, or Gemini bindings. The destination must add a supported user-scope mode rather than relying on destructive unlinking:

1. `enable-user-scope` and `disable-user-scope` operate only from a released `agent-harness` revision and require `--dry-run` before `--apply`.
2. Capture a receipt at `~/.local/state/agent-harness/user-scope-receipt.json` containing each managed live path, type, prior link target or content digest, harness revision, timestamp, and inverse action.
3. Refuse to alter a path not owned by the harness manifest or whose current state differs from the receipt.
4. Disable only manifest-owned projections: shared rules, skills, commands, agents, output styles, harness hook registrations, and harness-generated client config entries.
5. Preserve client binaries, mutable settings, credentials, MCP configuration not owned by the harness, caches, histories, plugins, and personal preferences.
6. Store the selected state at `~/.config/agent-harness/scope.json`; `.dotfiles/setup.sh` and integrity checks must respect `user_scope: disabled` and must not reinstall the harness.
7. Use explicit per-client modes (`disabled`, `project`, or `user`); missing project configuration never implies user-scope fallback.
8. Re-enabling user scope generates projections from the destination manifest and release revision. It never revives the deleted `.dotfiles` canonical copies.
9. Disable, enable, and repeated same-state operations are idempotent. Conflicts stop without overwriting post-cutover user changes.

The receipt and selected-scope file are runtime state and are never committed.

## Step 1 — Freeze the Asset and Ownership Inventory

**Files:** `harness-migration-manifest.json` (temporary tracked migration map), `setup.sh`, `ai/config/manifest.json`, `ai/skills/manifest.csv`, `.claude/settings.json`, `ai/config/claude/settings.base.json`, `.codex/config.toml`, `.codex/hooks.json`, `.mcp.json`, `.cursor/`, `.gemini/`, `.windsurf/`, `.claude/hooks/`, `scripts/config_inventory.py`, `scripts/config_generate.py`, `scripts/guidance_adapter_check.py`, and destination pre-existing files.

**Work:** Record every candidate path with category, canonical source, live projections, ownership, disposition, project-scope support, generated/runtime status, secret risk, and destination. Detect duplicate canonical/projection copies and current symlink targets. Verify the destination is a Git repository, record its branch/status/remotes without changing them, and preserve existing content. Convert any ambiguous item to an explicit human decision before moving it.

**Accepts:** Every source and live projection has exactly one disposition; no runtime state or secret is marked `move`; every moved asset has one destination owner; all pre-existing destination files are listed as preserved; manifest validation fails on an unknown, duplicated, or unowned path.

## Step 2 — Scaffold the Destination Package Contract

**Files:** `agent-harness/AGENTS.md`, `README.md`, `harness.manifest.json`, `core/`, `adapters/`, `controller/`, `scripts/`, `tests/`, `evals/`, `policy/`, `docs/architecture.md`, `docs/migration-from-dotfiles.md`, and `docs/plugin-contract.md`.

**Work:** Create the target layout without overwriting existing documentation. Define manifest schema versioning, supported clients, project-default scope, explicitly enabled user scope, installation lifecycle, root discovery, feature selection, and uninstall ownership. Resolve roots from the checked-out package/project rather than `/Users/axos-agallentes`, `$HOME/.dotfiles`, or implicit global client directories. Document plugin compatibility as an adapter over the manifest; do not create `.claude-plugin/` or publish a package.

**Accepts:** The manifest validates; all paths are repository-relative or explicitly runtime-relative; a scan rejects source-code absolute home/dotfiles paths; existing destination content is unchanged unless intentionally incorporated; plugin packaging can consume the manifest without moving canonical assets.

## Step 3 — Extract Canonical Core, Policy, and Controller

**Files:** Sources classified `move` or `split` from `ai/`, `.claude/workflows/`, `.claude/hooks/`, `scripts/ai/`, harness validators under `scripts/`, `evals/`, `.claude-atomic.yaml`, and `lensed-review.yaml`; destination `core/`, `controller/`, `policy/`, `scripts/`, and `evals/`.

**Work:** Transfer the inventory-defined reusable content while preserving meaningful Git attribution where practical. Split personal/AUC/repository-specific defaults into opt-in example profiles or leave them in `.dotfiles`; do not put private organization assumptions in the default package. Consolidate duplicate canonical/projection files so generators own projections. Preserve the safety invariants in the existing lifecycle, autonomy, review, and eval code before refactoring structure.

**Accepts:** Every manifest `move` item exists once canonically in the destination; every `split` item has tests proving the reusable/default boundary; no excluded runtime/private artifact is present; controller behavior and safety fixtures match the source baseline; source remains untouched pending parity.

## Step 4 — Build Project-Local Client Adapters

**Files:** `adapters/claude/`, `adapters/codex/`, `adapters/cursor/`, `adapters/gemini/`, `adapters/windsurf/`, `scripts/generate.py`, `scripts/doctor.py`, `tests/test_adapter_generation.py`, `tests/test_project_scope.py`, and `tests/fixtures/projects/`.

**Work:** Generate thin project-local loaders/projections from the canonical manifest. For each client, declare supported coordinator/executor/reviewer capabilities and the exact project discovery path. Hooks use a repository-root variable or adapter launcher, never a developer-specific absolute path. Unsupported project-scope features fail with a clear diagnostic and remain inactive rather than installing globally.

**Accepts:** A disposable project fixture activates only while its working directory is inside that project; a sibling/neutral fixture sees no harness; all generated outputs are deterministic; adapters contain no duplicated business policy; unsupported capabilities fail closed; existing MCP topology tests are adapted and green.

## Step 5 — Move Validation, Evals, and CI Authority

**Files:** Destination `tests/`, `evals/`, CI workflows, `scripts/validate.py`, `scripts/doctor.py`, plus migrated `scripts/test_*.py`, hook fixtures, config/guidance/topology checks, workflow tests, and eval runner assets from `.dotfiles`.

**Work:** Make the destination run the authoritative test suite. Add clean-room tests with empty HOME, project activation/isolation tests, manifest completeness, install/uninstall ownership, relative-path portability, hook schema/config/target checks, skill registry/reference checks, lifecycle tests, and deterministic eval smoke tests. Replace source-root assumptions with fixture roots. Run these while the real user scope remains unchanged; disposable HOME fixtures provide isolation.

**Accepts:** Destination CI is green from a clean clone with no `.dotfiles` dependency; empty-HOME and neutral-project tests pass; every manifest asset is covered by install/uninstall ownership tests; hook/config/guidance/topology suites pass; eval smoke tests produce schema-valid evidence; failure output names the owning adapter or manifest entry.

## Step 6 — Implement Reversible User-Scope Control Without Applying It

**Files:** Destination `adapters/user-scope/`, `scripts/scope.py`, `tests/test_user_scope.py`, `tests/fixtures/home/`; `.dotfiles/setup.sh`, `.claude/hooks/config-integrity.sh`, `harness-migration-manifest.json`, and user-scope config templates referenced by the manifest.

**Work:** Implement `scope.py status`, `enable-user-scope`, and `disable-user-scope` with mandatory `--dry-run` before `--apply`. Generate the receipt and selected-scope state defined above. Make `.dotfiles/setup.sh` defer to the state file and stop owning harness projections after cutover. Test enabled, disabled, drifted, missing, repeated, and unrelated-state fixtures. Do not apply either command to the live HOME in this step.

**Accepts:** Fixture dry-runs enumerate exact changes without mutation; enable generates only manifest-owned projections from the destination release; disable removes only those projections; unrelated files remain byte-identical; drift causes a safe refusal; repeated operations are no-ops; enable after disable restores the fixture; the live user scope is unchanged.

## Step 7 — Prove Project Adoption, Isolation, and Rollback

**Files:** `agent-harness/examples/minimal-project/`, `tests/test_install_uninstall.py`, `tests/test_client_isolation.py`, `tests/test_user_scope.py`, `docs/adoption.md`, `docs/rollback.md`, and release notes.

**Work:** Exercise the harness repository, a disposable minimal project, a neutral sibling project, and disposable enabled/disabled user-scope fixtures. Install selected project adapters, run smoke tasks and deterministic checks, uninstall, and verify byte-for-byte cleanup of owned files. Exercise rollback to the recorded source tag. Keep the real user scope active throughout this proof.

**Accepts:** Harness and minimal-project sessions load only selected project adapters; neutral-project sessions load no project adapter; disposable user-scope enable and disable both work; uninstall removes only owned assets; rollback restores the prior release; no real HOME mutation occurs; destination parity and isolation evidence are green.

## Step 8 — Cut Over Source Ownership and Simplify Dotfiles

**Files:** `.dotfiles/setup.sh`, `AGENTS.md`, `ai/`, `.claude/`, `.codex/`, `.cursor/`, `.gemini/`, `.windsurf/`, harness files under `scripts/` and `evals/`, `docs/agent-configuration-architecture.md`, a new durable decision in each repository, and `agent-harness/docs/migration-from-dotfiles.md`.

**Work:** After human approval and a green destination release candidate, remove migrated canonical assets and harness installation logic from `.dotfiles`. Retain personal configuration and thin repository-specific guidance. Update documentation to name `agent-harness` as source of truth. Preserve the currently active live projections until Step 9, but make their recorded owner the destination release and prevent `.dotfiles/setup.sh` from recreating them. Record the exact destination commit/tag in the migration decision.

**Accepts:** No migrated asset has two canonical copies; `.dotfiles/setup.sh` neither installs nor validates the harness; destination code has no executable `$HOME/.dotfiles` dependency; existing user-scope behavior still works from destination-owned projections; both repositories pass their reduced/expanded suites; rollback tag and enable/disable instructions are recorded before deletion.

## Step 9 — Turn Off Live User Scope and Prove Re-Enablement

**Files:** Runtime manifest-owned paths under `~/.claude/`, `~/.codex/`, `~/.cursor/`, `~/.gemini/`, `~/.windsurf/`, and `~/.agents/`; `~/.local/state/agent-harness/user-scope-receipt.json`; `~/.config/agent-harness/scope.json`; destination `scripts/scope.py` and `docs/user-scope.md`.

**Work:** Only after Steps 1-8 pass, review the live disable dry-run with the human, capture the receipt, disable user scope, restart clients, and confirm ordinary non-harness operation. Then perform one controlled live enable smoke test from the destination release, verify harness availability, disable it again, and leave `user_scope: disabled`. Never restore canonical files to `.dotfiles`.

**Accepts:** Disable changes only receipt-owned paths; ordinary clients and retained personal/MCP configuration still work; neutral repositories load no harness; the controlled enable restores user-scope harness behavior from the destination release; the second disable succeeds; final state is disabled; future enable dry-run is clean; repeated disable is a no-op.

## Step 10 — Freeze the Plugin-Ready Interface

**Files:** `harness.manifest.json`, `docs/plugin-contract.md`, manifest schema tests, adapter contract tests, and release/version metadata.

**Work:** Version the stable package interface consumed by a future plugin: asset groups, project and optional user-scope adapter entrypoints, configuration inputs, generated outputs, ownership receipt, install/uninstall hooks, compatibility matrix, and minimum harness version. Mark private controller internals as non-contractual. Do not create a marketplace entry or `.claude-plugin/plugin.json` in this migration.

**Accepts:** Contract tests detect breaking manifest/entrypoint changes; a documented plugin wrapper can select and install one project adapter without copying core logic; optional user scope uses the same versioned core; publishing and marketplace work remain explicitly out of scope; final user scope is disabled but supported for later explicit re-enable.

## Verification Matrix

Run existing checks from their source repository before cutover, then run their migrated equivalents from the destination:

```text
bash ./setup.sh --check
python3 scripts/config_doctor.py --summary
python3 scripts/config_inventory.py --summary
python3 scripts/guidance_adapter_check.py --summary
python3 scripts/mcp_topology_check.py --summary
python3 scripts/hook_config_check.py ai/config/claude/settings.base.json --summary
python3 scripts/hook_output_schema_check.py .claude/hooks --summary
python3 scripts/hook_target_check.py ai/config/claude/settings.base.json --summary
python3 scripts/self_modification_check.py --summary
python3 scripts/validate_skills.py
python3 scripts/run_evals.py --summary
python3 -m unittest -v scripts.test_setup_check
python3 -m unittest -v scripts.test_config_generate scripts.test_config_manifest scripts.test_config_inventory
python3 -m unittest -v scripts.test_mcp_topology_check
python3 -m unittest -v scripts.test_hook_target scripts.test_hook_config scripts.test_hook_fixture_runner
python3 -m unittest discover -s scripts
```

New destination gates:

```text
python3 scripts/validate.py --all
python3 scripts/doctor.py --project . --no-global-fallback
python3 -m pytest tests/test_manifest.py tests/test_project_scope.py
python3 -m pytest tests/test_install_uninstall.py tests/test_client_isolation.py
python3 -m pytest tests/test_adapter_generation.py tests/test_clean_home.py
```

Exact command names may only change if the corresponding manifest entry and documentation change in the same step; equivalent coverage may not be dropped.

## Rollback Strategy

- Before live disablement: no runtime change; delete the unapproved migration branch if abandoned.
- Before Step 8: reset the destination to its pre-migration tag; the existing live user scope and `.dotfiles` source remain unchanged.
- After Step 8 but before Step 9: restore both repositories to the recorded pre-cutover tags; live user scope remains active.
- After Step 9: run `enable-user-scope --dry-run`, resolve conflicts, then `--apply` from the recorded destination release if user scope must be restored. Never reconstruct links from memory or restore duplicate canonical source files.
- Any secret inclusion, global fallback, path escape, client-startup regression, or ambiguous ownership halts the migration and triggers rollback.

## Out of Scope

- Publishing or registering a plugin/marketplace package.
- Raising autonomy tiers, enabling autonomous merge, or changing the Agent Factory maturity roadmap.
- Replacing the existing lifecycle engine, review mechanism, or eval architecture during extraction.
- Migrating personal credentials, machine overlays, runtime history, caches, or unrelated dotfiles.
- Automatic user-scope fallback or permanent always-on global activation; explicit reversible user scope remains supported.

## Approval Required

Approval of this plan authorizes planning conclusions only. Implementation begins on isolated branches/worktrees in both repositories. Step 8 requires approval after destination parity evidence is available; Step 9 requires separate review of the live disable dry-run. User scope remains active until then and finishes disabled, not removed.
