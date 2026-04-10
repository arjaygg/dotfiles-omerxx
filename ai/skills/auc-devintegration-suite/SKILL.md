---
name: auc-devintegration-suite
description: |
  Provisions the `dev-integration` namespace on EKS DEV cluster (CCDE1L-AUCA-CL02),
  deploys SQL Server with AUC schema+data seeded from Dev/QA, deploys workers/supervisor
  from the current branch image, installs Chaos Mesh, seeds an active conversion job,
  then runs the FULL auc-conversion test suite (unit, integration, E2E, chaos, baseline)
  against the live environment.

  Use this whenever you need a complete branch test environment with real SQL Server data,
  live K8s workers, and full chaos/baseline coverage — not just testcontainers.

  Triggers: "run full test suite", "provision dev-integration", "branch environment",
  "full e2e with real data", "chaos + baseline environment"
version: "1.0"
triggers:
  - provision dev-integration
  - full test suite
  - branch environment
  - e2e with real data
  - chaos mesh environment
---

# AUC Dev-Integration Suite

Provisions `dev-integration` on EKS DEV and runs the complete test suite.

## When to Use

- You need to run integration/E2E/chaos/baseline tests with real AUC schema and data
- A PR needs full environment validation before merge
- You want chaos tests to actually execute (not skip due to missing pods/job/Chaos Mesh)
- You need baseline benchmarks with production-like partition functions

## Instructions

### Phase 1 — Infra (sequential, blocking)

Spawn **Agent: infra-provisioner** (foreground). It must complete before test agents start.

**Infra agent responsibilities:**

```
1. Create namespace
   kubectl create namespace dev-integration --dry-run=client -o yaml | kubectl apply -f -

2. Copy secrets from dev namespace
   kubectl get secret auc-conversion-secret -n dev -o yaml \
     | sed 's/namespace: dev/namespace: dev-integration/' \
     | kubectl apply -f -

3. Deploy SQL Server in-cluster
   Use Helm or raw manifests — mcr.microsoft.com/mssql/server:2022-latest
   - PVC: 20Gi
   - SA_PASSWORD from secret
   - Service: ClusterIP port 1433
   - Named: auc-sqlserver
   Wait for pod Ready.

4. Seed schema from Dev/QA
   a. Port-forward to DEV SQL Server (from auc-conversion-secret DSN)
   b. Export full schema: control.worker_registry, config.*, AUC tables
      including partition function pf_LargeDataTableID and ETL columns
      (ETLRowNumber, ETLIsUpdated)
   c. Export sample data (10K rows per table, or BASELINE_ROW_COUNT env var)
   d. Apply schema + data to the new auc-sqlserver pod via kubectl exec sqlcmd

5. Deploy workers (5 replicas) + supervisor from branch image
   - Use kustomize overlay: bases/auc-conversion, overlay dev-integration
   - Image tag: current branch CI image (from BRANCH_IMAGE env or latest dev tag)
   - Override: CHAOS_NAMESPACE=dev-integration, AUC_DB pointing at auc-sqlserver
   - Service: expose worker API on port 8080 (ClusterIP)

6. Install Chaos Mesh
   helm repo add chaos-mesh https://charts.chaos-mesh.org
   helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
     -n dev-integration --set chaosDaemon.runtime=containerd \
     --wait --timeout 5m

7. Seed active conversion job
   Insert a ProcessLog + ProcessLogChunk records in Processing state
   so CH1/CH5 have live chunks to interact with.
   Use kubectl exec into auc-sqlserver to run seed SQL.

8. Wait for ≥5 worker pods Ready
   kubectl rollout status deployment/auc-conversion-worker -n dev-integration --timeout=5m

9. Collect and return env vars:
   AUC_INTEGRATION_SQLSERVER_DSN=sqlserver://sa:<pass>@<svc-ip>:1433?database=AUC
   AUC_WORKER_API_URL=http://<worker-svc-ip>:8080
   CONFIG_DB_CONN=server=<svc-ip>;user id=sa;password=<pass>;database=AUC
   CHAOS_NAMESPACE=dev-integration
   WORKER_DEPLOYMENT=auc-conversion-worker
   KUBECONFIG=~/.kube/config
```

**Infra agent must output** a JSON block:
```json
{
  "AUC_INTEGRATION_SQLSERVER_DSN": "...",
  "AUC_WORKER_API_URL": "...",
  "CONFIG_DB_CONN": "...",
  "CHAOS_NAMESPACE": "dev-integration",
  "WORKER_DEPLOYMENT": "auc-conversion-worker",
  "KUBECONFIG": "~/.kube/config",
  "SOAK_TEST_DURATION": "30m",
  "E2E_K8S_ENABLED": "true"
}
```

---

### Phase 2 — Test Agents (parallel, after infra completes)

Spawn all four test agents simultaneously using the env vars from Phase 1.

#### Agent: unit-runner
```
go test -race -count=1 ./...
```
Report: pass/fail per package, race conditions.

#### Agent: integration-runner
```
go test -tags integration -v -count=1 -timeout 15m \
  ./tests/integration/... \
  ./tests/architecture/...
```
Set:
- `AUC_INTEGRATION_SQLSERVER_DSN` — use the in-cluster SQL Server DSN
- `AUC_WORKER_API_URL` — use the worker service URL
- `E2E_K8S_ENABLED=true`

Report: pass/skip/fail per test. E2E tests should now run (not skip).

#### Agent: chaos-runner
```
KUBECONFIG=~/.kube/config \
CHAOS_NAMESPACE=dev-integration \
WORKER_DEPLOYMENT=auc-conversion-worker \
CONFIG_DB_CONN="..." \
go test -tags chaos -v -count=1 -timeout 45m ./tests/chaos/...
```
All 9 tests should now execute:
- CH1/CH5: active chunks seeded in Phase 1
- CH2/CH3: ≥5 pods deployed
- CH3/CH4: Chaos Mesh installed
- WIP skip (`TestChaos_ShutdownDuringChunkBoundary`) is expected

Report: pass/skip/fail per test.

#### Agent: baseline-runner
```
SOAK_TEST_DURATION=30m \
AUC_INTEGRATION_SQLSERVER_DSN="..." \
go test -tags baseline -v -count=1 -timeout 60m -bench=. ./tests/baseline/...
```
The 4 integration benchmarks now have production-like schema — remove their skip guards
and set `ETLColumn: "ETLRowNumber"` in DataFilter. The baseline runner agent should:
1. Verify the in-cluster SQL Server has `pf_LargeDataTableID` and ETL columns
2. If yes: update the 4 benchmark DataFilter configs and re-run
3. Report benchmark results (ns/op, rec/sec)

---

### Phase 3 — Report (after all test agents complete)

Spawn **Agent: report-consolidator** with outputs from all four test agents.

Produce a consolidated table:

```
## Dev-Integration Full Test Suite Report

### Environment
- Namespace: dev-integration
- Cluster: CCDE1L-AUCA-CL02
- SQL Server: auc-sqlserver (in-cluster)
- Workers: 5 replicas
- Chaos Mesh: installed

### Results

| Suite        | Pass | Skip | Fail | Notes |
|---|---|---|---|---|
| Unit         |  26  |  0   |  0   | -race clean |
| Integration  |  ?   |  ?   |  ?   | E2E with live env |
| Chaos        |  ?   |  1   |  ?   | 1 WIP skip expected |
| Baseline     |  ?   |  ?   |  ?   | benchmarks: rec/sec |

### Failures
<list any failures with root cause>

### Benchmark Highlights
<key perf numbers>
```

---

## Agent Spawn Sequence

```
invoke /auc-devintegration-suite
│
├── [FOREGROUND] infra-provisioner
│     Provisions namespace, SQL Server, workers, Chaos Mesh, seeds job
│     → outputs env JSON
│
└── [PARALLEL, after infra] ──────────────────────────────────────┐
      unit-runner          integration-runner   chaos-runner   baseline-runner
      (local, ~2min)       (in-cluster, ~15m)  (K8s, ~45m)   (SQL, ~60m)
      │                    │                    │              │
      └──────────────── all complete ───────────────────────────┘
                              │
                    [FOREGROUND] report-consolidator
                              │
                        Final report
```

## Examples

```
# Provision environment and run full suite
/auc-devintegration-suite

# Override branch image
BRANCH_IMAGE=v1.0.352-supervisor.1 /auc-devintegration-suite

# Seed more data for baseline
BASELINE_ROW_COUNT=100000 /auc-devintegration-suite
```

## Environment Variables

| Var | Default | Purpose |
|-----|---------|---------|
| `BRANCH_IMAGE` | latest `dev` tag | Worker/supervisor image to deploy |
| `BASELINE_ROW_COUNT` | 10000 | Rows per table seeded from Dev/QA |
| `SOAK_TEST_DURATION` | `30m` | Baseline soak test duration |
| `CHAOS_NAMESPACE` | `dev-integration` | Namespace for chaos tests |
| `WORKER_REPLICAS` | `5` | Initial worker replica count |
| `SKIP_INFRA` | unset | Set to `true` to skip provisioning (reuse existing namespace) |
| `SKIP_SEED` | unset | Set to `true` to skip data seeding |
| `TEARDOWN` | unset | Set to `true` to delete namespace after suite completes |

## Teardown

After the suite completes, optionally clean up:
```bash
kubectl delete namespace dev-integration
helm uninstall chaos-mesh -n dev-integration
```

Or set `TEARDOWN=true` when invoking the skill.

## Related Skills

- `sqlserver-integration-tester` — runs integration tests only (no env provisioning)
- `auc-qa` — QA agent for test-first mutation-verified coverage
- `stack-pr` — creates PR after passing the full suite
