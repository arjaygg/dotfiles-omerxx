# Playbook: db-locks

Resolve database lock contention blocking migration chunk processing. Identifies and
terminates long-running blocking queries. Use only when lock wait timeout errors are confirmed.

## Preconditions

- [ ] Logs show lock wait errors: `Lock wait timeout exceeded` or `deadlock found`
- [ ] DB metrics show active locks > threshold (check Grafana: `auc_db_active_locks`)
- [ ] Confirm the blocking query is from the migration worker, not another system

## Steps

```bash
# 1. Identify blocking queries (requires DB access via kubectl exec or port-forward)
kubectl port-forward svc/auc-db -n auc 3306:3306 &
PF_PID=$!
sleep 2

# 2. Show processlist — find blocking queries
mysql -h 127.0.0.1 -u "$DB_USER" -p"$DB_PASS" -e "
  SELECT
    p.ID, p.USER, p.HOST, p.DB, p.TIME, p.STATE, LEFT(p.INFO, 100) as QUERY,
    r.trx_wait_started
  FROM information_schema.PROCESSLIST p
  LEFT JOIN information_schema.INNODB_TRX r ON p.ID = r.trx_mysql_thread_id
  WHERE p.TIME > 30
  ORDER BY p.TIME DESC
  LIMIT 20;
"

# 3. Terminate identified blocking query (replace <PROCESS_ID>)
# mysql -h 127.0.0.1 -u "$DB_USER" -p"$DB_PASS" -e "KILL QUERY <PROCESS_ID>;"

# 4. Clean up port-forward
kill $PF_PID 2>/dev/null || true
```

## Verification

- Lock wait errors stop appearing in worker logs within 2 minutes
- Chunk processing resumes (rate > 0 in metrics)
- `SHOW ENGINE INNODB STATUS` shows no blocking transactions

## Rollback

KILL QUERY is not reversible, but the terminated query will be retried by the worker.
If killing queries causes data inconsistency, scale down the worker first:
```bash
kubectl scale deployment conversion-worker -n auc --replicas=0
```
Then investigate the root cause before restarting.

## Notes

- Prefer `KILL QUERY` over `KILL CONNECTION` — QUERY terminates the statement, CONNECTION drops the session
- If the blocker is a long-running analytics query (not the worker), coordinate with the team before killing
- DB_USER and DB_PASS should come from the auc-db secret: `kubectl get secret auc-db-credentials -n auc -o jsonpath='{.data.password}' | base64 -d`
