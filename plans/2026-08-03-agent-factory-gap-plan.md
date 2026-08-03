# Agent Factory Gap Analysis and Delivery Plan

**Date:** 2026-08-03
**Status:** Draft for human approval
**Target:** `/Users/axos-agallentes/git/agent-harness/docs/The_Agent_Factory.md`
**Evidence boundary:** Current-state claims use executable code, configuration, tests/evals, generated
artifacts, live symlinks, and observed command behavior only. Existing repository `docs/`, `decisions/`,
`goals/`, and prior `plans/` were not used to infer harness behavior.

## Recommendation First

Treat the current system as a **Level-2 standardized platform with experimental Level-3 components**.
Do not advertise it as a Level-3 agentic harness or target-level A3 implementation yet. Preserve the
good foundations, immediately disable the contradictory admin-merge path and self-modifying policy
path, make validation truthful, then converge on one client-neutral controller running untrusted
workers in an actual sandbox with deterministic, promotion-grade evaluations.

The delivery order is deliberately safety-first:

1. **Contain unsafe actuation.** Disable the skipped-permission/admin-merge path and automatic policy
   self-graduation before changing any other actuation surface.
2. **Make the baseline truthful.** Repair host portability and make required runtime checks fail closed.
3. **Declare the contract, trust root, evidence verifier, and client roles.** No worker starts without them.
4. **Clean activation from an inventory.** Registry projections and measured compatibility quarantine replace
   ambiguous live delivery.
5. **Enforce sandbox and artifact boundaries.** Worktrees remain Git scope isolation, not security isolation.
6. **Add only a minimal controller seam.** `scripts/ai/git_lifecycle.py` remains the persisted-run authority.
7. **Route independent review by declared risk.** Low-risk work does not pay for irrelevant mandatory lenses.
8. **Add action coverage and signed attestation.** Evaluation evidence earns no effect until independently verified.
9. **Aggregate redacted telemetry.** Metrics consume safe event evidence; they never become a raw prompt store.
10. **Run A3-candidate pilots only.** The factory may open validated PRs; human merge remains mandatory.

## Target Interpretation

The target defines four independent dimensions:

- **Maturity:** Level 2 shared/governed practices; Level 3 scoped multi-step loops in secure sandboxes;
  Level 4 autonomous delivery cells as the continuous system of work.
- **Autonomy behavior:** observe → suggest → edit in sandbox → open PR → controlled merge → restricted
  high-impact autonomy.
- **Platform:** agent-readable knowledge, standardized MCP interfaces, agent-to-agent review, and
  deterministic golden-task evaluations.
- **Operating horizons:** metrics/pilots → standardization → bounded harness → delivery cells →
  enterprise default.

The target's autonomy labels cannot be compared numerically with this repository's current A0-A4
labels. The two ladders assign different behavior to the same numbers. All migration decisions must
name the allowed behavior, not only an `A*` label.

## Author-Defined Readiness Rubric

This is an **author-defined readiness rubric**, not a score defined by the target document. It maps the
target's Maturity, Autonomy behavior, Platform, and Operating-horizon sections to 16 implementation-facing
criteria. Strict scoring is 0=absent/contradicted, 1=partial/unverified, 2=reproducibly proven. Each
criterion has equal weight (two points): equal weighting prevents a strong shared-config foundation from
masking a missing sandbox, deterministic gate, or evidence path. The total is 32 points and is a gap
indicator, never an autonomy authorization.

| Rubric criterion | Target-section mapping | Score | Executable evidence | Judgment |
|---|---:|---|---|
| Level-2 standardized AI | Maturity | 1 | `guidance_adapter_check` 28/28; six portable config bases; enforcement differs materially by client | Partial |
| Level-3 agentic harness | Maturity | 1 | `.claude/workflows/orchestrate.js` and lifecycle controller exist; secure sandbox and reliable loop do not | Prototype |
| Level-4 factory | Maturity | 0 | No continuous delivery-cell scheduler, capacity model, or retained outcome loop | Absent |
| Intent contract | Platform | 1 | Frozen specs and lifecycle-owned paths exist; required risk tier and executable acceptance contract are not unified | Partial |
| Secure sandbox | Maturity / Autonomy behavior | 0 | Local execution has host access; worktrees isolate Git state only; remote legacy path uses write/admin credentials with skipped permissions | Absent |
| MCP + knowledge + A2A loop inputs | Platform | 2 | MCP topology 34/34; shared guidance loaders; worker/reviewer stages exist | Present, with delivery drift |
| Deterministic pre-review gate | Platform / Autonomy behavior | 0 | Native orchestrator does not require deterministic tests; legacy test detection may return no runner | Absent |
| A3 open-PR behavior | Autonomy behavior | 1 | Bound Claude lifecycle can stack/commit/push/open PR; evidence tier is A0 and a conflicting admin-merge path remains | Shape exists, claim unearned |
| A4 controlled merge | Autonomy behavior | 0 | Canonical lifecycle blocks merge; legacy workflow admin-merges without the required policy proof | Not implemented safely |
| A5 restricted high-impact autonomy | Autonomy behavior | 0 | No measurable high-impact restriction profile or evidence gate | Absent |
| Evidence-earned promotion | Autonomy behavior / Operating horizons | 0 | Resolver exists, but no tracked `evals/reports/*.json`; reversible legs use a risk override; hook policy can self-modify | Contradicted |
| Agent-readable knowledge | Platform | 2 | Thin client adapters load shared rules; instruction loader checks pass | Strong |
| Reliable MCP for search/tests/observability | Platform | 1 | Search/context interfaces are healthy; standardized test and observability MCP interfaces are absent | Partial |
| Specialized A2A review | Platform | 1 | Lensed review exists; architecture is not a configured lens; null review currently continues | Partial/unsafe |
| Golden-task evaluation architecture | Platform / Operating horizons | 1 | 11 case files, 41 behavioral cases, 5 sensitivity cases; on-demand only and no promotable reports | Prototype |
| Horizon outcomes | Operating horizons | 0 | Current metrics job is project-specific and does not measure factory outcomes | Not evidenced |

**Total: 11/32 (34%).**
**Maturity verdict:** Level 2 with Level-3 prototypes.
**Autonomy verdict:** Target-A3-shaped behavior exists only in one bounded Claude path; it is neither
cross-client nor evidence-earned. Target A4/A5 are not authorized.

## What Is Working and Worth Keeping

1. **Shared guidance distribution:** thin adapters and shared rules have 28/28 loader checks.
2. **Portable config foundations:** six canonical base/runtime/overlay records are present and parse;
   config generation tests pass 45 cases.
3. **MCP topology:** 34/34 topology assertions pass, with seven dedicated unit tests.
4. **Pre-tool fixture behavior:** the primary Claude pre-tool fixture suite passes 7/7.
5. **Git scope controls:** worktrees, exact base SHA, owned-path validation, stale-decision checks, action
   journaling, and demotion markers are substantive building blocks.
6. **Irreversible-leg fail-closed behavior:** `auto_ship` and `auto_clean` resolve to effective A0 because
   evidence is absent, despite declared A2.
7. **Review consolidation direction:** `lensed-review` provides one configurable finding contract and
   isolated lens references; the design should be retained while execution is made fail-closed.
8. **Evaluation mechanics:** the existing runner already supports routing, behavioral execution, grader
   isolation, and sensitivity analysis. It needs promotion-grade integration, not replacement.

## What Is Missing

### Governance and intent

- One canonical, machine-validated intent contract containing objective, risk class, base SHA, owned
  paths, sandbox profile, acceptance commands, required review profile, and allowed terminal action.
- One behavior-based autonomy ladder. The current and target ladders reuse labels with different meanings.
- Promotion evidence bound to commit SHA, case-set digest, runner identity, freshness, and observed outcomes.
- A human-owned exception process that cannot be authored or applied by the running agent.

### Security boundary

- An actual executor trust boundary. A linked worktree is not a sandbox.
- Least-privilege, short-lived credentials and an explicit egress policy.
- Separation between untrusted model output and the trusted component that applies a patch or opens a PR.
- Negative tests for secret reads, out-of-scope writes, prompt injection, unauthorized network/MCP access,
  and merge attempts.

### Factory loop

- A single deterministic state machine from validated intent through artifact, review, eval, PR, and halt.
- Reliable retry/repair semantics. A failed worker/reviewer must block or consume a bounded retry; it must
  never silently become zero findings.
- Independent review profiles selected from risk and changed surfaces; Security and Architecture are required
  only when the declared risk route requires them.
- Queueing, capacity, ownership, incident response, cancellation, and recovery for continuous delivery cells.

### Verification and learning

- CI-enforced behavioral and pressure evals for every autonomous stage.
- A versioned evidence ledger consumed by the autonomy resolver.
- Factory outcome metrics: success without intervention, human minutes, time-to-PR, escaped findings,
  rollback rate, scope violations, sandbox violations, cost, and promotion/demotion history.
- Cross-client conformance tests or an explicit declaration that a client is assist-only.

## What Is Not Working

| Priority | Finding | Evidence and consequence |
|---|---|---|
| P0 | Staged-change pipeline signal fails on the host | Full test discovery exits 1. `test_commit_due_when_small_changeset_staged` fails because `scripts/ai/atomic-status.sh:181-182` uses Bash associative arrays while `/bin/bash` is 3.2. The gate loses the signal exactly when a commit/split decision is needed. |
| P0 | Legacy autonomous workflow contradicts the target and local policy | `.github/workflows/claude-auto.yml:146` uses `--dangerously-skip-permissions` with write/admin credentials; `ai/skills/claude-auto/SKILL.md:393` performs `gh pr merge --admin`; its CI query excludes coverage and diff-size gates at line 355. |
| P0 | Native workflow has fail-open success paths | `.claude/workflows/orchestrate.js:478` lets an invalid worker continue; line 508 converts reviewer failure into zero findings; patch findings have no patch stage; line 630 can still halt `done`. Its 37 tests finish in 0.003s because they validate source shape, not the workflow behavior. |
| P0 | Policy checks are deliberately masked | `.github/workflows/claude-auto-gates.yml:57-81` appends `|| true` to hook schema, self-modification, hook config, and skill-reference checks. Current direct runs return non-zero. |
| P0 | Runtime policy self-modifies | `.claude/hooks/hook-graduate.sh:75-78` edits `hook-config.yaml` and its state; `sessionstart.sh` runs it automatically. `self_modification_check` reports two findings. |
| P1 | Claude pre-tool registration excludes MCP tools | `hook_config_check` reports `missing-mcp-tool-matcher`; the settings matcher at `ai/config/claude/settings.base.json:360` omits `mcp__*`. Fixture success does not prove event delivery. |
| P1 | Installed skills drift from canonical source | Live Claude and Codex skill roots lack `lensed-review` and `using-my-skills` but retain retired `tech-lead`; worktree projections show the opposite intended state. |
| P1 | Skill registry is not authoritative | `python3 scripts/validate_skills.py` exits 1 with 30 enabled top-level skills absent from `ai/skills/manifest.csv`; the check is not a blocking setup/CI gate. |
| P1 | Promotion evidence is empty | `evals/reports/` is absent and zero reports are tracked. Reversible legs report evidence A0 but effective A2 from a temporary risk override. |
| P1 | Full hook configuration is not clean | Direct checker reports 14 findings: 11 ignored matchers, one missing MCP matcher, and two unordered parallel-handler groups. |
| P2 | Hook schema checker contains permanent noise | It flags `stop.sh` for parsing a legacy decision shape, and its test preserves that finding as a baseline. This weakens trust in red output. |
| P2 | Live config ownership is ambiguous | Some user configs are symlinks while Codex/Gemini/Cursor are divergent regular files; generation comparison finds drift without a single policy for reconciliation. |
| P2 | Metrics are not factory metrics | `scripts/ai/harness-weekly-metrics.sh` hard-codes another repository, appends even when called with `--help`, and measures compaction/advisory counts rather than delivery outcomes. |

## What Is Too Much, Redundant, or Obsolete

Size is not itself a defect; these items are candidates because activation or independent evidence shows
duplication, drift, or no consumer.

- **Hook surface:** 60 current top-level hook executables plus 15 archived ones, 7,390 lines total.
  Fourteen current files have no static executable/config consumer. Manual diagnostics should move out of
  the runtime hook directory; archives belong in Git history, not the active distribution.
- **Duplicate LeanCtx telemetry:** direct binary registrations, wrapper registrations, and aggregator calls
  repeat observation for the same events. Retain one measured path per event.
- **Known no-op:** `.claude/hooks/lean-ctx-redirect.sh` exits immediately and is not the registered direct
  redirect implementation.
- **Self-graduation machinery:** `hook-graduate.sh` and `hook-graduation-state.json` weaken or alter policy
  automatically and conflict with evidence-owned autonomy.
- **Skill surface:** 73 tracked `SKILL.md` files (68 top-level plus five nested lab/snapshot artifacts),
  11,796 lines, 110 disabled skill overrides, and 30 enabled skills outside the router manifest.
- **Accidental skill leakage:** nested workspace outputs under `ai/skills/*workspace*` are discoverable as
  live skills, including an old generated Kubernetes skill and a duplicate Vision skill.
- **Review duplication:** lensed review is declared canonical, but `claude-auto` embeds separate Security,
  Performance, and Style reviewer prompts; legacy shim skills and agents remain discoverable.
- **Competing factory paths:** prompt-driven `claude-auto`, native `orchestrate.js`, CAP-style skill routing,
  and the deterministic lifecycle adapter overlap without one authoritative state machine.
- **Lifecycle concentration:** the controller/adapter/bridge core is 4,988 lines, including high-complexity
  functions. Preserve its safety invariants, but split policy, state, adapters, and effects behind tests.
- **Fixed context cost:** `lean-ctx tools health` reports 11,285 fixed tokens per session, duplicate full
  Cursor rules, one never-used tool, and 439 reclaimable schema tokens. This is a measured optimization,
  not a reason to remove useful tools blindly.

## Target Architecture

```text
Human / trusted intake
        |
        v
Machine-validated intent contract
(objective, risk, base SHA, owned paths, accepts, terminal action)
        |
        v
Human-owned policy + evidence resolver -------- retained eval/outcome ledger
        |                                                   ^
        v                                                   |
Client-neutral factory controller --------------------------+
        |
        +--> disposable executor cell --> patch artifact --> deterministic tests
        |          (untrusted model, least privilege)
        |
        +--> isolated Security reviewer --------+
        +--> isolated Architecture reviewer ----+--> triage/repair loop
        +--> conditional specialist reviewers --+
        |
        v
Trusted verifier + artifact promoter
        |
        +--> target A3: validated PR, human merge
        +--> target A4: policy-controlled merge after earned promotion
        +--> target A5: separately restricted high-impact profiles
```

Trust rules:

1. Model output is untrusted data, including reviewer output.
2. Only deterministic controller code changes run state or applies artifacts.
3. Executors never receive a broad personal token or the host home directory.
4. Missing/invalid worker, review, test, or evidence output blocks the run.
5. Every loop is bounded and its counter persists outside model context.
6. Every terminal state has an auditable reason and immutable evidence references.

## Implementation Plan

### Step 1 — Containment
**Files:** legacy autonomous workflow, `claude-auto` skill/gates, session-start and hook-graduation paths.

**Work:** Before any other actuation work, disable the label-triggered skipped-permission/admin-merge path; retain only a human/manual diagnostic dispatch. Disable automatic policy self-graduation and quarantine its state mutation. Do not substitute a controller or lifecycle here.

**Accepts:** No reachable workflow combines skipped permissions, write/admin credentials, and autonomous merge; session start cannot edit hook policy/autonomy/graduation state; the legacy path is visibly disabled with a safe manual fallback.

### Step 2 — Truthful baseline
**Files:** `scripts/ai/atomic-status.sh`, `scripts/ai/validate-changeset.sh`, pipeline/changeset tests, setup, runtime checkers, `validate_skills.py`, `skill_reference_check.py`, and `ai/skills/manifest.csv`.

**Work:** Define and enforce the Bash execution contract, or remove associative arrays, for both `atomic-status.sh` and `validate-changeset.sh`; shipped lifecycle calls must work with inherited PATH on macOS Bash 3.2. Preserve command rc/stderr in test diagnostics instead of JSON-decoding empty stdout. Make mandatory runtime/setup/CI checks fail closed. Reconcile all 30 enabled skills with the manifest before requiring `validate_skills.py` green. Scope the broad reference scan to runtime-delivered assets with an explicit allowlist, or label its historical/docs scan informational until a later cleanup gate.

**Accepts:** Full discovery passes on Bash 3.2 and Bash 5; staged and changeset failures retain rc/stderr; runtime checks fail closed; all 30 skills have a manifest disposition; historical/reference debt is never misreported as runtime-critical.

### Step 3 — Contract, trust root, evidence verifier, and client declaration
**Files:** intent/evidence schemas, `trust-root.toml`, `clients.toml`, autonomy/risk config, contract/evidence/client verifier scripts, and tests.

**Work:** Define intent fields for objective, requester, risk, base SHA, owned paths, sandbox profile, deterministic accepts, review route, data class, credential needs, and maximum action. Add a minimal evidence envelope/verifier (commit/case digests, provenance, schema version, freshness, attestation identity, verifier result) and a protected external trust anchor: an immutable policy source or verifying identity outside the agent-editable checkout. Signing material remains inaccessible to executors and the controller. Declare every client coordinator, executor, reviewer, or assist-only; undeclared capability fails closed. Exceptions only reduce scope/tier with independent human signature and expiry.

**Accepts:** Invalid intent/client/verifier, stale evidence, altered base, scope escape, or excess action is rejected before work; no agent-editable file raises autonomy; tests reject an altered trust root, immutable-policy reference, or issuer identity and prove signing material is unavailable to executor/controller; action-specific eval coverage is deferred to Step 8.

### Step 4 — Activation cleanup from a generated inventory
**Files:** skill registry/generator/drift checks, live client projections, hook config, diagnostics/removals, and generated hook-inventory artifact/check.

**Work:** Generate projections from an authoritative registry with `active`, `compatibility-shim`, `retired`, and `lab` states. Generate and validate an inventory assigning each of the 14 zero-static-reference hooks exactly one `runtime|manual|quarantine|retired` disposition, owner, and evidence. Seed the check with quarantine `doc-file-warning.sh`, `lean-ctx-redirect-native`, `lean-ctx-rewrite-native`, `notify-permission.sh`, `notify-stop.sh`, and `qmd-sync.sh`; manual `hook-integration-test.sh`, `stale-memory-check.sh`, and `test-hook.sh`; retired `drift-guard.sh`, `plan-naming-enforcer.js`, `plan-naming-enforcer.rs`, and `stack-enforce-prompt.sh`; and separately risk-review `monitor-cicd-build.sh` (retired/quarantine because it hard-codes another repository). Treat referenced no-op `lean-ctx-redirect.sh` separately. Quarantine paths non-actuating for at least 30 calendar days and 100 eligible sessions, require zero recorded use in the generated `hook-activation-ledger.jsonl`, and require the named hook owner to sign off before deletion. Move labs/manual diagnostics from live discovery and retain one LeanCtx observation per event.

**Accepts:** Registry covers every enabled skill; generated inventory/check covers all 14 hooks; quarantine cannot actuate and precedes deletion; each deletion records >=30 days, >=100 eligible sessions, zero use from `hook-activation-ledger.jsonl`, and named-owner sign-off; runtime hooks are registered, manual hooks non-runtime, retired items absent; disposable-HOME delivery and single-observation fixtures pass.

### Step 5 — Enforce sandbox and artifact boundary
**Files:** sandbox profiles/runner, artifact validator/promoter, executor/promote workflows, and tests.

**Work:** Use a non-privileged disposable container/VM: no host-home mount, Docker socket, or added capabilities; empty job permissions by default; egress deny through an allowlisted proxy; scoped ephemeral credentials; read-only inputs where possible. Workers emit only bounded patch/evidence; a trusted promoter validates a clean checkout before a PR.

**Accepts:** Negative tests reject secret/path/network/MCP abuse, credential reuse, privileged mounts, push/merge/policy mutation; promotion rejects symlinks, submodules, binaries, oversize patches, wrong-base changes, and out-of-scope paths; sandbox and teardown evidence is verifier-readable.

### Step 6 — Minimal controller/port seam
**Files:** controller/ports/events, `scripts/ai/git_lifecycle.py`, lifecycle adapter, client adapters, native orchestrator, and tests.

**Work:** Keep `scripts/ai/git_lifecycle.py` as the sole persisted-run/lifecycle authority. Add only a small seam for contract validation, lifecycle invocation, sandbox/review/eval selection, and terminal evidence; do not create a second lifecycle engine or persisted state machine. Clients are thin adapters. Replace source-shape tests with executable failure/retry/idempotency/recovery tests. Emit versioned redacted events for identity, state, policy decision, and outcome—never prompt, secret, or source text.

**Accepts:** Lifecycle-owned start/inspect/resume/cancel/audit works without chat history; invalid/null worker/reviewer blocks or uses persisted retry; stale/crash/duplicate cases are auditable; adapters have no business policy; event redaction tests pass.

### Step 7 — Risk-routed independent review
**Files:** review profiles, lensed-review configuration/references, review schema/port, and tests.

**Work:** Route lenses from risk, changed surfaces, data class, and dependency changes. Fresh reviewers see only artifact plus contract. Security and Architecture are independent when required by the route, not blanket requirements for low-risk docs/test pilots. Findings/dispositions and bounded repair are fail closed.

**Accepts:** Missing/malformed/timed-out required review blocks; required reviewers are independent; high findings block; tests prove low-risk routes omit irrelevant lenses and high-risk routes require each declared lens.

### Step 8 — Eval coverage and signed attestation
**Files:** eval runner/schema/cases/fixtures/reports/workflow, autonomy resolver, and tests.

**Work:** Add success, refusal, failure, pressure, and adversarial coverage for every action, including injection, missing acceptance, scope error, MCP/reviewer outage, stale evidence, secret access, and unauthorized merge. Sign/attest reports using a Step-3 trust-root issuer and verify commit/case digests. Behavioral/sensitivity results—not lint/routing scores—are promotion inputs.

**Accepts:** Every action is covered; invalid/stale/foreign/incomplete/threshold-failing reports reject; CI blocks regression; red/absent evidence has no effect; safety failures demote immediately.

### Step 9 — Privacy-safe telemetry aggregation
**Files:** metric aggregator, weekly wrapper, SLO config, and tests.

**Work:** Aggregate only redacted Step-6 evidence into repository-parameterized outcomes. Enforce retention/access/aggregation rules that prohibit prompt, secret, and source payloads. Metrics inform promotion but cannot override the verifier.

**Accepts:** Aggregation rejects sensitive payloads and unknown versions; dashboards measure intervention, time-to-PR, cost, violations, review escape, rollback, and utilization; missing telemetry blocks promotion but not assist-only use.

### Step 10 — A3-candidate pilots
**Files:** pilot config, intake/executor/promote workflows, retained reports, and metrics.

**Work:** Run low-risk documentation, test-only, dependency-patch, and mechanical-refactor **A3-candidate pilots**. The system may open a verified PR; human merge is mandatory. Start with one proven client; admit a second only after identical contract, lifecycle, review, and fail-closed conformance fixtures pass for both clients. Pre-register run denominators, matched control/cohort selection, a 30-day minimum post-PR observation window, and authoritative sources: signed CI gate reports for gate pass, the change/incident ledger for rollback, and the independent-review plus incident ledger for escaped-high findings. All first autonomous runs remain A3-candidate until independent human governance approves signed evidence and observed outcomes.

**Accepts:** At least 50 A3-candidate runs across three repositories with one proven client, or two clients only after the cross-client fixtures pass; pilot protocol pre-registers eligible-run denominator, matched control, 30-day post-PR window, and the named gate/rollback/escaped-high detection sources; zero unauthorized writes/secrets/merges/policy mutations/sandbox escapes; 95% gate pass, 100% routed review, below-2% rollback/escaped-high rate, and 30% median intervention improvement versus control; all failures have classified terminal reasons. A4/A5 and delivery-cell scaling remain out of scope.

## Horizon Mapping

| Target horizon | Plan exit gate |
|---|---|
| H0 baseline/pilots | Steps 1-3 complete; containment, truthful baseline, and trust-root contract |
| H1 standardize | Step 4 complete; activation registry and explicit client delivery |
| H2 bounded harness | Steps 5-9 complete; sandbox, lifecycle seam, review, attested evals, telemetry |
| H3 delivery cells | Explicitly deferred pending independently approved A3-candidate evidence |
| H4 enterprise default | Explicitly deferred; not authorized by this plan |

## Stop/Go Gates

- **Stop immediately:** any admin bypass, control-plane self-edit, missing required review, sandbox escape,
  unauthorized path/network/secret access, stale evidence acceptance, or ambiguous terminal state.
- **Do not start Step N+1** until Step N's `Accepts` statements have reproducible evidence.
- **Do not promote autonomy** because the implementation exists. Promotion requires green eval evidence,
  required observed sample size, SLO compliance, and human approval.
- **Prefer deletion over compatibility** only after usage telemetry proves the old path unused; until then,
  keep a thin shim that cannot exceed the new path's permissions.

## Verification Commands Used for This Baseline

These commands were run from the isolated worktree; outputs were not inferred from prior docs/plans.

```text
bash ./setup.sh --check
python3 scripts/config_doctor.py --summary
python3 scripts/config_inventory.py --summary
python3 scripts/guidance_adapter_check.py --summary
python3 scripts/mcp_topology_check.py --summary
python3 scripts/hook_config_check.py ai/config/claude/settings.base.json --summary
python3 scripts/hook_output_schema_check.py .claude/hooks --summary
python3 scripts/self_modification_check.py --summary
python3 scripts/validate_skills.py
python3 scripts/run_evals.py --summary
python3 -m unittest -v scripts.test_orchestrate_workflow
python3 -m unittest discover -s scripts
bash scripts/ai/autonomy-tier.sh --stage auto_stack --json
bash scripts/ai/autonomy-tier.sh --stage auto_commit --json
bash scripts/ai/autonomy-tier.sh --stage auto_push --json
bash scripts/ai/autonomy-tier.sh --stage auto_pr --json
bash scripts/ai/autonomy-tier.sh --stage auto_ship --json
bash scripts/ai/autonomy-tier.sh --stage auto_clean --json
lean-ctx tools health
```

## Checked / Not Yet Checked

**Checked:** target requirements; executable activation paths; config/MCP/guidance checks; hook fixtures and
configuration; skill registry and live delivery; autonomy resolution; orchestration source and static tests;
full script test discovery; sandbox indicators; CI workflow permissions/gates; eval inventory; token/tool
health; runtime symlinks.

**Not yet checked:** a paid Tier-3/Tier-4 behavioral eval run; a live non-dry-run native workflow; an actual
factory PR/CI/human-approval trace; sandbox escape tests; GitHub branch-protection configuration; Cursor and
Gemini live loader precedence; enterprise repository pilots. The plan forbids maturity or autonomy promotion
until these are checked through Steps 5-10.

## Approval Required Before Implementation

Human approval is required for this sequence and specifically for: disabling the legacy autonomous workflow,
removing automatic hook graduation, replacing the autonomy vocabulary, deleting compatibility surfaces,
and selecting the first pilot repositories. No implementation has begun.
