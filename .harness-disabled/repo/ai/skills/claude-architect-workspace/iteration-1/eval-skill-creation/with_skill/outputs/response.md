# Skill Creation: k8s-security-audit

## Clarifications (Trigger Conditions & Output Format)

**Trigger conditions:** The skill fires when a user asks to audit, scan, or review Kubernetes manifest YAML files for security issues — specifically mentioning misconfigurations, privileged containers, runAsNonRoot, resource limits, pod security contexts, or general "k8s security" concerns.

**Output format:** A structured Markdown findings report with:
- Summary table (severity counts)
- Per-finding blocks (severity, file, resource, container, issue description, remediation)
- List of clean files
- Remediation priority order
- Optional: patch snippets for each finding

---

## Existing Skills Check

Searched `~/.dotfiles/ai/skills/*/SKILL.md` and `~/.claude/skills/*/SKILL.md` — no existing similar skills found. Proceeding with creation.

---

## SKILL.md Written

**Path:** `~/.dotfiles/ai/skills/k8s-security-audit/SKILL.md`

The skill covers three checks:
1. **[CRITICAL]** Privileged containers (`securityContext.privileged: true`)
2. **[HIGH]** Missing `runAsNonRoot` at pod or container security context
3. **[MEDIUM]** Missing `resources.limits.cpu` or `resources.limits.memory`

---

## Symlink Command

Run this to make the skill available in Claude Code:

```bash
ln -sf ~/.dotfiles/ai/skills/k8s-security-audit ~/.claude/skills/k8s-security-audit
```

After running this, the skill will be auto-invoked whenever a user asks to audit Kubernetes manifests for security issues.

---

## File Created

```
~/.dotfiles/ai/skills/k8s-security-audit/SKILL.md
```

(In this eval, the file was written to the outputs directory at the path specified by the evaluator.)
