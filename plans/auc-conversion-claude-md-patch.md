# auc-conversion CLAUDE.md Migration & Deployment Verification Patch

Add this section to the auc-conversion project's `CLAUDE.md` (or `AGENTS.md`).
It is project-specific and does NOT belong in the user-global dotfiles.

Derived from: 28-day Claude Code insights report (2026-05-21), Migration & Deployment Verification
friction category (multiple sessions: premature success declaration, wrong resume flow, timeouts).

---

## Migration & Deployment Verification

**These rules prevent the most common migration failure modes observed in production.**

### Verifying Success

- Never assume job exit code 0 = success. Always verify actual artifacts:
  - Index creation: query `pg_stat_user_indexes` to confirm the index exists
  - Row counts: `SELECT COUNT(*) FROM <table>` must match expected batch range
  - Pod health: `kubectl get pods -n auc-conversion` must show all Running (not Pending/Error)
  - API health: hit the auc-conversion health endpoint and verify 200

### Timeouts

- Never set migration job timeouts under **30 minutes**. Index creation on multi-billion row
  tables routinely takes 60–90 minutes. A 10-minute timeout will kill a healthy run.
- For large table migrations (>500M rows), set timeout to at least **2 hours**.

### Resume vs New Migration

When asked to "resume" a migration, ALWAYS check existing state first — never start a new run:

```bash
# Step 1: Is any migration job currently running?
kubectl get jobs -n auc-conversion | grep -E "(Running|Pending)"

# Step 2: What does the DB say is the current migration state?
# (check migrations tracking table — schema varies by version)

# Step 3: What was the last successfully completed batch/tier?
# Only proceed with resume if: no active job AND DB state confirms incomplete
```

If an active job is found → monitor it; do NOT start another.
If DB state shows complete → migration is done; tell the user.
Only if no active job AND incomplete DB state → proceed with resume.

### Post-Deployment Verification

After any release deployment (vX.Y.Z), verify with **both** signals:

1. **K8s:** `kubectl rollout status deploy -n auc-conversion` → must complete without error
2. **DB:** confirm schema version matches expected release (check schema_migrations or equivalent)
3. **Logs:** `kubectl logs -n auc-conversion deploy/auc-conversion --since=5m` → no ERROR/FATAL in first 5 minutes post-deploy
