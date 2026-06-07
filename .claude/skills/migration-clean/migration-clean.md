# /migration-clean — Full Migration Reset

Performs a complete cleanup of all migration state tables before restarting
a fresh full-load migration run in DEV. `reset-tables` alone is NOT sufficient
(it only cleans dbo.* destination tables, not KeyMap, Evidence, or Audit tables).

## Usage

```
/migration-clean [planID] [namespace] [context]
```

**Defaults:** planID=3776, namespace=dev, context=CCDE1L-AUCA-CL02

## Instructions

Parse arguments: `planID`, `namespace` (default: dev), `k8s_context` (default: CCDE1L-AUCA-CL02).

Get API pod and credentials:
```bash
API_POD=$(kubectl get pod -n $NAMESPACE --context $K8S_CONTEXT -l app=auc-conversion-api --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
CONV_PASS=$(kubectl get secret auc-conversion-secret -n $NAMESPACE --context $K8S_CONTEXT -o jsonpath='{.data.SQLSERVER_DB_CONVERSION_PASSWORD}' | base64 -d)
DB_HOST=$(kubectl get secret auc-conversion-secret -n $NAMESPACE --context $K8S_CONTEXT -o jsonpath='{.data.SQLSERVER_DB_CONVERSION_HOST}' | base64 -d)
DB_USER=$(kubectl get secret auc-conversion-secret -n $NAMESPACE --context $K8S_CONTEXT -o jsonpath='{.data.SQLSERVER_DB_CONVERSION_USER}' | base64 -d)
API_KEY=$(kubectl get secret auc-conversion-secret -n $NAMESPACE --context $K8S_CONTEXT -o jsonpath='{.data.APP_APIKEY}' | base64 -d)
```

Execute in order — stop and report on any step failure:

### Step 1: Cancel the plan
```bash
kubectl exec -n $NAMESPACE $API_POD --context $K8S_CONTEXT -- \
  sh -c "wget -q -S -O - --post-data '' --header 'X-API-KEY: $API_KEY' \
  'http://localhost:8080/migration/plans/$PLAN_ID/cancel'"
```

### Step 2: Truncate all config.KeyMap_* tables (dynamic — covers all 49+)
```sql
SET QUOTED_IDENTIFIER ON; SET ANSI_NULLS ON;
DECLARE @s NVARCHAR(MAX)='';
SELECT @s=@s+'TRUNCATE TABLE config.'+QUOTENAME(TABLE_NAME)+'; '
FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='config' AND TABLE_NAME LIKE 'KeyMap%';
EXEC sp_executesql @s;
SELECT ISNULL((SELECT SUM(p.rows) FROM sys.indexes i JOIN sys.partitions p
  ON i.object_id=p.object_id AND i.index_id=p.index_id
  WHERE i.index_id IN(0,1) AND SCHEMA_NAME(OBJECTPROPERTY(i.object_id,'SchemaId'))='config'
  AND OBJECT_NAME(i.object_id) LIKE 'KeyMap%'),0) AS KeyMapRowsRemaining;
```

### Step 3: Delete Evidence, Errors, AuditLog
```sql
DELETE FROM config.ConversionProcessEvidence
WHERE ProcessLogID IN (SELECT pl.ID FROM config.ConversionProcessLog pl
  JOIN config.MigrationTableSequence mts ON mts.TableID=pl.ProcessID
  WHERE mts.MigrationPlanID=@PlanID);

DELETE FROM config.ConversionProcessLogError
WHERE ProcessLogID IN (SELECT pl.ID FROM config.ConversionProcessLog pl
  JOIN config.MigrationTableSequence mts ON mts.TableID=pl.ProcessID
  WHERE mts.MigrationPlanID=@PlanID);

DELETE FROM config.ConversionAuditLogDetails
WHERE AuditLogID IN (SELECT AuditLogID FROM config.ConversionAuditLog
  WHERE ProcessLogID IN (SELECT pl.ID FROM config.ConversionProcessLog pl
    JOIN config.MigrationTableSequence mts ON mts.TableID=pl.ProcessID
    WHERE mts.MigrationPlanID=@PlanID));

DELETE FROM config.ConversionAuditLog
WHERE ProcessLogID IN (SELECT pl.ID FROM config.ConversionProcessLog pl
  JOIN config.MigrationTableSequence mts ON mts.TableID=pl.ProcessID
  WHERE mts.MigrationPlanID=@PlanID);
```

### Step 4: Delete stale chunks
```sql
SET QUOTED_IDENTIFIER ON; SET ANSI_NULLS ON;
DELETE PLC FROM config.ProcessLogChunk PLC
INNER JOIN config.ConversionProcessLog CPL ON CPL.ID=PLC.ProcessLogID
INNER JOIN config.MigrationTableSequence MTS ON MTS.TableID=CPL.ProcessID
WHERE MTS.MigrationPlanID=@PlanID;
```

### Step 5: Truncate AUCEtasChecksum (checksum dedup table)
```sql
TRUNCATE TABLE dbo.AUCEtasChecksum;
```

### Step 6: Trigger destination table truncation
```bash
kubectl exec -n $NAMESPACE $API_POD --context $K8S_CONTEXT -- \
  sh -c "wget -q -S -O - --post-data '' --header 'X-API-KEY: $API_KEY' \
  'http://localhost:8080/settings/reset-tables'"
```
Wait ~60 seconds for the SQL Agent job to complete, then verify: `SELECT COUNT(*) FROM dbo.Contact` should be 0.

### Step 7: Reset ProcessLog statuses and re-link MTS
```sql
-- Delete remaining stale chunks (insurance)
DELETE PLC FROM config.ProcessLogChunk PLC
INNER JOIN config.ConversionProcessLog CPL ON CPL.ID=PLC.ProcessLogID
INNER JOIN config.MigrationTableSequence MTS ON MTS.TableID=CPL.ProcessID
WHERE MTS.MigrationPlanID=@PlanID;

-- Reset ProcessLog to PENDING
UPDATE CPL SET CPL.Status='PENDING', CPL.ProcessEndDate=NULL, CPL.ProcessStartDate=NULL,
  CPL.UploadedRecords=0, CPL.TotalRecords=0, CPL.RecordWithErrorCount=0,
  CPL.TotalProcessedRecords=0, CPL.ErrorMessage=NULL, CPL.IsForRetry=0,
  CPL.TotalChunks=NULL, CPL.CompletedChunks=NULL
FROM config.ConversionProcessLog CPL
INNER JOIN config.MigrationTableSequence MTS ON MTS.TableID=CPL.ProcessID
WHERE MTS.MigrationPlanID=@PlanID;

-- Re-link MTS.ProcessLogID
UPDATE MTS SET MTS.ProcessLogID=pl.ID
FROM config.MigrationTableSequence MTS
CROSS APPLY (SELECT TOP 1 ID FROM config.ConversionProcessLog
  WHERE ProcessID=MTS.TableID AND Status='PENDING' ORDER BY ID DESC) pl
WHERE MTS.MigrationPlanID=@PlanID;
SELECT @@ROWCOUNT AS MTSLinked;
```

### Step 8: Verify clean state
Report counts for all cleaned tables. All should be 0 except TableInfo.

### Step 9: Start the migration (only if requested OR when new version is deployed)
```bash
kubectl exec -n $NAMESPACE $API_POD --context $K8S_CONTEXT -- \
  sh -c "wget -q -S -O - --post-data '' --header 'X-API-KEY: $API_KEY' \
  'http://localhost:8080/migration/plans/$PLAN_ID/start'"
```

## Tables NOT cleaned (intentional)
- `dbo.TableInfo` — reference/lookup data (ALF file mapping), pre-seeded
- `config.MigrationPlan` — status managed automatically by `/start` endpoint
- `config.DataQuarantine` — plan-scoped, already empty
- `config.ProcessLogTelemetry` — already empty

## Notes
- Run this BEFORE deploying a new version that fixes chunk sizing
- KeyMap cleanup is critical: stale FK surrogate IDs cause FK constraint violations
- Evidence cleanup is critical: SourceRowCount=1 placeholders cause 0-row chunks
- Use sqlcmd via `kubectl run` pod with `mcr.microsoft.com/mssql-tools` image
