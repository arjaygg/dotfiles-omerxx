# Vision Skill Benchmark — Iteration 1

Comparing `old_skill` (`ai/skills/vision-workspace/skill-snapshot/SKILL.md`, v3.0.0 — fixed 4-agent panel) against `with_skill` (`ai/skills/vision/SKILL.md`, v4.0.0 — adaptive routing) across the 8 evals in `ai/skills/vision/evals/evals.json`. Responses generated blind to `expected_output`; scored after the fact.

Verdict scale: **PASS** (matches expected behavior), **PARTIAL** (correct technical conclusion, but process/format deviates from expected), **FAIL** (violates an explicit constraint in `expected_output`).

## 1. narrow-cache-regression

Expected: concise inline or single-build-lens diagnosis, correct path fix, no unrelated workstreams.

- **old_skill — PARTIAL.** Found the correct `~/go/pkg/mod` fix, but still launched all 4 panel agents (Deploy/Security/Observability report "no findings") and closed with structured JSON. Right answer, disproportionate process.
- **with_skill — PASS.** Handled fully inline, correct fix, explicitly states no other lens is warranted.

## 2. single-iam-risk

Expected: inline or single security specialist, focused on PassRole scoping, no build/deploy/observability workstreams.

- **old_skill — PARTIAL.** Correct HIGH-severity PassRole finding via advisor-gated Security agent, but Build/Deploy/Observability were still launched (no findings) as standing panel members.
- **with_skill — PASS.** Single security-lens inline analysis, correct finding, no other workstreams launched.

## 3. broad-regulated-k8s-design

Expected: proportionate multi-domain design covering supply chain, deployment, platform, observability, governance, and migration safety, without assuming a fixed panel.

- **old_skill — PARTIAL.** The fixed Build/Deploy/Security/Observability panel happens to cover most needed lenses, but **omitted database-migration safety entirely** (no standing role owns it — the response's own closing note flags this gap) and used parallel-only execution with no staged dependency between deployment design and migration strategy.
- **with_skill — PASS.** Covers supply chain, deployment/canary, governance/policy, observability, and stages a migration-safety lens *after* the deployment/rollback mechanism is defined (expand/contract pattern reasoned from the canary rollback window) — matches "parallel workstreams and staged synthesis" exactly.

## 4. adaptive-imagepull-incident

Expected: evidence-led triage on registry identity/deploy config, adaptive expansion only if the stale-secret hypothesis is disconfirmed.

- **old_skill — PARTIAL.** Reaches the same stale-imagePullSecret hypothesis with equivalent supporting evidence, but via the fixed panel (Build launched and explicitly returns nothing) rather than conditional expansion — there is no expansion mechanism, just fixed structure.
- **with_skill — PASS.** Begins narrow, gives an explicit ordered verification sequence, and only expands to a network/registry specialist *conditionally*, if verification disconfirms the leading hypothesis — matches "adaptive expansion" precisely.

## 5. constrained-runtime-format

Expected: five-bullet inline analysis, no fixed panel, no JSON, safer timeout recommendation.

- **old_skill — FAIL.** Directly violates the explicit "no JSON" instruction — produces a JSON status block (citing its own "Success Criteria requiring structured JSON output" as override) in addition to a bullet summary, and still runs the TodoWrite/4-agent scaffold (simulated inline) in a runtime that has no subagent capability. This is the clearest constraint violation in the set.
- **with_skill — PASS.** Exactly five bullets, no JSON, no panel, correct timeout diagnosis and recommendation.

## 6. dynamic-descope

Expected: explicit de-scoping of irrelevant workstreams with recorded rationale, correct 90-vs-14-day violation and fix.

- **old_skill — FAIL** (on the behavior actually being tested). Explicitly states the panel composition is fixed regardless of the user's narrowed request — no de-scoping occurs; Build and Security still run full standing checklists. The retention-days fix itself is correctly identified, but the eval targets de-scoping behavior specifically, which is structurally absent.
- **with_skill — PASS.** Produces an explicit de-scoping record (repository evidence + user narrowing, both cited) alongside the correct fix.

## 7. tool-capability-portability

Expected: capability-based analysis with no hardcoded tool dependency, transient-network hypothesis, bounded retry + verification proposal.

- **old_skill — PARTIAL.** Reaches the correct ECONNRESET/transient-network hypothesis and a reasonable retry recommendation, but frames the whole response around the fixed panel/JSON contract regardless of the runtime's actual exposed capabilities (`repo_search`/`file_read`/`ci_history` only) — the process isn't capability-derived, just narrated as "simulated inline."
- **with_skill — PASS.** Explicitly scopes the analysis to the three available capabilities, uses `ci_history` as the verification mechanism for a before/after check, and proposes retry as the proportionate next step without assuming unavailable tooling.

## 8. output-adaptation-executive

Expected: exact-format decision memo, ≤250 words, no JSON, conditional recommendation, explicit unknowns.

- **old_skill — FAIL.** Violates the explicit format constraints — emits the full TodoWrite/4-agent trace plus a JSON findings block *before* the requested memo, making the total response far over 250 words and directly contradicting "no JSON." The eventual four headings are present but buried under non-conforming scaffolding.
- **with_skill — PASS.** Exact four headings, ~230 words, no JSON, conditional migrate-only-if-verified recommendation, and explicit unknowns (no capability matrix supplied) instead of fabricated platform claims.

## Summary

| Eval | old_skill | with_skill |
|---|---|---|
| narrow-cache-regression | PARTIAL | PASS |
| single-iam-risk | PARTIAL | PASS |
| broad-regulated-k8s-design | PARTIAL | PASS |
| adaptive-imagepull-incident | PARTIAL | PASS |
| constrained-runtime-format | FAIL | PASS |
| dynamic-descope | FAIL | PASS |
| tool-capability-portability | PARTIAL | PASS |
| output-adaptation-executive | FAIL | PASS |

**with_skill (v4.0.0, adaptive)** passes all 8 evals. **old_skill (v3.0.0, fixed panel)** never outright fails on *technical correctness* — every root-cause/finding it reaches is accurate — but it fails or degrades on every eval that specifically tests **proportionality, de-scoping, or format/capability constraints**, which is exactly the design gap the adaptive skill was built to close:

- 3 outright **FAIL**s (constrained-runtime-format, dynamic-descope, output-adaptation-executive) all stem from the same root cause: old_skill's Success Criteria hardcode structured JSON output and a fixed 4-agent panel as non-negotiable, so it cannot honor explicit user-specified output formats or capability constraints, and cannot de-scope when a request narrows.
- 5 **PARTIAL**s reach correct conclusions but carry unnecessary coordination overhead (agents launched purely to report "no findings") or, in the broad design eval, silently drop a domain (migration safety) that doesn't map to any of the 4 fixed roles.
- with_skill's routing-by-decomposition approach (inline / single specialist / parallel / staged / adaptive expansion) matched the proportionate topology in all 8 cases, including correctly identifying when parallel-plus-staged was warranted (eval 3) versus when a single lens sufficed (evals 1, 2).
