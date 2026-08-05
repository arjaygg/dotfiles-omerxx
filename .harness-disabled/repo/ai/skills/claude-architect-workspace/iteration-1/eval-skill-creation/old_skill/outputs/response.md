# k8s-security-audit Skill — Creation Response

## What was created

A new skill definition at `SKILL.md` in this directory. The skill is named `k8s-security-audit` and instructs an AI coding agent to scan Kubernetes manifest YAML files for three categories of security misconfiguration.

## Skill design decisions

### Scope of checks

Three checks were included as specified in the task:

| ID | Severity | Check |
|----|----------|-------|
| A  | HIGH     | `securityContext.runAsNonRoot` not set to `true` (container or pod level) |
| B  | MEDIUM   | `resources.limits.cpu` or `resources.limits.memory` absent |
| C  | CRITICAL | `securityContext.privileged: true` |

Privileged containers rank CRITICAL because they grant nearly full host kernel access. Root execution is HIGH because it widens the blast radius of a container escape. Missing resource limits are MEDIUM because they enable noisy-neighbour DoS but do not directly enable privilege escalation.

### Coverage of container paths

The skill accounts for all standard YAML paths where containers appear:
- `spec.containers[]` (Pod, Deployment, StatefulSet, DaemonSet, Job)
- `spec.initContainers[]`
- `spec.template.spec.containers[]` (controller wrappers)
- `spec.jobTemplate.spec.template.spec.containers[]` (CronJob)

### Output format

The report uses a fixed section-per-severity layout so findings are always visible even when a category has zero results. The `(none)` sentinel prevents false confidence from a silently empty section.

### Remediation offer

Rather than embedding remediation inline (which adds noise when there are many findings), the skill instructs the agent to offer remediation snippets after the report. This keeps the primary output focused on findings.

### Read-only constraint

The skill explicitly prohibits file modification. Security audits should never mutate the files they inspect — fixes belong in a separate workflow.

## How to use the skill

Place `SKILL.md` in the appropriate skills directory (e.g., `~/.dotfiles/ai/skills/k8s-security-audit/SKILL.md`) and ensure the skill loader picks it up. Then invoke it with:

```
/k8s-security-audit
```

or trigger it naturally:

```
audit the manifests in ./k8s/ for security issues
```

The agent will locate YAML files, scan each container spec, and emit the structured findings report.
