---
name: k8s-security-audit
description: >
  Scans Kubernetes manifest YAML files for common security misconfigurations including
  containers running as root (missing securityContext.runAsNonRoot), missing resource
  limits (requests/limits), and privileged containers. Outputs a structured findings
  report with severity, file, and remediation guidance. Use this whenever you need to
  audit Kubernetes manifests, review k8s security, check for privileged containers,
  find missing resource limits, validate pod security context, or run a k8s security scan.
version: 1.0.0
triggers:
  - audit kubernetes manifests
  - k8s security audit
  - scan k8s yaml
  - check kubernetes security
  - find privileged containers
  - missing resource limits kubernetes
  - check runAsNonRoot
  - kubernetes misconfiguration scan
  - pod security context audit
  - k8s security scan
---

# k8s-security-audit

## When to Use

Invoke this skill whenever:
- A user asks to audit, scan, or review Kubernetes manifest YAML files for security issues
- A user mentions "privileged containers", "runAsNonRoot", or "resource limits" in the context of Kubernetes
- A user asks to validate pod security contexts
- A PR or codebase contains Kubernetes manifests that need a security review
- A user asks "are my k8s manifests secure?" or similar

## Instructions

### Step 1 — Locate manifest files

Search the working directory (or a specified path) for Kubernetes manifest YAML files.

```bash
# Find all YAML files in k8s/, manifests/, deploy/, or helm/ directories
glob pattern: **/*.yaml or **/*.yml
filter: files containing 'kind:' (Deployment, DaemonSet, StatefulSet, Job, CronJob, Pod)
```

Focus on resource kinds that define containers:
- `Deployment`, `StatefulSet`, `DaemonSet`, `Job`, `CronJob`, `Pod`, `ReplicaSet`

### Step 2 — Run the three security checks

For each manifest file containing containers, check:

#### Check 1: runAsNonRoot (HIGH severity)
A container is flagged if **none** of the following are set to `true`:
- `spec.securityContext.runAsNonRoot: true`
- `spec.template.spec.securityContext.runAsNonRoot: true`
- `spec.containers[*].securityContext.runAsNonRoot: true`

If `runAsNonRoot` is absent or `false` at both pod and container level, flag it.

#### Check 2: Missing resource limits (MEDIUM severity)
A container is flagged if it is missing **either**:
- `resources.limits.cpu`
- `resources.limits.memory`

Also note if `resources.requests` are missing (INFORMATIONAL).

#### Check 3: Privileged containers (CRITICAL severity)
A container is flagged if:
- `securityContext.privileged: true`

at either the pod or container level.

### Step 3 — Produce the findings report

Output a structured report in this format:

```
# Kubernetes Security Audit Report

**Date:** <today>
**Scanned:** <N> manifest files
**Findings:** <total count>

---

## Summary

| Severity | Count |
|----------|-------|
| CRITICAL | N     |
| HIGH     | N     |
| MEDIUM   | N     |
| INFO     | N     |

---

## Findings

### [CRITICAL] Privileged Container
- **File:** `path/to/manifest.yaml`
- **Resource:** `<kind>/<name>`
- **Container:** `<container-name>`
- **Issue:** `securityContext.privileged: true` grants host-level capabilities.
- **Remediation:** Remove `privileged: true` or replace with specific capabilities via `securityContext.capabilities.add`.

### [HIGH] Container May Run as Root
- **File:** `path/to/manifest.yaml`
- **Resource:** `<kind>/<name>`
- **Container:** `<container-name>`
- **Issue:** `securityContext.runAsNonRoot` is not set. Container may run as UID 0.
- **Remediation:** Add `securityContext: runAsNonRoot: true` and set `runAsUser` to a non-zero UID.

### [MEDIUM] Missing Resource Limits
- **File:** `path/to/manifest.yaml`
- **Resource:** `<kind>/<name>`
- **Container:** `<container-name>`
- **Issue:** Missing `resources.limits.cpu` and/or `resources.limits.memory`. Risk of resource exhaustion.
- **Remediation:** Add `resources.limits` with appropriate cpu and memory values.

---

## Clean Files

The following files had no findings:
- `path/to/clean.yaml`

---

## Remediation Priority

1. Fix all CRITICAL findings immediately (privileged containers).
2. Address HIGH findings (root-capable containers) before next deploy.
3. Schedule MEDIUM fixes (resource limits) within current sprint.
```

### Step 4 — Offer remediation patches

After the report, offer to generate patch snippets for each finding. Example:

```yaml
# Remediation for [HIGH] runAsNonRoot in deployment/my-app
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
        - name: my-app
          resources:
            limits:
              cpu: "500m"
              memory: "256Mi"
            requests:
              cpu: "100m"
              memory: "128Mi"
```

## Examples

**User:** "Audit the manifests in ./k8s/ for security issues"
**Action:** Glob `./k8s/**/*.yaml`, run all three checks, output report.

**User:** "Are there any privileged containers in our deployment manifests?"
**Action:** Glob manifest files, run Check 3 only (privileged), report findings.

**User:** "Scan this file for k8s misconfigurations" (attaches a YAML)
**Action:** Read the provided file, run all three checks, output report.

**User:** "Check our helm charts for missing resource limits"
**Action:** Glob `**/templates/**/*.yaml`, run Check 2, report findings.

## Related Skills

- `bmad-custom-pr-review` — full adversarial PR review that can include security findings
- `explore` — codebase exploration to locate manifest files in unfamiliar repos
