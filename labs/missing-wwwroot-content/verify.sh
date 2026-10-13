#!/bin/bash
# Collect the evidence sources the playbook discusses: Activity Log (control plane),
# deployment records, and the App Service log tables via Log Analytics.
# SINCE=2026-10-13T13:45:00Z limits the Activity Log, deployment records and every KQL query
# to the final run, so earlier exploratory activity is not mixed in.
set -euo pipefail

RG="${1:-}"
APP_NAME="${2:-}"
OUT_DIR="${3:-artifacts/raw/evidence}"
SINCE="${SINCE:-}"
ASSET_SUFFIX="/assets/probe.txt"

if [ -z "$RG" ] || [ -z "$APP_NAME" ]; then
    echo "Usage: $0 <RESOURCE_GROUP> <APP_NAME> [OUTPUT_DIR]"
    exit 1
fi

mkdir -p "$OUT_DIR"
# tr strips the carriage return that a Windows-hosted Azure CLI appends to tsv output
WORKSPACE_ID=$(az monitor log-analytics workspace list --resource-group "$RG" --query "[0].customerId" --output tsv | tr -d '\r')

if [ -n "$SINCE" ]; then
    TIME_FILTER="TimeGenerated > datetime($SINCE)"
    ACTIVITY_FILTER="[?eventTimestamp >= '$SINCE' && contains(resourceId, '$APP_NAME')]"
else
    TIME_FILTER="TimeGenerated > ago(6h)"
    ACTIVITY_FILTER="[?contains(resourceId, '$APP_NAME')]"
fi

az monitor activity-log list \
    --resource-group "$RG" \
    --offset 24h \
    --max-events 200 \
    --query "${ACTIVITY_FILTER}.{time:eventTimestamp,operation:operationName.value,caller:caller,status:status.value}" \
    --output json > "$OUT_DIR/activity-log.json"

# Plan-level changes (for example a SKU change made by something other than the experimenter)
az monitor activity-log list \
    --resource-group "$RG" \
    --offset 24h \
    --max-events 200 \
    --query "[?contains(resourceId, 'serverfarms')].{time:eventTimestamp,operation:operationName.value,caller:caller,status:status.value}" \
    --output json > "$OUT_DIR/activity-log-plan.json"

az webapp log deployment list --resource-group "$RG" --name "$APP_NAME" --output json > "$OUT_DIR/deployment-records-all.json"
python3 - "$OUT_DIR/deployment-records-all.json" "$OUT_DIR/deployment-records.json" "$SINCE" <<'PY'
import json
import sys

source, target, since = sys.argv[1], sys.argv[2], sys.argv[3]
records = json.load(open(source, encoding='utf-8'))
kept = [r for r in records if not since or (r.get('end_time') or r.get('received_time') or '') >= since]
json.dump(kept, open(target, 'w', encoding='utf-8'), indent=2)
print(f"deployment records kept: {len(kept)} of {len(records)}")
PY
rm -f "$OUT_DIR/deployment-records-all.json"

run_kql() {
    local name="$1" query="$2"
    az monitor log-analytics query \
        --workspace "$WORKSPACE_ID" \
        --analytics-query "$query" \
        --output json > "$OUT_DIR/kql-$name.json"
}

run_kql http-404 "AppServiceHTTPLogs | where $TIME_FILTER | where CsUriStem endswith '$ASSET_SUFFIX' | where ScStatus == 404 | summarize FirstLogged404=min(TimeGenerated), LastLogged404=max(TimeGenerated), Count404=count()"
run_kql http-success "AppServiceHTTPLogs | where $TIME_FILTER | where CsUriStem endswith '$ASSET_SUFFIX' | where ScStatus between (200 .. 399) | summarize LastLoggedSuccess=max(TimeGenerated), CountSuccess=count()"
run_kql ingestion-lag "AppServiceHTTPLogs | where $TIME_FILTER | where CsUriStem endswith '$ASSET_SUFFIX' | summarize Rows=count(), MinLagSeconds=min(datetime_diff('second', ingestion_time(), TimeGenerated)), MedianLagSeconds=percentile(datetime_diff('second', ingestion_time(), TimeGenerated), 50), MaxLagSeconds=max(datetime_diff('second', ingestion_time(), TimeGenerated))"
run_kql console-audit "AppServiceConsoleLogs | where $TIME_FILTER | where ResultDescription has 'LAB_AUDIT' | project TimeGenerated, ResultDescription | order by TimeGenerated asc"
run_kql platform-lifecycle "AppServicePlatformLogs | where $TIME_FILTER | where Message has_any ('Site started', 'Stopping', 'Starting', 'terminat', 'Deleting container') | project TimeGenerated, Level, Message | order by TimeGenerated asc"

python3 - "$OUT_DIR/evidence-manifest.json" "$SINCE" <<'PY'
import datetime
import json
import sys

with open(sys.argv[1], 'w', encoding='utf-8') as handle:
    json.dump({
        'collectedAt': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'since': sys.argv[2] or 'last 6 hours',
    }, handle, indent=2)
PY
echo "Evidence written to $OUT_DIR"
