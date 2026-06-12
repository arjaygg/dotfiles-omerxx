# Playbook: timeout-extend

Extend processing timeouts on the conversion worker when chunks are timing out due to
large data volumes or slow DB queries. Non-destructive — extends, does not disable.

## Preconditions

- [ ] Logs show timeout errors: `context deadline exceeded` or `query execution timeout`
- [ ] DB query metrics show queries running longer than current timeout value
- [ ] Current timeout in ConfigMap is below threshold (check before extending beyond 10m)

## Steps

```bash
# 1. Read current timeout
CURRENT=$(kubectl get cm conversion-worker-config -n auc \
  -o jsonpath='{.data.chunk_processing_timeout_seconds}')
echo "Current timeout: ${CURRENT}s"

# 2. Extend by 50% (cap at 600s / 10min)
NEW=$(( CURRENT * 3 / 2 ))
if [[ $NEW -gt 600 ]]; then NEW=600; fi
echo "New timeout: ${NEW}s"

# 3. Apply
kubectl patch cm conversion-worker-config -n auc \
  --type merge -p "{\"data\":{\"chunk_processing_timeout_seconds\":\"${NEW}\"}}"

# 4. Restart worker to pick up new config
kubectl rollout restart deployment/conversion-worker -n auc
kubectl rollout status deployment/conversion-worker -n auc --timeout=120s
```

## Verification

- No new timeout errors in worker logs for 5 minutes
- `kubectl logs -n auc deploy/conversion-worker --tail=50` — no `context deadline exceeded`

## Rollback

```bash
kubectl patch cm conversion-worker-config -n auc \
  --type merge -p "{\"data\":{\"chunk_processing_timeout_seconds\":\"${CURRENT}\"}}"
kubectl rollout restart deployment/conversion-worker -n auc
```
