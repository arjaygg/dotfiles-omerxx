---
name: auc-manifest-review
description: >
  Expert K8s DevOps Agent for auc-deployment-manifest. Use this whenever reviewing open PRs in
  axos-financial/auc-deployment-manifest, auditing Kustomize overlays across dev/qa/stg/uat/prd,
  comparing manifests for environment parity, or posting structured review findings to PRs.
  Automatically invoked when user asks to "review manifest PRs", "check manifest parity",
  "audit k8s overlays", or "review deployment manifest".
version: 1.0.0
triggers:
  - review manifest
  - manifest pr review
  - k8s overlay audit
  - auc manifest
  - deployment manifest review
  - check manifest parity
---

# AUC Manifest Review Agent

Expert K8s DevOps Agent that reviews open PRs in `axos-financial/auc-deployment-manifest`,
performs deep cross-environment analysis, and posts structured findings to each PR.

## When to Use

- Reviewing open PRs in auc-deployment-manifest for correctness, completeness, relevance, and effectivity
- Auditing Kustomize overlays across environments (dev / qa / stg / uat / prd)
- Detecting environment parity gaps, label selector mismatches, secret handling issues
- Posting structured review findings with resolution plans to GitHub PRs

## Instructions

When this skill is invoked, spawn a **background agent** using the Agent tool with `run_in_background: true`.

The agent must:

### 1. Enumerate Open PRs

```bash
gh pr list --repo axos-financial/auc-deployment-manifest --state open \
  --json number,title,headRefName,author,createdAt,files
```

### 2. For Each Open PR

```bash
gh pr view <N> --repo axos-financial/auc-deployment-manifest --json title,body,files
gh pr diff <N> --repo axos-financial/auc-deployment-manifest
```

Fetch the current state of ALL overlay files for cross-env comparison:
- `auc-conversion/base/` — base manifests (all envs inherit)
- `auc-conversion/overlays/{dev,qa,stg,uat,prd}/` — per-env patches

### 3. Review Each PR

Check all four dimensions:

**Correctness**
- Label selectors in Deployments, Services, PDBs, and configmap WORKER_LABEL_SELECTOR env vars must be internally consistent
- Image tags must follow `v1.X.Y` semver format (not `latest`)
- Secret references (`secretKeyRef`) must name existing Secrets in the same namespace
- Security contexts: `runAsNonRoot`, `readOnlyRootFilesystem`, `capabilities: drop: [ALL]` present in prd
- Probes (`livenessProbe`, `readinessProbe`) must be present for prd deployments
- `stringData` in Secret manifests must not contain real credentials (flag `REPLACE_WITH_*` placeholders as incomplete)

**Relevance**
- Changes must be scoped to the PR's stated purpose (title + description)
- Flag unrelated changes included in the PR
- Check if the PR supersedes or conflicts with another open PR

**Completeness**
- If a change is made to prd overlay, check whether qa/stg/uat need the same change
- If an env var is added to worker in one overlay, check other overlays for parity gap
- If a base file is changed, verify the change doesn't break non-prd overlays

**Effectivity**
- Resource requests/limits appropriate for environment tier (see table below)
- HPA settings: prd should have `minReplicas ≥ 2`; dev/qa can be lower
- PDB `minAvailable` should protect ≥ 70% of prd workers
- Image tag must be bumped consistently (api + worker + scheduler all at same version in prd/qa)

### 4. Environment Tier Expectations

| Setting | dev | qa | stg | uat | prd |
|---------|-----|----|-----|-----|-----|
| Worker minReplicas | 1 | 1–5 | 2 | 2 | 2+ |
| Image tag | pipeline-set | pipeline-set | semver | semver | semver, no `latest` |
| PDB | optional | optional | recommended | recommended | required |
| Probes | optional | required | required | required | required |
| Security context | optional | optional | recommended | recommended | required |
| Secrets in manifests | placeholder OK | placeholder OK | sealed/injected | sealed/injected | sealed/injected |
| `readOnlyRootFilesystem` | — | — | — | — | required |

### 5. Cross-Environment Parity Report

Build a comparison table for each key setting changed in the PR:

| Setting | base | dev | qa | stg | uat | prd | Status |
|---------|------|-----|----|-----|-----|-----|--------|
| WORKER_LABEL_SELECTOR | — | ... | ... | ... | ... | ... | ✅/⚠️/❌ |
| minReplicas | ... | ... | ... | ... | ... | ... | ✅/⚠️/❌ |
| image tag | ... | ... | ... | ... | ... | ... | ✅/⚠️/❌ |

### 6. Compose Review Body

Format findings as:

```markdown
## K8s DevOps Review — PR #<N>: <title>

### Purpose Assessment
<1-2 sentences: does the PR accomplish what it claims?>

### Findings

| # | Severity | File | Finding | Resolution |
|---|----------|------|---------|------------|
| 1 | CRITICAL/HIGH/MEDIUM/LOW | `path/to/file.yaml` | Description | Fix X |

### Environment Parity

| Setting | dev | qa | stg | uat | prd |
|---------|-----|----|-----|-----|-----|
| ... | ... | ... | ... | ... | ... |

### Cross-PR Conflicts
<List any conflicts with other open PRs — overlapping files, conflicting values>

### Resolution Plan
1. [ ] Action item with owner suggestion
2. [ ] ...

### Verdict
**APPROVE** / **REQUEST_CHANGES** / **COMMENT**
> Reason in one sentence.

---
*Reviewed by auc-manifest-review agent | axos-financial/auc-deployment-manifest*
```

### 7. Post the Review

```bash
# For APPROVE:
gh pr review <N> --repo axos-financial/auc-deployment-manifest --approve \
  --body "<findings markdown>"

# For REQUEST_CHANGES:
gh pr review <N> --repo axos-financial/auc-deployment-manifest --request-changes \
  --body "<findings markdown>"

# For COMMENT only:
gh pr review <N> --repo axos-financial/auc-deployment-manifest --comment \
  --body "<findings markdown>"
```

## Severity Definitions

| Level | Meaning |
|-------|---------|
| CRITICAL | Security secret in plaintext, broken label selector, wrong namespace, manifest won't apply |
| HIGH | Missing probe in prd, HPA misconfigured, `latest` tag in prd, missing PDB in prd |
| MEDIUM | Environment parity gap, resource imbalance, stale ADR reference |
| LOW | Naming inconsistency, cosmetic YAML style, missing comment |

## Repo Context

- **Repo:** `axos-financial/auc-deployment-manifest`
- **Structure:** Kustomize — `<service>/base/` + `<service>/overlays/{dev,qa,stg,uat,prd}/`
- **Services:** `auc-conversion`, `auc-conversion-secret`, `outsystemscc`, `auc-api`, `auc-ui`, etc.
- **Components:** conversion-api, conversion-scheduler, conversion-worker
- **Secret handling:** `*-secret.yaml` files per overlay; values must be sealed/injected — NEVER plaintext
- **Pipeline:** image tags are bumped via `kustomize edit set image` in CI; `latest` is forbidden in prd

## Related Skills

- `bmad-custom-pr-review` — general PR code review (non-manifest)
- `hawk` — adversarial Go code reviewer for auc-conversion ETL
- `auc-qa` — QA agent for test-first development in auc-conversion
