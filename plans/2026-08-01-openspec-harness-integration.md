# OpenSpec Integration for the Agent Harness

**Date:** 2026-08-01
**Status:** Research complete; implementation not started
**Recommendation:** Conditional adoption as a constrained artifact engine
**Evaluated release:** `@fission-ai/openspec@1.7.0` / tag `v1.7.0`

## Executive decision

Adopt OpenSpec only for the layer this harness does not currently have: versioned behavioral
specifications, change-local planning artifacts, an artifact dependency graph, delta-spec
synchronization, and a preserved change archive.

Do not adopt OpenSpec as the harness's policy engine, agent orchestrator, implementation loop,
quality gate, acceptance authority, git workflow, or cross-tool configuration owner.

The safe integration shape is:

1. Pin the OpenSpec CLI as a repo-owned tool dependency.
2. Disable telemetry, registry update checks, and self-upgrade.
3. Never let `openspec init` or `openspec update` write into live tool configuration directories.
4. Keep all user-facing skills and commands owned by `ai/skills/`, `ai/commands/`, the manifest,
   and `setup.sh`.
5. Use a harness-specific OpenSpec schema and repository validators.
6. Project approved OpenSpec tasks into the existing per-worker frozen-spec contract.
7. Keep CAP/native Workflow, lensed review, Definition of Done, autonomy tiers, hooks, and stack
   workflow authoritative.
8. Gate spec sync/archive behind strict validation, review evidence, a clean worktree, and an A2
   human confirmation.

The recommended first rollout is planning-only in one disposable worktree. Apply, sync, and archive
remain disabled until the planning pilot proves that ownership and routing do not drift.

## Research basis and source freshness

### OpenSpec sources

- DeepWiki entry: <https://deepwiki.com/Fission-AI/OpenSpec>
- DeepWiki OPSX workflow: <https://deepwiki.com/Fission-AI/OpenSpec/3-opsx-workflow-system>
- DeepWiki AI integration: <https://deepwiki.com/Fission-AI/OpenSpec/5-ai-tool-integration>
- Repository: <https://github.com/Fission-AI/OpenSpec>
- Evaluated release: <https://github.com/Fission-AI/OpenSpec/releases/tag/v1.7.0>
- Documentation: `docs/concepts.md`, `docs/commands.md`, `docs/customization.md`,
  `docs/supported-tools.md`, `docs/cli.md`, and `docs/migration-guide.md` at `v1.7.0`
- Default schema: `schemas/spec-driven/schema.yaml` at `v1.7.0`
- Workflow templates: `src/core/templates/workflows/*.ts` at `v1.7.0`

DeepWiki was last indexed on 2026-07-02 at commit `546224e0`. Release `v1.7.0` was published on
2026-07-29 from commit `4e16790d`. DeepWiki is useful for architecture orientation, but current
release source and docs are authoritative where they differ.

### Harness sources

- `AGENTS.md`
- `docs/agent-configuration-architecture.md`
- `setup.sh`
- `ai/skills/manifest.csv`
- `ai/skills/using-my-skills/SKILL.md`
- `ai/skills/session-artifacts/SKILL.md`
- `ai/skills/goal-authoring/SKILL.md`
- `ai/skills/cap/`
- `ai/skills/lensed-review/`
- `ai/rules/agent-user-global.md`
- `ai/references/definition-of-done.md`
- `ai/agents/executor-implement.md`
- `.claude/workflows/orchestrate.js`
- `.claude/hooks/pre-tool-gate-v2.sh`
- `plans/specs/TEMPLATE.md`
- `plans/2026-07-27-native-agent-orchestration.md`
- `decisions/0002-separate-agent-guidance-from-dotfiles-distribution.md`
- `decisions/0006-agents-skills-standard-path.md`
- skill, config, hook, and orchestration validators under `scripts/`

### Local environment evidence

- Node is `v25.9.0`, satisfying OpenSpec's `>=20.19.0` minimum.
- OpenSpec is not installed.
- Both `npm view` and an isolated `npm exec @fission-ai/openspec@1.7.0` failed with
  `UNABLE_TO_GET_ISSUER_CERT_LOCALLY`.
- The integration pilot is therefore blocked until the local npm trust chain is fixed.
- Do not bypass this with `strict-ssl=false`, `NODE_TLS_REJECT_UNAUTHORIZED=0`, or another
  certificate-verification disablement.
- Homebrew currently exposes OpenSpec `1.6.0`, not the evaluated `1.7.0`; it is not an equivalent
  pilot substitute.

## What OpenSpec provides

OpenSpec has two durable project areas:

```text
openspec/
├── specs/                 # accepted behavioral capability specifications
└── changes/
    ├── <active-change>/   # proposal, delta specs, design, tasks, metadata
    └── archive/           # completed changes preserved with context
```

Its default artifact graph is:

```text
proposal ──┬──> specs ──┐
           └──> design ─┴──> tasks ──> apply
```

Each artifact is reported as `done`, `ready`, or `blocked`. The CLI exposes structured state through
`status --json` and dynamic prompt inputs through `instructions ... --json`. Custom schemas can
change artifact types, templates, and dependency edges.

The default core profile installs six workflows:

- propose
- explore
- apply
- update
- sync
- archive

The expanded set adds new, continue, fast-forward, verify, bulk archive, and onboard.

OpenSpec supports 30+ tools through generated project-local skills and tool-specific command
adapters. Relevant paths include:

| Tool | Skills | Commands |
|---|---|---|
| Claude Code | `.claude/skills/openspec-*` | `.claude/commands/opsx/*.md` |
| Cursor | `.cursor/skills/openspec-*` | `.cursor/commands/opsx-*.md` |
| Codex | `.codex/skills/openspec-*` | none; skills-only |
| Gemini CLI | `.gemini/skills/openspec-*` | `.gemini/commands/opsx/*.toml` |
| OpenCode | `.opencode/skills/openspec-*` | `.opencode/commands/opsx-*.md` |
| Devin Desktop | `.devin/skills/openspec-*` | `.devin/workflows/opsx-*.md` |

This broad adapter coverage is useful reference material, but those generated locations collide
with this repository's dotfiles distribution layer.

## What the harness already provides

### Configuration ownership

The harness deliberately separates:

- project guidance: `AGENTS.md`, `CLAUDE.md`, `docs/`, `decisions/`, `goals/`, `plans/`
- user-global cross-agent policy: `ai/rules/`
- canonical skills: `ai/skills/`
- canonical shared commands: `ai/commands/`
- tool adapters and hard controls: `.claude/`, `.cursor/`, `.codex/`, `.gemini/`, hooks, and config
- installation/distribution: `setup.sh` and symlinks

`ai/skills/manifest.csv` is the routing source of truth. `scripts/generate_router.py` derives
`ai/skills/using-my-skills/SKILL.md`, and `scripts/validate_skills.py` enforces manifest coverage.

`setup.sh` distributes canonical skills through:

- relative links into `.claude/skills/`
- individual user-level Claude skill links
- `~/.agents/skills -> ~/.dotfiles/ai/skills`
- legacy Codex links
- deliberately partial Cursor links
- deliberately partial Gemini links

Generated real directories under any of those tool paths create a second source of truth.

### Existing artifact model

| Existing artifact | Meaning |
|---|---|
| `goals/` | durable objective, scope, acceptance, and stop conditions |
| dated `plans/*.md` | executable implementation design with per-step Files/Accepts |
| `plans/active-context.md` | compact session pointer |
| `plans/progress.md` | chronological task progress |
| `plans/decisions.md` | active decision log |
| `decisions/` | durable architecture decisions |
| `plans/specs/*.md` | immutable-intent per-worker execution contract and runtime state |

### Existing execution and acceptance model

- The Coordinator owns planning and final acceptance.
- A fresh Executor receives a frozen spec, exact scope, and observable acceptance criteria.
- Native Claude Workflow runs implementation, lensed review, triage, and DoD acceptance.
- CAP supplies the cross-agent orchestration path.
- Findings are triaged as `intent_gap`, `bad_spec`, `patch`, `defer`, or `reject`.
- The frozen spec carries bounded retries, doubt/review counters, a spec change log, and review
  triage history.
- Hard hooks enforce tool use, naming, scope, model/fan-out limits, and git safety.
- Shipping is a separate stack/CI/autonomy pipeline.

OpenSpec does not replace any of these controls.

## Fit analysis

### The real gap OpenSpec fills

The harness has strong execution contracts and governance, but no canonical corpus describing the
system's accepted externally observable behavior. Existing plans explain individual changes, and
tests prove selected behavior, but there is no capability-level source of truth with delta changes.

`openspec/specs/` can fill that gap.

For this dotfiles repository, candidate capabilities include:

- skill discovery and distribution
- cross-client configuration portability
- frozen worker contract behavior
- native orchestration safety
- hook enforcement behavior
- autonomy and irreversible-action checkpoints

Not every change needs a behavior spec. Pure docs, internal refactors, tooling reorganizations, and
implementation-only cleanup should use OpenSpec's `skip_specs: true` rather than inventing behavior.

### Overlap and authority matrix

| Concern | Current authority | OpenSpec role | Integration rule |
|---|---|---|---|
| Policy and safety | hooks, settings, `AGENTS.md`, `ai/rules/` | prompt context only | current authority wins |
| Long-lived objective | `goals/` | change proposal can reference it | proposal does not replace goal |
| Accepted behavior | currently distributed | `openspec/specs/` | OpenSpec becomes scoped authority |
| Proposed behavior | goal/plan text | delta specs | OpenSpec owns behavior deltas |
| Change intent/scope | goal and dated plan | `proposal.md` | link rather than duplicate |
| Change-local design | dated plan | `design.md` | provisional design lives with change |
| Durable design decision | `decisions/` | design links to ADR | promote durable decisions to ADR |
| Implementation tasks | plan steps, TodoWrite | `tasks.md` | OpenSpec is checklist source |
| Worker handoff | `plans/specs/*.md` | source artifacts | frozen spec remains execution authority |
| Worker/run state | frozen-spec frontmatter/logs | no equivalent | harness only |
| Review | lensed review | generated verify prompt | harness is authoritative |
| Acceptance | task Accepts + DoD | file/status and heuristic verify | harness is authoritative |
| Git/PR/CI/merge | stack skills and hooks | none | harness only |
| Change history | goals/progress/ADRs | `changes/archive/` | complementary technical audit trail |
| Cross-tool adapters | `ai/skills`, manifest, setup | generated tool files | harness only |

### Naming collision to document

Two different kinds of "spec" remain:

- `openspec/specs/`: accepted behavior contracts
- `plans/specs/`: worker execution contracts

Do not silently merge them. Use the terms **behavior spec** and **worker contract** in skills,
commands, logs, and documentation. A future rename of `plans/specs/` to `plans/worker-specs/` may
improve clarity, but it is a separate migration and not required for the pilot.

## Why naive `openspec init` is unsafe

Running `openspec init --tools claude,cursor,codex,gemini,opencode` in this repository would:

1. Write real generated directories into paths that `setup.sh` expects to contain canonical
   symlinks or deliberate tool adapters.
2. Bypass `ai/skills/manifest.csv` and the generated skill router.
3. Add full duplicate workflow bodies as both skills and commands.
4. Let `openspec update` become a second owner that can remove or overwrite known files.
5. Add routing collisions with the existing `explore`, CAP, lensed review, archive, and ship skills.
6. Grant generated workflows broad `Bash(openspec:*)` access without integrating harness gates.
7. Put OpenSpec mutation behind child shell processes that current native Edit/Write guards cannot
   inspect file-by-file.
8. Introduce global profile/delivery state that can vary by machine.
9. Preserve OpenSpec's weaker completion semantics while making them look native.

Even `openspec init --tools none` is not safe against the live checkout without inspection:

- init performs legacy cleanup detection
- there is no trustworthy dry-run for the complete mutation set
- explicit non-interactive options can suppress the review prompt

Use it only in a disposable worktree/fixture and allowlist the resulting diff. For real project
bootstrap, prefer a harness-owned scaffold that writes only reviewed `openspec/` paths.

## Reliability and security findings

### OpenSpec state is navigation, not proof

OpenSpec `done` is based on output-path existence. An interrupted write, empty file, partial file,
or one match for a glob can appear complete. Upstream issue:
<https://github.com/Fission-AI/OpenSpec/issues/1084>.

The harness must validate content, required sections, placeholders, graph closure, freshness, and
source hashes independently.

### Custom schemas are prompt configuration, not hard gates

Custom schemas validate basic structure and dependency cycles. They do not provide first-class
test, lint, security, review, or acceptance gates. Upstream issue:
<https://github.com/Fission-AI/OpenSpec/issues/1142>.

Schema instructions, project context, and operation guidance are advisory. Hard controls remain in
hooks, validators, Workflow return schemas, and CI.

### Apply is weaker than the existing executor

The generated apply workflow:

- reads task checkboxes
- edits code directly
- marks checkboxes complete
- pauses on an agent-recognized blocker

It does not enforce:

- frozen intent
- exact file scope
- source artifact freshness
- test-first behavior
- objective test/coverage gates
- lensed review
- Coordinator triage
- DoD acceptance
- bounded retry/HALT state
- branch/worktree/commit discipline

Do not expose it unchanged.

### Verify is heuristic

The generated verify workflow uses code search and inference to estimate requirement/scenario
coverage. It returns prose grouped as critical/warning/suggestion. It is not a deterministic CLI
gate, persisted attestation, or reliable exit code.

Treat it as optional evidence only. Lensed review, real test commands, requirement-to-test
traceability, and DoD remain authoritative.

### Generated archive is unsafe for this harness

The generated archive workflow manually compares specs, performs semantic merge work, and then runs
`mkdir`/`mv`. It does not call the dedicated CLI archive command. It can continue after incomplete
artifacts/tasks or skipped sync when the user confirms. Upstream issue:
<https://github.com/Fission-AI/OpenSpec/issues/863>.

The CLI archive path is safer but still not transactional and has bypass flags. It must be wrapped,
run in an isolated branch/worktree, and followed by a complete diff and validation pass.

### Generated-file ownership is explicit

OpenSpec documents generated files as OpenSpec-owned. `update` can remove deselected workflows and
overwrite generated content. Skills and commands contain near-duplicate bodies. Upstream issue:
<https://github.com/Fission-AI/OpenSpec/issues/1139>.

No OpenSpec-generated file should become a live harness source.

### Supply chain

- Package license: MIT.
- Runtime requires Node `>=20.19.0`.
- Release `v1.7.0` has npm integrity/provenance tied to release commit `4e16790d`; the Git tag is
  not signed.
- A prior `tmp` path-traversal dependency issue was removed through dependency refresh in merged
  PR <https://github.com/Fission-AI/OpenSpec/pull/1249>, before `v1.7.0`.
- Use a lockfile and exact version; do not install `@latest`.
- Re-run dependency audit and provenance checks for every proposed upgrade.

### Network behavior

OpenSpec telemetry defaults on and sends command/version metadata. `openspec update` checks the npm
registry and can offer to install `@latest` globally.

Every harness invocation must set:

```text
OPENSPEC_TELEMETRY=0
DO_NOT_TRACK=1
OPENSPEC_NO_UPDATE_CHECK=1
```

The wrapper must reject `update` and self-upgrade.

## Recommended architecture

```text
User / agent request
        |
        v
Harness planning skill
        |
        +--> pinned wrapper --> OpenSpec JSON/status/instructions
        |                         |
        |                         +--> openspec/changes/<change>/
        |                         +--> openspec/specs/
        |
        +--> harness readiness validator
        |
        +--> dated plans/specs/<worker>.md
                     |
                     v
              CAP / native Workflow
                     |
          implement -> lensed review -> triage -> DoD
                     |
                     v
             harness closure gate
                     |
          strict validate -> human A2 approval
                     |
                     v
             CLI archive in worktree
```

### Ownership boundaries

#### Harness owns

- dependency pinning and invocation environment
- source-of-truth policy and precedence
- schema trust and path containment
- skills, commands, routing, and cross-tool distribution
- readiness and semantic validation
- frozen worker contracts and source hashes
- implementation runtime and concurrency
- tests, lint, security, coverage, and DoD
- review findings and Coordinator triage
- branch/worktree/commit/PR/CI/merge lifecycle
- archive authorization, rollback, and post-diff checks

#### OpenSpec owns

- active change directory shape
- behavior delta format
- artifact dependency graph and status hints
- dynamic artifact instructions and templates
- accepted behavior spec merge mechanics
- technical change archive layout

#### OpenSpec must never own

- files under live `.claude/`, `.cursor/`, `.codex/`, `.gemini/`, `.opencode/`, or `.devin/`
- global npm upgrades
- authority to declare implementation complete
- authority to bypass a hook, failed test, unresolved review finding, or DoD item
- authority to ship, merge, clean, or change autonomy configuration

## Harness-specific schema

Create a versioned schema named `agent-harness-v1`.

Recommended graph:

```text
proposal ──┬──> specs ──┐
           └──> design ─┼──> tasks ──> readiness ──> apply
                        ┘
```

### `proposal`

Required content:

- why
- exact intent
- in scope
- non-goals
- new and modified capabilities
- affected systems
- risk/autonomy classification
- linked goal, issue, or user request

Behaviorless work must set `skip_specs: true`.

### `specs`

Keep OpenSpec's delta format:

- ADDED
- MODIFIED
- REMOVED
- RENAMED
- requirements with SHALL/MUST
- observable scenarios with exactly `#### Scenario`

Specs contain behavior only. Tool names, file paths, libraries, and implementation steps belong in
design/tasks.

### `design`

Required content:

- current constraints
- goals/non-goals not already captured by the proposal
- decisions with alternatives
- security and failure behavior
- migration and rollback
- risks and mitigations
- links to durable ADRs
- no unresolved question that would change behavior, approach, or task breakdown

### `tasks`

Every checkbox must include:

- task ID and action
- exact Files scope
- observable Accepts criterion
- requirement/scenario references
- verification command or evidence
- dependency ordering

Example:

```markdown
- [ ] 2.1 Add strict change validation
  - Files: `scripts/openspec_integration_check.py`, `scripts/test_openspec_integration.py`
  - Accepts: the invalid-empty-artifact fixture exits non-zero with `artifact-incomplete`
  - Requirements: `change-readiness / Interrupted artifact`
  - Verify: `python3 scripts/test_openspec_integration.py`
```

### `readiness`

The artifact records, but does not by itself enforce:

- actionable
- logically ordered
- testable
- surface-anchored
- complete
- sufficient
- coherent
- no unresolved implementation-changing questions
- strict OpenSpec validation result
- harness semantic validator result
- explicit human approval when required

The harness validator must parse this artifact and independently re-run its checks. File existence is
not readiness.

### Schema distribution

Canonical source:

```text
ai/openspec/schemas/agent-harness-v1/
```

User-level discovery:

```text
~/.local/share/openspec/schemas/agent-harness-v1
  -> ~/.dotfiles/ai/openspec/schemas/agent-harness-v1
```

Project config selects the versioned schema. The wrapper must run `openspec schema which` and reject:

- a schema resolved from an unexpected path
- a schema whose content hash differs from the tracked version
- a project-local shadow unless the project explicitly opts into and reviews it
- a symlink or template path that escapes the approved schema/project roots

Do not use OpenSpec stores during the pilot. Stores are beta and add mutable machine-local resolution
that is unnecessary for one repository.

## Harness-owned OpenSpec interface

### Dependency layout

Use a nested tool package rather than a root `package.json`:

```text
tools/openspec/
├── package.json
└── package-lock.json
```

Reason: this repository's CI detects a root `package.json` and switches to npm/Jest coverage logic.
A nested package avoids changing the repository's test-runner classification.

Pin exactly:

```json
"@fission-ai/openspec": "1.7.0"
```

Use `npm ci --prefix tools/openspec`, not a global install and not `@latest`.

### Wrapper

Add a harness-owned wrapper, preferably Python for structured validation:

```text
scripts/openspec_harness.py
```

Responsibilities:

- resolve only `tools/openspec/node_modules/.bin/openspec`
- verify exact CLI version
- set telemetry/update environment variables
- set timeouts
- preserve stdout JSON and exit codes
- constrain the selected root to a repository/worktree
- reject path escapes and untrusted schema resolution
- expose read-only commands directly
- expose mutating commands only through named guarded operations
- log command, version, root, change, schema hash, and result without sensitive content

Allowed read operations:

- list
- show
- status
- instructions
- validate
- schemas
- schema which
- doctor

Guarded mutation operations:

- scaffold reviewed `openspec/` directories/config
- create a change
- archive a verified change

Denied operations:

- update
- config profile/delivery mutation
- global install/self-upgrade
- raw schema mutation
- store setup/register/remove during pilot
- archive bypass flags
- direct generated-skill/command installation

### Project bootstrap

Do not run OpenSpec init against the live project.

The wrapper should create only:

```text
openspec/
├── config.yaml
├── specs/
└── changes/
    └── archive/
```

`config.yaml` should be concise:

- select `agent-harness-v1`
- point agents to `AGENTS.md` rather than copying its contents
- contain only OpenSpec-specific artifact rules
- define apply/archive operation guidance as advisory
- never duplicate hook, git, model-routing, or autonomy policy

## Skill and command strategy

Do not import the 12 upstream generated skills.

Minimize routing surface with two harness-owned skills:

### `openspec-change`

Phase: plan.

Responsibilities:

- explore through the existing `explore` skill
- create/update proposal, specs, design, tasks, readiness
- run CLI status/instructions through the wrapper
- run strict structural and harness semantic validation
- stop before code
- produce a reviewed active change ready for projection

### `openspec-close`

Phase: review/ship boundary; explicit invocation only.

Responsibilities:

- require completed task checkboxes
- require accepted frozen worker contracts
- require real tests and lensed-review/DoD evidence
- re-check behavior/spec consistency
- preview spec synchronization
- require A2 confirmation
- invoke guarded CLI archive in an isolated worktree
- validate and review the resulting diff

### Existing components to extend

- CAP gets a `--from-openspec <change>` or equivalent preplanned mode.
- Native Workflow receives an explicit absolute frozen-spec path and change ID.
- Lensed review remains the review implementation.
- The Definition of Done remains the standing acceptance bar.
- Stack skills remain the only commit/PR/CI/merge path.

### Optional command

After the pilot, add one thin command:

```text
ai/commands/spec-change.md
```

It dispatches to the two skills and the wrapper. It must not contain a duplicate workflow body.
Cross-tool command adapters are deferred; skills are the portable interface.

## Frozen-spec bridge

The worker contract remains `plans/specs/YYYY-MM-DD-<label>.md`.

Add source traceability:

```yaml
openspec_change: <change-name>
openspec_schema: agent-harness-v1
openspec_source_hash: <hash of proposal/specs/design/tasks/readiness>
openspec_task_ids:
  - 2.1
  - 2.2
```

Projection rules:

1. Read current OpenSpec JSON status and every dependency artifact from disk.
2. Run strict OpenSpec validation and harness readiness validation.
3. Select a bounded task group.
4. Copy the user-approved intent into `<intent-contract>`.
5. Copy exact Files, Accepts, constraints, requirement references, and verification commands.
6. Record source hashes.
7. Run the existing frozen-spec readiness bar.
8. Spawn only after every criterion passes.
9. Before acceptance or task checkbox updates, re-hash source artifacts.
10. If hashes changed, halt and re-project; never accept against stale planning artifacts.
11. Mark OpenSpec tasks complete only after Coordinator acceptance, not worker self-report.

The existing date inconsistency must be fixed first: the hook applies the dated
`YYYY-MM-DD-context.md` convention to nested `plans/specs/*.md`, while some orchestration prose and
path construction still use undated `<label>.md`.

## Validation design

Add `scripts/openspec_integration_check.py` with machine-readable and summary output.

It must check:

- exact CLI version and locked dependency
- expected schema source and hash
- schema/template containment
- no generated OpenSpec artifacts under tool config directories
- no `opsx-*` or `openspec-*` unmanaged skills/commands
- config contains no duplicated policy block
- artifact graph closure
- required files are non-empty and contain required sections
- no placeholders, comments-only content, or incomplete writes
- proposal capability list matches delta spec paths
- behaviorless changes declare `skip_specs: true`
- delta specs pass `openspec validate --strict`
- task lines use valid checkboxes and each has Files/Accepts/requirement/evidence
- readiness checks are present and independently satisfied
- source hashes on frozen contracts are current
- task completion is backed by accepted worker evidence
- archive prerequisites are complete
- archive target and spec outputs remain inside the selected root
- no bypass flags or raw update/init command is used

Add fixture-driven tests for:

- interrupted/empty artifact falsely reported `done`
- glob with only one incomplete output
- missing capability delta
- partial MODIFIED requirement
- untrusted project schema shadow
- schema/template path escape
- stale frozen-spec source hash
- incomplete task marked complete without acceptance evidence
- generated real directory under `.claude/skills`
- OpenSpec update attempting to overwrite a managed path
- archive with incomplete artifacts/tasks
- failed spec sync leaving the change unarchived
- successful archive producing validated specs and a dated archive path
- telemetry/update environment always disabled

## Hard enforcement

Planning prose is not enough because OpenSpec mutates through Bash.

Add a command gate that:

- denies direct `openspec init`
- denies direct `openspec update`
- denies direct `openspec archive`
- denies OpenSpec self-upgrade/global package-manager invocations
- denies `--no-validate`, `--skip-specs`, and unattended `--yes`
- permits only `scripts/openspec_harness.py ...`
- prevents the wrapper from targeting `main` for mutating pilot operations
- requires a worktree for guarded archive

Add fixtures to prove every deny and allow path.

The wrapper must still validate internally; a shell command can be invoked outside Claude hooks by
Codex, Gemini, Cursor, a human, or CI.

## Cross-agent distribution

### Claude Code

- canonical skills link from `ai/skills/`
- native Workflow path for complex apply
- hard hooks available
- no generated `.claude/skills/openspec-*`
- no generated `.claude/commands/opsx/`

### Cursor

- add the two new skills to the explicit Cursor subset in `setup.sh`
- use portable CAP path unless a native equivalent is explicitly available
- defer `/opsx-*` command files

### Codex

- consume canonical skills through `~/.agents/skills`
- retain legacy links only as current setup requires
- do not use OpenSpec's `.codex/skills` generator
- use portable CAP path

### Gemini CLI

- consume canonical skills through the standard path/current harness adapter
- do not generate duplicate project-local `.gemini/skills`
- defer generated TOML commands
- use portable CAP path

### OpenCode and Devin/Windsurf

- treat as a later phase
- the current harness uses `opencode/`, while upstream writes `.opencode/`
- OpenSpec `windsurf` now aliases to Devin and writes `.devin/`, while this repo still has
  `.windsurf/` distribution
- do not claim parity until explicit discovery and invocation tests pass

## Alternatives considered

### A. Run OpenSpec init for every supported tool

**Rejected.**

Fastest setup, but creates a second owner for tool config, bypasses the manifest, duplicates commands
and skills, weakens enforcement, and lets update delete/overwrite files.

### B. Vendor all generated OpenSpec skills and commands into the harness

**Rejected.**

Creates 6-12 large overlapping skills plus tool-format variants, increases routing collisions, and
requires repeated manual merge work on every upstream release.

### C. Use OpenSpec concepts but reimplement the engine

**Rejected.**

Would duplicate artifact graph, delta parser, validation, status, and archive mechanics. The
maintenance cost is larger than wrapping the CLI.

### D. Use OpenSpec only as a behavior/artifact engine behind harness adapters

**Selected.**

Reuses the valuable data model while preserving one policy source, one execution pipeline, one
review mechanism, and existing hard controls.

### E. Do not adopt OpenSpec

**Fallback.**

Remain on goals/plans/frozen specs if the pilot cannot prevent ownership drift, semantic false
completion, unsafe archive behavior, or unacceptable routing overhead.

## Risk register

| Risk | Evidence | Control | Promotion condition |
|---|---|---|---|
| Generated files become a second source | OpenSpec owns and updates tool files | never generate into live repo; validator denies them | zero unmanaged tool artifacts |
| Empty/partial artifact appears done | issue #1084; existence-based status | semantic validator and source hashes | fixture is reliably rejected |
| Custom schema appears to enforce quality | issue #1142 | hooks/CI remain authoritative | all gates have executable checks |
| Apply bypasses frozen worker contract | upstream apply edits directly | CAP/orchestrator bridge | no complex apply runs upstream loop |
| Verify yields false confidence | heuristic search/report | lensed review + tests + DoD | real evidence required for closure |
| Archive moves/syncs unsafe state | generated archive manual and permissive | worktree, strict validation, A2 confirmation, post-diff | rollback drill passes |
| Update overwrites customization | documented generated ownership | update denied; reviewed version bump only | staged diff is deterministic |
| Skill routing collisions | explore/apply/verify overlap | two uniquely named skills + evals | no baseline regression |
| Global config differs by machine | profile/delivery/schema are user state | wrapper pins behavior and schema hash | clean-machine parity test |
| npm install is not reproducible | global `@latest`, ranged deps | exact nested dependency + lockfile | frozen install and audit pass |
| npm registry trust failure | local issuer error | configure trusted CA; never disable TLS | isolated install succeeds securely |
| Telemetry/update network calls | defaults and update behavior | three env controls + network test | no outbound call in fixture |
| Concurrent changes drift | file state and non-transactional archive | one-change pilot; per-change worktrees/locks later | concurrency test passes |
| Specs duplicate existing policy | broad config context temptation | behavior-only scope and validator | no copied AGENTS/rules blocks |
| OpenSpec store drift | beta machine-local registry | stores disabled | separate design and pinning decision |

## Rollout phases

### Phase 0 — Preconditions

- resolve npm CA trust
- freeze OpenSpec `1.7.0`
- fix the dated frozen-spec path inconsistency
- record ownership boundaries
- verify no live OpenSpec-generated files exist

### Phase 1 — Read-only CLI pilot

- install exact dependency in nested tool package
- add wrapper
- run list/status/instructions/validate/schema resolution in isolated fixtures
- keep all OpenSpec mutations disabled

### Phase 2 — Planning-only pilot

- add schema and `openspec-change`
- scaffold one pilot repository/change without tool generation
- create/review proposal, delta specs, design, tasks, readiness
- do not apply, sync, or archive

### Phase 3 — Execution bridge

- project a reviewed task group into a dated frozen worker contract
- run existing CAP/native Workflow
- mark tasks complete only after acceptance
- prove stale-source detection

### Phase 4 — Guarded closure

- add `openspec-close`
- require strict validation, tests, lensed review, DoD, and A2 approval
- run archive in an isolated worktree
- verify resulting specs/archive and complete diff

### Phase 5 — Cross-client distribution

- link the two skills through existing setup paths
- add routing and invocation tests for Claude, Cursor, Codex, and Gemini
- defer OpenCode/Devin until explicit path parity work

### Phase 6 — Promotion decision

- compare pilot results against adoption metrics
- adopt for new behavioral changes, remain planning-only, or remove cleanly
- do not migrate historical plans/goals/decisions in bulk

## Implementation plan

### Step 0 — Resolve install trust and freeze the evaluation baseline

**Files:**

- no repository files until the trust chain is understood
- later evidence in this plan or a dedicated pilot report

**Actions:**

1. Configure npm/Node to trust the correct local or corporate root CA.
2. Verify `npm view @fission-ai/openspec@1.7.0` succeeds with certificate verification enabled.
3. Verify package integrity/provenance and release commit.
4. Record runtime and package-manager versions.
5. Confirm there are no known advisories in the locked production graph.

**Accepts:**

- npm access succeeds without disabling TLS verification
- exact `1.7.0` metadata and integrity are recorded
- the pilot stops if provenance, integrity, or audit checks fail

### Step 1 — Fix the frozen worker-contract path invariant

**Files:**

- `plans/specs/TEMPLATE.md`
- `.claude/workflows/orchestrate.js`
- `.claude/hooks/pre-tool-gate-v2.sh`
- `scripts/test_orchestrate_workflow.py`
- hook fixtures covering plan naming

**Actions:**

1. Choose one dated convention: `plans/specs/YYYY-MM-DD-<label>.md`.
2. Make template, Workflow path construction, prompts, hook checks, and tests agree.
3. Preserve explicit absolute-root confinement.
4. Add a real-run fixture for a dated worker contract.

**Accepts:**

- every producer and consumer uses the same dated path
- a valid dated worker contract is writable
- an undated contract is rejected before a worker starts
- existing HALT/terminal-status tests remain green

### Step 2 — Record the architecture boundary

**Files:**

- `decisions/<next>-adopt-openspec-as-artifact-engine.md`
- `docs/agent-configuration-architecture.md`
- `AGENTS.md`
- `plans/decisions.md`

**Actions:**

1. Record the selected ownership model.
2. Define behavior spec vs worker contract terminology.
3. Place OpenSpec in the precedence model below hard enforcement and canonical project guidance.
4. State that generated tool artifacts and raw updater use are unsupported.
5. State that goals, dated plans, worker contracts, ADRs, and stack workflow remain.

**Accepts:**

- a fresh agent can identify one authority for every artifact/policy type
- no document claims OpenSpec is an execution or acceptance authority
- durable and session decision records link to each other

### Step 3 — Add a reproducible CLI package and wrapper

**Files:**

- `tools/openspec/package.json`
- `tools/openspec/package-lock.json`
- `.gitignore`
- `scripts/openspec_harness.py`
- `scripts/test_openspec_harness.py`
- optionally `scripts/install-openspec.sh`

**Actions:**

1. Pin exact OpenSpec `1.7.0` in a nested package.
2. Resolve only the nested binary.
3. Add exact-version, timeout, root, path, schema, and environment checks.
4. Implement a read-only operation allowlist.
5. Reject updater/global config/store operations.
6. Keep installation explicit during pilot; do not silently add a network install to `setup.sh`.

**Accepts:**

- `npm ci --prefix tools/openspec` is reproducible
- the wrapper refuses another OpenSpec version or binary
- telemetry and update checks are disabled on every invocation
- read-only JSON output and exit codes pass through unchanged
- denied operations fail before invoking OpenSpec
- no root `package.json` is added

### Step 4 — Add the versioned harness schema

**Files:**

- `ai/openspec/schemas/agent-harness-v1/schema.yaml`
- `ai/openspec/schemas/agent-harness-v1/templates/proposal.md`
- `ai/openspec/schemas/agent-harness-v1/templates/spec.md`
- `ai/openspec/schemas/agent-harness-v1/templates/design.md`
- `ai/openspec/schemas/agent-harness-v1/templates/tasks.md`
- `ai/openspec/schemas/agent-harness-v1/templates/readiness.md`
- schema tests/fixtures

**Actions:**

1. Implement proposal/specs/design/tasks/readiness graph.
2. Preserve `specs` as the behavior-delta artifact.
3. Define task Files/Accepts/requirements/evidence format.
4. Define readiness record format.
5. Validate cycles, templates, path containment, and expected hash.

**Accepts:**

- `openspec schema validate agent-harness-v1` passes
- a fixture reports the expected dependency order
- tasks cannot pass harness validation without every required field
- readiness cannot pass with placeholders or unresolved blocking questions
- schema/template paths cannot escape their approved root

### Step 5 — Add safe schema distribution and project bootstrap

**Files:**

- `setup.sh`
- `scripts/openspec_harness.py`
- `scripts/test_portable_config_templates.py` or a focused OpenSpec setup test
- `openspec/config.yaml` only when this repository becomes the pilot

**Actions:**

1. Link the canonical schema into the OpenSpec user schema directory.
2. Add a bootstrap operation that writes only reviewed `openspec/` paths.
3. Keep config context concise and non-duplicative.
4. Reject schema shadowing and unexpected resolution.
5. Add setup dry-run/check coverage.

**Accepts:**

- setup creates exactly one canonical schema link
- bootstrap never writes into tool configuration directories
- repeated bootstrap is idempotent
- `schema which` resolves to the tracked expected schema
- setup checks pass on a clean machine fixture

### Step 6 — Add semantic change validation

**Files:**

- `scripts/openspec_integration_check.py`
- `scripts/test_openspec_integration.py`
- `scripts/fixtures/openspec/**`
- `setup.sh --check` integration
- CI/pre-commit wiring selected by the implementation branch

**Actions:**

1. Implement all checks from the Validation design section.
2. Emit stable rule IDs and JSON/summary modes.
3. Keep an explicit baseline only for pre-existing unrelated findings; new OpenSpec rules are not
   ratcheted away.
4. Test interrupted/empty/glob/stale/shadow/archive cases.

**Accepts:**

- every invalid fixture fails for its intended stable rule ID
- every valid fixture passes
- an empty artifact is rejected even when OpenSpec status says `done`
- generated tool artifacts are rejected
- stale frozen source hashes are rejected
- validator is wired into the same reviewable check surfaces as other harness validators

### Step 7 — Add the planning adapter

**Files:**

- `ai/skills/openspec-change/SKILL.md`
- optional step/reference files under `ai/skills/openspec-change/`
- `ai/skills/manifest.csv`
- generated `ai/skills/using-my-skills/SKILL.md`
- routing eval fixtures/cases
- `ai/skills/README.md`

**Actions:**

1. Implement planning-only create/update/status flow through the wrapper.
2. Reuse the existing `explore` skill for pre-change research.
3. Require user review of intent, behavior deltas, and high-impact decisions.
4. Run strict and harness validation before declaring ready.
5. Stop before implementation.

**Accepts:**

- the skill creates no implementation code
- router is regenerated from the manifest
- manifest and skill lint pass
- routing evals distinguish OpenSpec planning from generic exploration, CAP, and goal authoring
- no upstream generated skill or command is present

### Step 8 — Add frozen-contract projection

**Files:**

- `plans/specs/TEMPLATE.md`
- `scripts/openspec_harness.py`
- projection-specific tests/fixtures
- `ai/agents/executor-implement.md`

**Actions:**

1. Add change/schema/task/hash traceability.
2. Generate one dated frozen contract per bounded worker task group.
3. Re-run readiness before projection.
4. Verify source hashes before worker acceptance and task completion.
5. Halt on drift rather than silently reconciling it.

**Accepts:**

- projection is deterministic for identical inputs
- every projected contract has exact Files and observable Accepts
- source changes invalidate the contract
- no task is checked off before Coordinator acceptance
- parallel worker labels cannot collide

### Step 9 — Integrate the existing execution runtimes

**Files:**

- `ai/skills/cap/SKILL.md`
- relevant CAP step files and `cap-workflow.js`
- `.claude/workflows/orchestrate.js`
- `scripts/test_orchestrate_workflow.py`
- CAP tests/evals

**Actions:**

1. Add a preplanned OpenSpec mode that consumes the projected contract.
2. Skip duplicate planning phases in that mode.
3. Keep TDD, bounded retries, lensed review, triage, DoD, and HALT behavior.
4. Pass explicit absolute root, change ID, and contract path.
5. Return acceptance evidence to the wrapper.

**Accepts:**

- exactly one execution engine owns each run
- native Claude and portable paths consume the same contract
- no upstream OpenSpec apply workflow edits code
- failure writes durable HALT state
- accepted completion updates only the corresponding OpenSpec tasks
- existing orchestration and CAP tests remain green

### Step 10 — Add guarded closure and archive

**Files:**

- `ai/skills/openspec-close/SKILL.md`
- `scripts/openspec_harness.py`
- `ai/skills/manifest.csv`
- generated router
- archive fixtures/tests
- autonomy/audit integration selected by implementation

**Actions:**

1. Require strict OpenSpec and harness validation.
2. Require accepted worker contracts, tests, lensed review, triage, and DoD.
3. Preview delta impact.
4. Require explicit A2 approval.
5. Run CLI archive through the wrapper in an isolated worktree.
6. Validate all resulting behavior specs and archive paths.
7. Review the complete diff before any commit.

**Accepts:**

- closure fails on any incomplete task, stale hash, failed test, unresolved finding, or unmet DoD
- no bypass flag is accepted
- no archive starts without logged A2 confirmation
- failed sync leaves the active change recoverable
- successful archive produces validated specs and one dated archive directory
- stack workflow remains the only shipping path

### Step 11 — Add hard command gates

**Files:**

- `.claude/hooks/pre-tool-gate-v2.sh`
- `scripts/fixtures/pretool-gate-v2.json`
- equivalent portable wrapper tests

**Actions:**

1. Deny direct mutating OpenSpec commands.
2. Allow wrapper-mediated read operations.
3. Require branch/worktree and A2 conditions for archive.
4. Test command quoting, absolute paths, `npx`, npm scripts, shell wrappers, and aliases.

**Accepts:**

- direct init/update/archive and bypass variants are denied
- the approved wrapper path is allowed
- equivalent indirect invocations cannot evade the gate
- portable wrapper enforcement works without Claude hooks
- all existing pre-tool fixtures still pass

### Step 12 — Distribute to the first four clients

**Files:**

- `setup.sh`
- cross-client setup/drift tests
- Cursor explicit skill subset
- docs for Claude/Cursor/Codex/Gemini invocation

**Actions:**

1. Distribute only the two harness-owned skills.
2. Verify Claude, Cursor, Codex, and Gemini discovery.
3. Verify no generated project-local OpenSpec skills/commands appear.
4. Defer OpenCode/Devin parity.

**Accepts:**

- one canonical skill body serves all four clients
- all symlinks resolve in the main checkout and a worktree
- skill coverage/drift checks pass
- invocation smoke tests pass for all four clients
- no tool-specific duplicate workflow body is introduced

### Step 13 — Run one planning-only pilot

**Files:**

- one isolated feature worktree
- one low-risk `openspec/changes/<pilot>/`
- pilot evidence report under `plans/`

**Actions:**

1. Choose one small, observable, non-security-critical harness behavior.
2. Create proposal, one delta capability spec, design if needed, tasks, and readiness.
3. Run strict and harness validators.
4. Stop before implementation.
5. Measure artifact quality, routing behavior, setup friction, and duplicated content.

**Accepts:**

- no file outside the approved OpenSpec/planning paths changes
- all validations pass
- a human can trace each task to behavior and evidence
- no existing goal/plan/decision authority becomes ambiguous
- planning overhead is judged acceptable before Phase 3 is authorized

### Step 14 — Run one end-to-end pilot

**Files:**

- a new isolated worktree/change
- one projected frozen worker contract
- execution/review/closure evidence

**Actions:**

1. Author and approve the change.
2. Project a task group.
3. Execute through native Workflow or portable CAP.
4. Re-run tests, lensed review, triage, and DoD.
5. Exercise stale-hash rejection once.
6. Archive through the guarded worktree path.
7. Review the full diff and rollback drill.

**Accepts:**

- one change completes without bypassing a harness control
- stale planning data is detected and blocks acceptance
- task completion reflects Coordinator acceptance
- archive produces correct behavior specs and preserved change history
- rollback restores a usable active state without destructive git commands

### Step 15 — Decide promotion, restriction, or removal

**Files:**

- this plan
- pilot evidence report
- durable decision update
- any goal/index only if implementation is explicitly authorized as a goal

**Actions:**

1. Compare evidence to promotion criteria.
2. Choose one:
   - promote for new behavioral changes
   - retain planning-only
   - remove the integration
3. Record limitations and upgrade process.
4. Do not bulk-migrate historical artifacts.

**Accepts:**

- decision cites measured pilot evidence
- unsupported clients and operations remain explicitly named
- rollback/removal path is tested
- no automatic upgrade or schema migration is enabled

## Promotion criteria

Promote beyond planning-only only if all hold:

- zero OpenSpec-generated files under live tool config directories
- zero unresolved manifest/router/skill drift
- zero direct raw mutating OpenSpec command paths
- every false-`done` fixture is rejected by harness validation
- source-hash drift blocks worker acceptance
- real test/review/DoD evidence gates closure
- archive rollback drill succeeds
- four-client discovery passes
- no routing eval regression
- no telemetry or update-check network event
- the user explicitly approves promotion

## Rollback plan

The integration is removable because canonical policy and execution remain outside OpenSpec.

Rollback:

1. Disable the two skills in the manifest and regenerate the router.
2. Remove their distribution links through `setup.sh`.
3. Remove the wrapper and nested dependency.
4. Remove the user-level schema link.
5. Leave existing `openspec/` directories archived or move their useful behavioral specs to docs
   through a reviewed change.
6. Re-run setup, skill, routing, hook, and config checks.
7. Preserve pilot evidence and the decision record.

No historical goals, plans, worker contracts, or ADRs need conversion to roll back.

## Explicit non-goals

- replacing goals
- replacing dated implementation plans
- replacing `plans/specs/` worker contracts
- replacing CAP or native Workflow
- replacing lensed review or Definition of Done
- replacing stack branches, PRs, CI, merge, or cleanup
- importing every upstream workflow
- enabling OpenSpec stores
- bulk-converting historical plans or decisions
- enabling OpenSpec self-update
- supporting every upstream AI tool in the first rollout
- changing autonomy above A2

## Stop and ask if

Stop before implementation if:

- npm trust cannot be fixed without disabling certificate verification
- a root package manifest is proposed
- OpenSpec must own files under a live tool config directory
- `openspec init` produces a diff outside the reviewed `openspec/` allowlist
- the schema cannot preserve behavior-only specs and task Files/Accepts
- a mutating command cannot be contained to an isolated worktree
- a quality or archive gate remains prompt-only
- an existing goal/plan/frozen-spec authority would become ambiguous
- the proposed pilot includes security-critical, production, or irreversible work
- OpenSpec stores or cross-repo planning become required
- promotion is requested without completed planning and end-to-end pilot evidence
