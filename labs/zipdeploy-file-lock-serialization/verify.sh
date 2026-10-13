#!/bin/bash
# Collect deployment records and the Activity Log for the run.
# SINCE=2026-10-13T22:48:00Z limits both to the final run (the Activity Log is read over the last 24 hours).
set -euo pipefail

RG="${1:-}"
APP_NAME="${2:-}"
OUT_DIR="${3:-artifacts/raw/evidence}"
SINCE="${SINCE:-}"

if [ -z "$RG" ] || [ -z "$APP_NAME" ]; then
    echo "Usage: $0 <RESOURCE_GROUP> <APP_NAME> [OUTPUT_DIR]"
    exit 1
fi

mkdir -p "$OUT_DIR"

if [ -n "$SINCE" ]; then
    ACTIVITY_FILTER="[?eventTimestamp >= '$SINCE' && contains(resourceId, '$APP_NAME')]"
else
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
