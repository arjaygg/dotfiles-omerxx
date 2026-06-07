Perform a full migration state cleanup before restarting a fresh full-load migration in DEV.

## Arguments: $ARGUMENTS
Parse: planID (default: 3776), namespace (default: dev), context (default: CCDE1L-AUCA-CL02).

## Why this is needed
`reset-tables` (Truncate_AUC_Reload SQL Agent job) only cleans `dbo.*` destination tables.
It does NOT clean config.KeyMap_*, ConversionProcessEvidence, or AuditLog tables.
Without cleaning these:
- KeyMap stale surrogate IDs → FK constraint violations
- Evidence SourceRowCount=1 placeholders → 0-row chunks (wrong ETLRowNumber bounds)
- Stale chunks → workers process empty ranges

## Steps to execute (in order, stop on failure)

### Step 1 — Cancel the plan
```
kubectl exec -n {namespace} {api_pod} --context {context} -- sh -c 'wget -q -S -O - --post-data "" --header "X-API-KEY: {api_key}" "http://localhost:8080/migration/plans/{planID}/cancel"'
```
Get api_pod: `kubectl get pod -n {namespace} --context {context} -l app=auc-conversion-api --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}'`
Get api_key: `kubectl get secret auc-conversion-secret -n {namespace} --context {context} -o jsonpath='{.data.APP_APIKEY}' | base64 -d`
Get CONV_PASS: `kubectl get secret auc-conversion-secret -n {namespace} --context {context} -o jsonpath='{.data.SQLSERVER_DB_CONVERSION_PASSWORD}' | base64 -d`
DB: 10.238.200.190:1433, user SVC_CCD_ALF_AUC_RW, database AUC

Use `kubectl run sqlcmd-SUFFIX --rm -i --restart=Never --context {context} -n {namespace} --image=mcr.microsoft.com/mssql-tools --command -- /opt/mssql-tools/bin/sqlcmd -S 10.238.200.190,1433 -U SVC_CCD_ALF_AUC_RW -P "$CONV_PASS" -d AUC -W -Q "..."` for all SQL steps.
Use unique suffixes (step1, step2, etc.) to avoid pod name collisions.

### Step 2 — Truncate all config.KeyMap_* tables
```sql
SET QUOTED_IDENTIFIER ON; SET ANSI_NULLS ON;
DECLARE @s NVARCHAR(MAX)='';
SELECT @s=@s+'TRUNCATE TABLE config.'+QUOTENAME(TABLE_NAME)+'; '
FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='config' AND TABLE_NAME LIKE 'KeyMap%';
EXEC sp_executesql @s;
SELECT ISNULL((SELECT SUM(p.rows) FROM sys.indexes i JOIN sys.partitions p ON i.object_id=p.object_id AND i.index_id=p.index_id WHERE i.index_id IN(0,1) AND SCHEMA_NAME(OBJECTPROPERTY(i.object_id,'SchemaId'))='config' AND OBJECT_NAME(i.object_id) LIKE 'KeyMap%'),0) AS KeyMapRowsRemaining;
```
Verify KeyMapRowsRemaining = 0.

### Step 3 — Delete Evidence, Errors, AuditLog (3 separate sqlcmd pods)
**Evidence:**
```sql
DELETE FROM config.ConversionProcessEvidence WHERE ProcessLogID IN (SELECT pl.ID FROM config.ConversionProcessLog pl JOIN config.MigrationTableSequence mts ON mts.TableID=pl.ProcessID WHERE mts.MigrationPlanID={planID}); SELECT @@ROWCOUNT AS EvidenceDeleted;
```
**Errors:**
```sql
DELETE FROM config.ConversionProcessLogError WHERE ProcessLogID IN (SELECT pl.ID FROM config.ConversionProcessLog pl JOIN config.MigrationTableSequence mts ON mts.TableID=pl.ProcessID WHERE mts.MigrationPlanID={planID}); SELECT @@ROWCOUNT AS ErrorsDeleted;
```
**AuditLog (details first, then header):**
```sql
DELETE FROM config.ConversionAuditLogDetails WHERE AuditLogID IN (SELECT AuditLogID FROM config.ConversionAuditLog WHERE ProcessLogID IN (SELECT pl.ID FROM config.ConversionProcessLog pl JOIN config.MigrationTableSequence mts ON mts.TableID=pl.ProcessID WHERE mts.MigrationPlanID={planID})); DELETE FROM config.ConversionAuditLog WHERE ProcessLogID IN (SELECT pl.ID FROM config.ConversionProcessLog pl JOIN config.MigrationTableSequence mts ON mts.TableID=pl.ProcessID WHERE mts.MigrationPlanID={planID}); SELECT @@ROWCOUNT AS AuditLogsDeleted;
```

### Step 4 — Delete stale chunks
```sql
SET QUOTED_IDENTIFIER ON; SET ANSI_NULLS ON; DELETE PLC FROM config.ProcessLogChunk PLC INNER JOIN config.ConversionProcessLog CPL ON CPL.ID=PLC.ProcessLogID INNER JOIN config.MigrationTableSequence MTS ON MTS.TableID=CPL.ProcessID WHERE MTS.MigrationPlanID={planID}; SELECT @@ROWCOUNT AS ChunksDeleted;
```

### Step 5 — Truncate AUCEtasChecksum
```sql
TRUNCATE TABLE dbo.AUCEtasChecksum; SELECT COUNT(*) AS Remaining FROM dbo.AUCEtasChecksum;
```

### Step 6 — Trigger destination table truncation
```
kubectl exec -n {namespace} {api_pod} --context {context} -- sh -c 'wget -q -S -O - --post-data "" --header "X-API-KEY: {api_key}" "http://localhost:8080/settings/reset-tables"'
```
Wait for truncation: poll `SELECT COUNT(*) FROM dbo.Contact` until 0 (check every 20s, timeout 3 min).

### Step 7 — Reset ProcessLog to PENDING and re-link MTS
```sql
UPDATE CPL SET CPL.Status='PENDING', CPL.ProcessEndDate=NULL, CPL.ProcessStartDate=NULL, CPL.UploadedRecords=0, CPL.TotalRecords=0, CPL.RecordWithErrorCount=0, CPL.TotalProcessedRecords=0, CPL.ErrorMessage=NULL, CPL.IsForRetry=0, CPL.TotalChunks=NULL, CPL.CompletedChunks=NULL FROM config.ConversionProcessLog CPL INNER JOIN config.MigrationTableSequence MTS ON MTS.TableID=CPL.ProcessID WHERE MTS.MigrationPlanID={planID}; SELECT @@ROWCOUNT AS ResetCount; UPDATE MTS SET MTS.ProcessLogID=pl.ID FROM config.MigrationTableSequence MTS CROSS APPLY (SELECT TOP 1 ID FROM config.ConversionProcessLog WHERE ProcessID=MTS.TableID AND Status='PENDING' ORDER BY ID DESC) pl WHERE MTS.MigrationPlanID={planID}; SELECT @@ROWCOUNT AS MTSLinked;
```

### Step 8 — Verify clean state
Query and display counts for all cleaned tables. All should be 0.

### Step 9 — Report
Print a clean summary table of before/after for each table.
Do NOT start the migration automatically — wait for user instruction.

## Do NOT clean
- `dbo.TableInfo` — reference/lookup data (ALF file mapping), pre-seeded, must stay
- `config.MigrationPlan` — status managed by /start endpoint
- `config.DataQuarantine` — plan-scoped, already empty
- `config.ProcessLogTelemetry` — already empty
