---
name: quarantine-triage-live
description: >
  AUC live migration quarantine + bottleneck triage. Use this whenever you need
  reproducible, fast incident investigation for PROCESSING tables, quarantine
  reason extraction, dependency blockers, and resume recommendations in DEV/QA.
  Invoke as /quarantine-triage-live.
version: 1.0.0
triggers:
  - /quarantine-triage-live
  - quarantine triage
  - bottleneck triage
  - process stuck
  - why is this process stuck
  - resume migration plan
  - live quarantine investigation
---

# /quarantine-triage-live — AUC Live Incident Triage

## Role

You are a **fast incident triage skill** for active AUC runs.

Goal: produce a deterministic evidence pack in minutes, with:
1. current blocker process logs,
2. root-cause reason breakdown,
3. dependency impact,
4. concrete resume actions.

This skill complements `/quarantine-analyst`:
- Use **this** for live operational triage and reproducibility.
- Use `/quarantine-analyst` for broad exploratory analysis, visuals, and deep offline research.

---

## Default assumptions

- K8s context: `CCDE1L-AUCA-CL02`
- Namespace: `dev`
- Secret: `auc-conversion-secret`
- SQL tunnel: `127.0.0.1,10114`
- DB: `AUC`

Override with env vars if needed:
- `AUC_TRIAGE_CONTEXT`
- `AUC_TRIAGE_NAMESPACE`
- `AUC_TRIAGE_SECRET`
- `AUC_TRIAGE_SQL_SERVER`
- `AUC_TRIAGE_SQL_DB`

---

## Deterministic workflow (always follow)

### Phase 0 — Capture run metadata
- Record timestamp, context, namespace, DB target.
- Save all outputs to a timestamped artifact folder.

### Phase 1 — App/K8s state snapshot
- deployments/pods readiness for api/scheduler/worker
- worker pod resource usage (`kubectl top pod`)

### Phase 2 — Active process bottleneck scan
- current `PROCESSING` process logs
- process progress (`TotalRecords`, `UploadedRecords`, `RecordWithErrorCount`)
- quarantine counts for active process logs

### Phase 3 — Root-cause extraction (fast + reproducible)
For target process logs:
- `DataQuarantine.ErrorCategory` distribution
- audit detail reason distribution (`ErrorType`, `Severity`)
- top failing columns
- top message snippets

### Phase 4 — Dependency impact
- migration plan level/status around blocker process logs
- identify child tables likely blocked by missing FK parents

### Phase 5 — Resume recommendation
Return exactly:
1. Primary blocker(s)
2. Why blocked (reason categories)
3. Blast radius (dependent tables/levels)
4. Next 3 actions (pause/resume/retry ordering)

---

## Execution command

```bash
~/.dotfiles/ai/skills/quarantine-triage-live/scripts/run_quarantine_triage.sh \
  --context CCDE1L-AUCA-CL02 \
  --namespace dev \
  --process-logs auto
```

Optional explicit process logs:
```bash
~/.dotfiles/ai/skills/quarantine-triage-live/scripts/run_quarantine_triage.sh \
  --process-logs 3789,3794
```

Artifacts are written to:
- `.artifacts/quarantine-triage/<timestamp>/`

---

## Output contract

Always summarize with this exact section order:
1. **Active Bottlenecks**
2. **Root-Cause Reasons**
3. **Dependency/Blast Radius**
4. **Resume Plan (ordered actions)**
5. **Evidence Files**

---

## Related skills

- `/quarantine-analyst` — broad/visual/deep analysis
- `/db-admin` — server-level performance/config analysis
- `/strange` — strict debugging workflow
