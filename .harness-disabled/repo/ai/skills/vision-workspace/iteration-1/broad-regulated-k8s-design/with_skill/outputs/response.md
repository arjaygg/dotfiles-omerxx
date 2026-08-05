**Conclusion:** This is a broad, high-risk design task spanning supply-chain security, deployment safety, platform/policy enforcement, observability, and data-migration safety — proportionate to launch several parallel specialists now, then a staged synthesis pass once their outputs can be cross-checked against each other, plus one governance/compliance lens that depends on what the others surface.

**Scope and approach:** Framed the decision as: *what architecture satisfies a regulated bank's audit and safety requirements for a GitHub Actions → EKS/Helm/PostgreSQL pipeline?* Given the risk profile (production banking workloads, regulatory audit exposure, irreversible-if-wrong deployment/rollback design), this warrants parallel specialists rather than inline reasoning or a single generalist pass — but only the lenses the requirements actually touch, not a fixed roster:

- **Supply-chain & build specialist** — dependency pinning, SAST, SBOM generation, image signing.
- **Deployment/platform specialist** — Helm promotion flow, canary rollout, auto rollback, staged environments.
- **Policy & governance specialist** — manual approval gates, auditable promotion trail, policy enforcement at the cluster level.
- **Observability specialist** — SLO gates feeding canary/rollback decisions.
- **Data-migration specialist**, staged after the deployment design, since safe migration sequencing depends on knowing the rollout/rollback mechanism first (a migration strategy that assumes instant rollback is wrong if rollback is actually canary-gated over minutes).

No build-vs-deploy-vs-security-vs-observability panel was assumed a priori — these five came directly from the eight requirements in the prompt; a narrower ask would have used fewer.

**Evidence-backed findings:**

1. **Supply chain (parallel):** Dependency pinning (actions and base images by digest, not tag) plus SAST (CodeQL/Semgrep) and SBOM generation (Syft/CycloneDX) are complementary controls — pinning stops drift, SAST/SBOM give the audit trail regulators expect. Image signing (cosign/Sigstore) is the binding step that ties a specific, scanned artifact to what actually deploys; without it, the SBOM is a claim about a build, not a guarantee about what's running.
2. **Deployment/platform (parallel):** Canary rollout (Argo Rollouts or Flagger) with SLO-driven automated analysis satisfies both "canary rollout" and "auto rollback" as one mechanism rather than two — auto rollback should be canary-analysis-triggered, not a separate bolt-on. Manual prod approval sits as a gate *before* canary starts, not instead of it; both are required, at different points in the pipeline.
3. **Policy & governance (parallel, cross-checked against #1):** An admission controller (Kyverno/OPA Gatekeeper) enforcing "only signed + attested images may run" is what makes signing (#1) actually binding at the cluster level rather than advisory. The auditable-promotion requirement needs an immutable record (approver identity, artifact digest, timestamp) independent of the CI logs, since CI logs are not the audit-of-record for a regulated environment.
4. **Observability (parallel):** SLOs must be defined per-service and wired directly into the canary analysis query (Prometheus/Datadog), not left to manual judgment during a rollout window — this is what makes #2's "auto rollback" actually automatic rather than alert-then-human-decides.
5. **Migration safety (staged after #2):** Because rollback here is canary/SLO-gated (potentially minutes, not instant), DB migrations must be backward-compatible with both the old and new application version for the duration of a canary window — expand/contract migration pattern, not a single-phase alter that only the new code can read.

**Prioritized actions:**
- Stand up signing + admission-control enforcement first (#1 + #3) — this is the control that makes every other safety property (canary, rollback, audit) trustworthy rather than assumed.
- Build the canary/SLO/rollback mechanism as one integrated system (#2 + #4), not separately.
- Adopt expand/contract migration pattern before any schema change ships through this pipeline (#5).
- Wire the immutable promotion audit log (#3) independent of CI/CD tool logs, since regulators typically require an audit-of-record outside the deploy tool itself.

**Assumptions / unresolved questions:** Assumed EKS admission-control tooling (Kyverno/Gatekeeper) is permissible in this environment — not confirmed. Assumed no existing pipeline exists to retrofit (greenfield design), consistent with the prompt providing no files. Open question: which specific compliance framework (SOX, PCI-DSS, etc.) governs the audit-trail retention requirements — this would affect log retention duration and evidence format but wasn't specified.
