# Playbook: circuit-breaker

Trip the circuit breaker on the conversion worker to stop processing new migration chunks
while an incident is being investigated. Safe to apply — no data loss.

## Preconditions

- [ ] `kubectl get deployment conversion-worker -n auc` shows at least 1 ready replica
- [ ] Active migration is confirmed stuck or producing errors (not just slow)
- [ ] Not already tripped: `kubectl get cm conversion-circuit-breaker -n auc -o jsonpath='{.data.state}'` → must not be `open`

## Steps

```bash
# 1. Set circuit breaker state to open
kubectl patch cm conversion-circuit-breaker -n auc \
  --type merge -p '{"data":{"state":"open","reason":"watchdog-auto","timestamp":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"}}'

# 2. Scale down worker to stop processing
kubectl scale deployment conversion-worker -n auc --replicas=0

# 3. Confirm
kubectl get deployment conversion-worker -n auc
```

## Verification

- `kubectl get deployment conversion-worker -n auc` → `READY 0/0`
- `kubectl get cm conversion-circuit-breaker -n auc -o jsonpath='{.data.state}'` → `open`
- No new chunk processing errors in logs for 60s

## Rollback

```bash
kubectl patch cm conversion-circuit-breaker -n auc \
  --type merge -p '{"data":{"state":"closed"}}'
kubectl scale deployment conversion-worker -n auc --replicas=2
```
