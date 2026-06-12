# Playbook: stale-pods

Drain and restart conversion worker pods that have stopped processing due to stuck goroutines,
OOM conditions, or lost DB connections. Pods remain in Running state but are unresponsive.

## Preconditions

- [ ] Worker pods show `Running` status but chunk processing rate is 0 for >5 minutes
- [ ] Liveness probe NOT failing (else Kubernetes would already restart)
- [ ] No active circuit breaker (`kubectl get cm conversion-circuit-breaker -n auc -o jsonpath='{.data.state}'` → `closed`)

## Steps

```bash
# 1. Identify stale pods
kubectl get pods -n auc -l app=conversion-worker -o wide

# 2. Check last-processed timestamp from each pod's metrics endpoint
for pod in $(kubectl get pods -n auc -l app=conversion-worker -o name); do
  echo "=== $pod ==="
  kubectl exec -n auc "$pod" -- wget -qO- http://localhost:9090/metrics 2>/dev/null \
    | grep -E "last_chunk_processed|chunks_processed_total" || echo "(no metrics)"
done

# 3. Rolling restart — Kubernetes replaces one pod at a time
kubectl rollout restart deployment/conversion-worker -n auc

# 4. Wait for rollout to complete
kubectl rollout status deployment/conversion-worker -n auc --timeout=180s
```

## Verification

- `kubectl get pods -n auc -l app=conversion-worker` — all pods `Running` with recent age
- Chunk processing rate resumes: check metrics or log `chunks processed` entries
- No `OOMKilled` in `kubectl describe pods -n auc -l app=conversion-worker`

## Rollback

Rolling restart is safe — if new pods fail to start, Kubernetes keeps old pods running.
Force scale down/up only if rollout is stuck:
```bash
kubectl scale deployment conversion-worker -n auc --replicas=0
sleep 10
kubectl scale deployment conversion-worker -n auc --replicas=2
```
