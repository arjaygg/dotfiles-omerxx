#!/usr/bin/env bash
set -euo pipefail

CONTEXT="${AUC_TRIAGE_CONTEXT:-CCDE1L-AUCA-CL02}"
NAMESPACE="${AUC_TRIAGE_NAMESPACE:-dev}"
SECRET_NAME="${AUC_TRIAGE_SECRET:-auc-conversion-secret}"
SQL_SERVER="${AUC_TRIAGE_SQL_SERVER:-127.0.0.1,10114}"
SQL_DB="${AUC_TRIAGE_SQL_DB:-AUC}"
PROCESS_LOGS="auto"
OUT_ROOT=".artifacts/quarantine-triage"

usage() {
  cat <<USAGE
Usage: $0 [options]

Options:
  --context <name>         Kubernetes context (default: ${CONTEXT})
  --namespace <name>       Kubernetes namespace (default: ${NAMESPACE})
  --secret <name>          Secret name for DB creds (default: ${SECRET_NAME})
  --sql-server <host,port> SQL Server endpoint (default: ${SQL_SERVER})
  --sql-db <name>          SQL database (default: ${SQL_DB})
  --process-logs <csv|auto>ProcessLog IDs CSV or auto (default: auto)
  --out-root <dir>         Artifact root dir (default: ${OUT_ROOT})
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --context) CONTEXT="$2"; shift 2 ;;
    --namespace) NAMESPACE="$2"; shift 2 ;;
    --secret) SECRET_NAME="$2"; shift 2 ;;
    --sql-server) SQL_SERVER="$2"; shift 2 ;;
    --sql-db) SQL_DB="$2"; shift 2 ;;
    --process-logs) PROCESS_LOGS="$2"; shift 2 ;;
    --out-root) OUT_ROOT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

for c in kubectl sqlcmd sdm; do
  command -v "$c" >/dev/null || { echo "missing command: $c"; exit 1; }
done

if ! sdm ready -v >/dev/null 2>&1; then
  echo "warning: sdm ready check failed; continuing (sqlcmd may fail)" >&2
fi

b64_get_secret() {
  kubectl --context "$CONTEXT" -n "$NAMESPACE" get secret "$SECRET_NAME" -o "jsonpath={.data.$1}" | base64 --decode
}

DB_USER="$(b64_get_secret SQLSERVER_DB_CONVERSION_USER)"
DB_PASS="$(b64_get_secret SQLSERVER_DB_CONVERSION_PASSWORD)"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="${OUT_ROOT}/${STAMP}"
mkdir -p "$OUT_DIR"

SQLCMD=(sqlcmd -S "$SQL_SERVER" -U "$DB_USER" -P "$DB_PASS" -d "$SQL_DB" -W -s "," -w 500)

run_sql_to_file() {
  local file="$1"
  local query="$2"
  "${SQLCMD[@]}" -Q "SET NOCOUNT ON; ${query}" > "$OUT_DIR/$file"
}

# K8s snapshots
kubectl --context "$CONTEXT" -n "$NAMESPACE" get deploy > "$OUT_DIR/k8s_deployments.txt" || true
kubectl --context "$CONTEXT" -n "$NAMESPACE" get pods -o wide > "$OUT_DIR/k8s_pods.txt" || true
kubectl --context "$CONTEXT" -n "$NAMESPACE" top pod > "$OUT_DIR/k8s_top_pods.txt" || true

run_sql_to_file "active_processing.csv" "
SELECT pl.ID AS ProcessLogID, pl.ProcessID, ct.TableName, pl.Status,
       pl.TotalRecords, pl.UploadedRecords, pl.RecordWithErrorCount,
       pl.TotalChunks, pl.CompletedChunks, pl.ProcessStartDate, pl.LastDateUpdated
FROM config.ConversionProcessLog pl
LEFT JOIN config.ConversionTable ct ON ct.ID = pl.ProcessID
WHERE pl.Status='PROCESSING'
ORDER BY pl.ID;"

if [[ "$PROCESS_LOGS" == "auto" ]]; then
  PROCESS_LOGS="$("${SQLCMD[@]}" -h -1 -Q "SET NOCOUNT ON; SELECT STRING_AGG(CAST(ID AS VARCHAR(20)),',') FROM config.ConversionProcessLog WHERE Status='PROCESSING';" | tr -d '[:space:]')"
  if [[ -z "$PROCESS_LOGS" || "$PROCESS_LOGS" == "NULL" ]]; then
    echo "No active processing process logs found. Artifacts: $OUT_DIR"
    exit 0
  fi
fi

if ! [[ "$PROCESS_LOGS" =~ ^[0-9]+(,[0-9]+)*$ ]]; then
  echo "invalid --process-logs value: $PROCESS_LOGS" >&2
  exit 1
fi

IN_LIST="$PROCESS_LOGS"

echo "$PROCESS_LOGS" > "$OUT_DIR/target_process_logs.txt"

run_sql_to_file "quarantine_counts.csv" "
SELECT dq.ProcessLogID,
       COUNT(*) AS QuarantineRows,
       SUM(CASE WHEN dq.ErrorCategory IS NULL THEN 1 ELSE 0 END) AS NullErrorCategory,
       SUM(CASE WHEN dq.ErrorCategory IS NOT NULL THEN 1 ELSE 0 END) AS NonNullErrorCategory
FROM config.DataQuarantine dq
WHERE dq.ProcessLogID IN (${IN_LIST})
GROUP BY dq.ProcessLogID
ORDER BY QuarantineRows DESC;"

run_sql_to_file "quarantine_error_category_breakdown.csv" "
SELECT dq.ProcessLogID, COALESCE(dq.ErrorCategory,'<NULL>') AS ErrorCategory, COUNT(*) AS Rows
FROM config.DataQuarantine dq
WHERE dq.ProcessLogID IN (${IN_LIST})
GROUP BY dq.ProcessLogID, COALESCE(dq.ErrorCategory,'<NULL>')
ORDER BY dq.ProcessLogID, Rows DESC;"

run_sql_to_file "audit_reason_breakdown.csv" "
SELECT al.ProcessLogID,
       COALESCE(ald.ErrorType,'UNCLASSIFIED') AS ErrorType,
       COALESCE(ald.Severity,'UNKNOWN') AS Severity,
       COUNT(*) AS Rows
FROM config.ConversionAuditLog al
JOIN config.ConversionAuditLogDetails ald ON ald.AuditLogID = al.AuditLogID
WHERE al.ProcessLogID IN (${IN_LIST})
GROUP BY al.ProcessLogID, COALESCE(ald.ErrorType,'UNCLASSIFIED'), COALESCE(ald.Severity,'UNKNOWN')
ORDER BY al.ProcessLogID, Rows DESC;"

run_sql_to_file "audit_top_columns.csv" "
SELECT al.ProcessLogID,
       COALESCE(ald.SourceColumn,'(none)') AS SourceColumn,
       COALESCE(ald.DestinationColumn,'(none)') AS DestinationColumn,
       COUNT(*) AS Rows
FROM config.ConversionAuditLog al
JOIN config.ConversionAuditLogDetails ald ON ald.AuditLogID = al.AuditLogID
WHERE al.ProcessLogID IN (${IN_LIST})
GROUP BY al.ProcessLogID, COALESCE(ald.SourceColumn,'(none)'), COALESCE(ald.DestinationColumn,'(none)')
ORDER BY al.ProcessLogID, Rows DESC;"

run_sql_to_file "audit_top_messages.csv" "
SELECT TOP 60
       al.ProcessLogID,
       COALESCE(ald.ErrorType,'UNCLASSIFIED') AS ErrorType,
       LEFT(COALESCE(ald.ErrorMessage,'<no message>'),200) AS ErrorMessage,
       COUNT(*) AS Rows
FROM config.ConversionAuditLog al
JOIN config.ConversionAuditLogDetails ald ON ald.AuditLogID = al.AuditLogID
WHERE al.ProcessLogID IN (${IN_LIST})
GROUP BY al.ProcessLogID, COALESCE(ald.ErrorType,'UNCLASSIFIED'), LEFT(COALESCE(ald.ErrorMessage,'<no message>'),200)
ORDER BY Rows DESC;"

run_sql_to_file "plan_dependency_snapshot.csv" "
WITH plans AS (
  SELECT DISTINCT MigrationPlanID
  FROM config.MigrationTableSequence
  WHERE ProcessLogID IN (${IN_LIST})
)
SELECT mts.MigrationPlanID, mts.Level, mts.TableID, ct.TableName, mts.ProcessLogID,
       COALESCE(pl.Status,'UNSTARTED') AS ProcessStatus,
       pl.TotalRecords, pl.UploadedRecords, pl.RecordWithErrorCount
FROM config.MigrationTableSequence mts
JOIN plans p ON p.MigrationPlanID = mts.MigrationPlanID
LEFT JOIN config.ConversionTable ct ON ct.ID = mts.TableID
LEFT JOIN config.ConversionProcessLog pl ON pl.ID = mts.ProcessLogID
ORDER BY mts.MigrationPlanID, mts.Level, mts.TableID;"

cat > "$OUT_DIR/README.md" <<README
# Quarantine Triage Artifact

- generated_utc: ${STAMP}
- kube_context: ${CONTEXT}
- namespace: ${NAMESPACE}
- sql_server: ${SQL_SERVER}
- sql_db: ${SQL_DB}
- target_process_logs: ${PROCESS_LOGS}

## Files
- k8s_deployments.txt
- k8s_pods.txt
- k8s_top_pods.txt
- active_processing.csv
- quarantine_counts.csv
- quarantine_error_category_breakdown.csv
- audit_reason_breakdown.csv
- audit_top_columns.csv
- audit_top_messages.csv
- plan_dependency_snapshot.csv
README

echo "Artifact written: $OUT_DIR"
