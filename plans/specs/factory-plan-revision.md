# Frozen Spec: Agent Factory Gap Plan Revision

## Objective

Revise `plans/2026-08-03-agent-factory-gap-plan.md` so its implementation sequence is safe, evidence-backed, and executable after the architecture and evidence reviews.

## Evidence boundary

- Use `/Users/axos-agallentes/git/agent-harness/docs/The_Agent_Factory.md` only as the target state.
- Do not use existing repository `docs/`, `decisions/`, `goals/`, or prior `plans/` as evidence of current harness behavior.
- Current-state claims may rely only on executable source, operational prompt/config assets, tests/evals, generated artifacts, live wiring, and observed command behavior already cited in the draft or reviewer findings.

## Required corrections

1. Reorder delivery as: containment; truthful baseline; contract/trust root/client declaration; activation cleanup; enforceable sandbox and artifact boundary; minimal controller seam; risk-routed review; eval coverage and signed attestation; privacy-safe telemetry aggregation; A3-candidate pilots.
2. Keep `scripts/ai/git_lifecycle.py` as the sole persisted-run/lifecycle authority. Add only a small controller/port seam; do not design a second lifecycle engine.
3. Split containment from baseline repair. Containment must disable the admin merge/skipped-permission path and automatic policy self-graduation before other actuation work.
4. Make the baseline truthful without pretending all historical/reference debt is runtime-critical:
   - explicitly fix the Bash 3.2 staged-change failure;
   - make mandatory runtime checks fail closed;
   - address the 30-entry enabled-skill manifest mismatch before requiring `validate_skills.py` green;
   - either scope `skill_reference_check.py` to runtime-delivered assets with an explicit allowlist, or keep its broad historical/docs scan informational until a later cleanup gate.
5. Rename the 16-criterion score to an **author-defined readiness rubric**, retain correct 11/32 arithmetic, and add target-section mapping plus weight rationale. Never imply the target document defines that rubric.
6. Add an early minimal evidence schema, verifier, and trust-root declaration; action-specific eval coverage comes later.
7. Put sandbox/artifact isolation before any actuating controller. Specify a non-privileged container/VM, no Docker socket or added capabilities, egress policy/proxy, empty job permissions, and scoped ephemeral credentials.
8. Require artifact promotion to reject symlinks, submodules, binaries, oversize patches, wrong-base changes, and out-of-scope paths.
9. Establish privacy-safe, redacted event evidence when the controller is introduced; defer dashboard aggregation to the telemetry step.
10. Add an explicit inventory artifact for the 14 zero-static-reference hooks, with `runtime|manual|quarantine|retired` disposition. Quarantine compatibility paths before deletion and require a measured observation window.
11. Route Architecture/Security review according to declared risk; do not require both for every low-risk docs/test pilot.
12. Call all first autonomous runs **A3-candidate pilots** until promotion evidence is independently approved.
13. Defer A4/A5 production implementation to conditional roadmap gates because it conflicts with the human-merge invariant and needs separate human-approved policy/trusted merge-service design. Do not list speculative production files for A4/A5.
14. Preserve the session-artifacts format: every numbered implementation step must include concrete `**Files:**` and measurable `**Accepts:**`, and Step N+1 cannot begin before Step N acceptance.
15. The trust root must be external/protected rather than agent-editable checkout state: declare the verifying identity or immutable policy source, keep signing material inaccessible to executor/controller, and require negative tests for altered root, policy, and issuer.
16. Make compatibility quarantine deletion measurable: a minimum observation duration and run count, zero-use threshold from a named telemetry source, and owner sign-off; quarantined paths remain non-actuating until that gate passes.
17. Before a second client may join an A3-candidate pilot, require cross-client conformance fixtures for the same contract, lifecycle, review, and fail-closed behaviors; otherwise pilot with one proven client.
18. Pre-register pilot metric denominators, cohort/control matching, minimum post-PR observation window, and authoritative sources for gate pass, rollback, and escaped-high-finding detection.

## Known confirmed evidence to preserve

- Maturity verdict: Level 2 with experimental Level-3 components.
- Bash 3.2 breaks two shipped runtime paths: three `test_pipeline_status` failures at associative-array use in `scripts/ai/atomic-status.sh`, plus all ten `test_validate_changeset` cases crashing at `scripts/ai/validate-changeset.sh:58`. The latter ten share one product portability failure; their helper amplifies it by discarding nonzero status/stderr and JSON-decoding empty stdout. A Bash-5-first PATH makes all ten pass, while the production lifecycle inherits the failing PATH.
- Mandatory checker failures: hook config 14; self-modification 2; enabled skills absent from manifest 30; broad skill reference scan 101.
- Native orchestrator: invalid-worker/reviewer fail-open behavior, no patch-apply stage, and 37 primarily source-shape tests completing in roughly 0.004 seconds.
- Legacy remote path: skipped permissions, admin token/admin merge, and incomplete CI gate set.
- Promotion evidence: no tracked `evals/reports/`; tier-2 routing 81.82%; behavioral/sensitivity cases are not automated promotion gates.
- Strong foundations: guidance 28/28, topology 34/34, portable bases 6/6, pre-tool fixtures 7/7, config-generation tests 45 passing, plus exact-SHA/owned-path/journal/lock/idempotency/demotion lifecycle primitives.

## Output and verification

- Edit only `plans/2026-08-03-agent-factory-gap-plan.md`.
- Return a compact summary of changes and the exact validation commands/results.
- Verify step count equals `**Files:**` count equals `**Accepts:**` count.
- Verify no `TODO`, `TBD`, placeholder, or unsupported target-defined-score wording remains.
- Do not implement harness changes, commit, push, or create a PR.
- Do not spawn subagents.
