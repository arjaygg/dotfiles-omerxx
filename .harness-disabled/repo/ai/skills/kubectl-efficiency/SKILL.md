---
name: kubectl-efficiency
description: Minimal-token kubectl command patterns — field extraction, log bounding, field-selector filtering, watch over polling. Use when writing or reviewing kubectl commands.
version: 1.0.0
disable-model-invocation: true
triggers:
  - kubectl-efficiency
  - efficient kubectl
  - minimize kubectl output
---

# Skill: kubectl-efficiency

These rules apply whenever an agent primitive (skill, command, rule) writes or recommends kubectl commands.
The goal is minimal token output — return only the data needed, nothing more.

## Decision Tree

Before writing any kubectl command, choose the least-verbose path:

```
Need one field?         → kubectl get <r> -o jsonpath='{.field}'
Need a table view?      → kubectl get <r> -o custom-columns=NAME:.metadata.name,... --no-headers
Need filter/transform?  → kubectl get <r> -o json | jq 'select(...) | .field'
Need recent logs?       → kubectl logs --tail=N --since=Xh [-l selector]
Need multi-pod logs?    → stern <regex> --since=Xh --tail=N
Need to track changes?  → kubectl get <r> --watch  (never poll in a loop)
Need to preview change? → kubectl diff -f manifest.yaml
```

## Required Patterns

**Logs — always bound the output:**
```bash
kubectl logs my-pod --tail=100 --since=1h
kubectl logs -l app=nginx --tail=50 --since=30m
kubectl logs -f deploy/my-app --since=5m 2>/dev/null | grep --line-buffered "ERROR"
```

**Field extraction — jsonpath over full dump:**
```bash
# Good
kubectl get pod my-pod -o jsonpath='{.spec.nodeName}'
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\n"}{end}'

# Bad — dumps full YAML for a single field
kubectl get pod my-pod -o yaml | grep nodeName
```

**Job/pod status — server-side field selectors over grep:**
```bash
# Good — server-side filter, minimal response
kubectl get jobs -n auc-conversion --field-selector=status.active=1 -o name
kubectl get pods --field-selector status.phase=Running

# Bad — fetches all, pipes to grep client-side
kubectl get jobs -n auc-conversion | grep -E "(Running|Pending)"
```

**Watching — one connection over polling:**
```bash
# Good — single stream connection
kubectl get pods --watch -l app=nginx
kubectl wait --for=condition=Ready pod -l app=nginx --timeout=120s

# Bad — repeated API calls, misses events between cycles
while true; do kubectl get pods; sleep 5; done
```

**Kustomize apply — direct flag over pipe:**
```bash
# Good
kubectl apply -k overlays/qa/

# Bad
kubectl kustomize overlays/qa/ | kubectl apply -f -
```

**Env var lookup — exact variable over piped grep:**
```bash
# Good — returns exactly one value
kubectl exec deployment/my-app -- printenv MY_VAR

# Bad — dumps all env vars, pipes to grep
kubectl exec deployment/my-app -- env | grep MY_VAR
```

## Forbidden Anti-Patterns

- `kubectl logs <pod>` with no `--tail` or `--since` — can return gigabytes
- `kubectl get -o yaml` or `-o json` (raw dump) when only one field is needed
- `kubectl get <resource> | grep` for status/phase checks — use `--field-selector`
- Polling loops with kubectl inside — use `--watch` or `kubectl wait --for=condition=`
- `kubectl describe pod` when `kubectl get pod -o jsonpath=...` answers the question

## Allowed Exceptions

- `-o yaml` is acceptable when piping into another `kubectl apply -f -` (schema transforms)
- `kubectl describe` is acceptable for human-readable diagnostic output (not in scripts)
- Full log dumps acceptable only when explicitly requested by the user for forensic analysis

## Reference

Full best practices with examples: `docs/research/2026-06-01-kubectl-efficiency-best-practices.md` in `auc-discovery`.
