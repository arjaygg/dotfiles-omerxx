---
name: k8s-security-audit
description: >
  Scans Kubernetes manifest YAML files for common security misconfigurations. Use this skill
  whenever you need to audit k8s manifests, review Deployment/Pod/DaemonSet YAML for security
  issues, or want a findings report before applying manifests to a cluster — invoke proactively
  when manifests are added or modified.
version: 1.0.0
triggers:
  - audit kubernetes manifests
  - scan k8s yaml for security
  - check for privileged containers
  - find missing resource limits
  - runAsNonRoot check
  - kubernetes security review
  - k8s misconfiguration scan
  - audit deployment yaml
---

# k8s-security-audit

Scans Kubernetes manifest YAML files for common security misconfigurations and produces a
structured findings report.

## When to Use

- Before applying any new or modified Kubernetes manifests to a cluster
- During PR review when `.yaml`/`.yml` files under a k8s/manifests/deploy directory are touched
- When a security review of workload definitions is requested
- Proactively when Deployment, DaemonSet, StatefulSet, Job, or CronJob manifests are added

## Checks Performed

| ID  | Severity | Check |
|-----|----------|-------|
| S01 | HIGH     | Container runs as root — `securityContext.runAsNonRoot` not set to `true` |
| S02 | HIGH     | Privileged container — `securityContext.privileged: true` |
| S03 | MEDIUM   | Missing CPU resource limit — `resources.limits.cpu` not set |
| S04 | MEDIUM   | Missing memory resource limit — `resources.limits.memory` not set |
| S05 | LOW      | Missing CPU resource request — `resources.requests.cpu` not set |
| S06 | LOW      | Missing memory resource request — `resources.requests.memory` not set |

## Instructions

### Step 1 — Locate manifests

Find all YAML files in the target path (default: current working directory):

```bash
# From repo root or a specific directory
find . -name "*.yaml" -o -name "*.yml" | grep -v node_modules | grep -v .git
```

Or use Glob to locate files matching `**/*.yaml` and `**/*.yml`.

### Step 2 — Parse and check each file

For each manifest file that contains `kind: Deployment`, `kind: DaemonSet`, `kind: StatefulSet`,
`kind: Job`, `kind: CronJob`, or `kind: Pod`:

**S01 — runAsNonRoot:**
Look for `securityContext` in each container spec. Flag if:
- `securityContext` is absent, OR
- `securityContext.runAsNonRoot` is absent or set to `false`

**S02 — Privileged:**
Look for `securityContext.privileged: true` in any container spec. Flag if present.

**S03/S04 — Resource limits:**
Look for `resources.limits` in each container spec. Flag individually if `cpu` or `memory` key
is absent under `limits`.

**S05/S06 — Resource requests:**
Look for `resources.requests` in each container spec. Flag individually if `cpu` or `memory` key
is absent under `requests`.

### Step 3 — Emit findings report

Output the report in this format:

```
## k8s Security Audit Report
Generated: <date>
Scanned: <N> files, <M> containers

### Findings

| File | Kind | Name | Container | ID  | Severity | Finding |
|------|------|------|-----------|-----|----------|---------|
| path/to/file.yaml | Deployment | my-app | app | S01 | HIGH | runAsNonRoot not set |
| path/to/file.yaml | Deployment | my-app | app | S03 | MEDIUM | CPU limit missing |

### Summary
- HIGH:   <count>
- MEDIUM: <count>
- LOW:    <count>
- PASS:   <count> containers with no findings

### Remediation Snippets

For each HIGH finding, emit a minimal YAML snippet showing the fix:

**S01 — Set runAsNonRoot:**
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
```

**S02 — Remove privileged or use specific capabilities instead:**
```yaml
securityContext:
  privileged: false
  capabilities:
    drop: ["ALL"]
```

**S03/S04 — Add resource limits:**
```yaml
resources:
  limits:
    cpu: "500m"
    memory: "256Mi"
  requests:
    cpu: "100m"
    memory: "128Mi"
```
```

### Step 4 — Exit criteria

- All target files scanned
- Report table populated (empty table if no findings)
- Summary counts accurate
- Remediation snippets included for any HIGH findings

## Examples

**User:** "Audit the manifests in ./k8s/ for security issues"
**Action:** Glob `./k8s/**/*.yaml`, read each, apply checks S01–S06, emit report.

**User:** "Check this deployment.yaml before I apply it"
**Action:** Read the single file, apply all checks, emit report with findings or a clean pass.

**User:** "Review the PR — any security problems in the manifest changes?"
**Action:** Identify changed YAML files via git diff, read each, apply checks, emit report.

## Related Skills

- `bmad-custom-pr-review` — full adversarial PR review including non-security issues
- `explore` — codebase exploration to locate manifest directories
