# Skill: k8s-security-audit

## Trigger

Use this skill when the user asks to:
- Audit Kubernetes manifests for security issues
- Scan YAML files for misconfigurations
- Check k8s manifests for security best practices
- Find privileged containers, missing resource limits, or root-running containers

Trigger phrases: "audit k8s manifests", "scan kubernetes yaml", "check security", "find misconfigurations", "k8s security audit"

## Overview

Scans one or more Kubernetes manifest YAML files for common security misconfigurations and produces a structured findings report. Covers three categories:

1. **Root execution** — containers where `securityContext.runAsNonRoot` is not set to `true`
2. **Missing resource limits** — containers without `resources.limits.cpu` or `resources.limits.memory`
3. **Privileged containers** — containers where `securityContext.privileged: true`

## Instructions

### Step 1 — Locate manifest files

If the user provided explicit file paths, use those. Otherwise, search the working directory for YAML files that appear to be Kubernetes manifests:

```bash
# Find candidate files
find . -name "*.yaml" -o -name "*.yml" | xargs grep -l "kind:" 2>/dev/null
```

Or use Glob:
- Pattern: `**/*.{yaml,yml}`
- Then filter to files containing `kind:` and `apiVersion:`.

### Step 2 — Read each manifest

Use the Read tool to load each file. For large directories, batch reads using the pctx `execute_typescript` tool when available.

### Step 3 — Analyze each container spec

For every manifest, traverse all container definitions (`.spec.containers[]`, `.spec.initContainers[]`, `.spec.template.spec.containers[]`, etc.) and check:

#### Check A: runAsNonRoot not set

Flag the container if ALL of the following are true:
- `securityContext.runAsNonRoot` is absent OR `false` at the container level
- `securityContext.runAsNonRoot` is absent OR `false` at the pod spec level
- `securityContext.runAsUser` is absent OR `0` (both levels)

Severity: **HIGH**

#### Check B: Missing resource limits

Flag the container if:
- `resources.limits` is absent, OR
- `resources.limits.cpu` is absent, OR
- `resources.limits.memory` is absent

Severity: **MEDIUM**

#### Check C: Privileged container

Flag the container if:
- `securityContext.privileged: true` at the container level

Severity: **CRITICAL**

### Step 4 — Output the findings report

Produce the report in this exact format:

```
=== k8s-security-audit findings report ===
Scanned: <N> file(s)  |  <date>

[CRITICAL] Privileged containers
────────────────────────────────
  <file>  →  <resource kind>/<name>  →  container: <containerName>
  ...
  (none) if no findings

[HIGH] Containers that may run as root
────────────────────────────────────────
  <file>  →  <resource kind>/<name>  →  container: <containerName>
  ...
  (none) if no findings

[MEDIUM] Missing resource limits
──────────────────────────────────
  <file>  →  <resource kind>/<name>  →  container: <containerName>  →  missing: <cpu|memory|cpu,memory>
  ...
  (none) if no findings

Summary
───────
  Total findings : <N>
  CRITICAL       : <N>
  HIGH           : <N>
  MEDIUM         : <N>
```

### Step 5 — Offer remediation snippets

After the report, offer to show remediation examples for any finding category that has results. Example remediation snippets to use when asked:

#### runAsNonRoot fix
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
```

#### Resource limits fix
```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

#### Privileged fix
```yaml
securityContext:
  privileged: false
  # Use specific capabilities instead:
  capabilities:
    add: ["NET_ADMIN"]  # only if needed
    drop: ["ALL"]
```

## Notes

- Init containers are scanned with the same rules as regular containers.
- CronJob manifests nest containers under `.spec.jobTemplate.spec.template.spec.containers[]` — handle this path.
- If a file fails to parse as YAML, record it as a parse error in the report rather than silently skipping.
- Do not modify any files — this skill is read-only.
- When no findings exist in a category, print `(none)` rather than omitting the section.
