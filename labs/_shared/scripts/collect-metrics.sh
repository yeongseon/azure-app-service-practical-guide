#!/usr/bin/env bash

set -euo pipefail

RG="${1:-}"
APP_NAME="${2:-}"
OUTPUT_DIR="${3:-artifacts/raw/metrics}"
DURATION="${4:-PT1H}"
INTERVAL="${5:-PT1M}"

if [[ -z "${RG}" || -z "${APP_NAME}" ]]; then
  echo "Usage: $0 <RG> <APP_NAME> [OUTPUT_DIR] [DURATION_ISO8601] [INTERVAL_ISO8601]"
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

PLAN_METRICS_FILE="${OUTPUT_DIR}/plan-metrics.json"
APP_METRICS_FILE="${OUTPUT_DIR}/app-metrics.json"
SUMMARY_CSV="${OUTPUT_DIR}/metrics-summary.csv"

APP_ID="$(az webapp show --resource-group "${RG}" --name "${APP_NAME}" --query id --output tsv)"
PLAN_ID="$(az webapp show --resource-group "${RG}" --name "${APP_NAME}" --query serverFarmId --output tsv)"

if [[ -z "${APP_ID}" || -z "${PLAN_ID}" ]]; then
  echo "[collect-metrics] Failed to resolve app or plan resource ID"
  exit 1
fi

read -r START_TIME END_TIME <<<"$(python3 - <<'PY' "${DURATION}"
from datetime import datetime, timedelta, timezone
import re
import sys

duration = sys.argv[1]
match = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
if not match:
    raise SystemExit('Invalid duration format. Expected like PT1H or PT30M')
hours = int(match.group(1) or 0)
minutes = int(match.group(2) or 0)
seconds = int(match.group(3) or 0)
delta = timedelta(hours=hours, minutes=minutes, seconds=seconds)
end = datetime.now(timezone.utc)
start = end - delta
print(start.isoformat().replace('+00:00', 'Z'), end.isoformat().replace('+00:00', 'Z'))
PY
)"

echo "[collect-metrics] start=${START_TIME} end=${END_TIME}"

az monitor metrics list \
  --resource "${PLAN_ID}" \
  --metric "CpuPercentage,MemoryPercentage" \
  --aggregation "Average Minimum Maximum Total Count" \
  --interval "${INTERVAL}" \
  --start-time "${START_TIME}" \
  --end-time "${END_TIME}" \
  --output json > "${PLAN_METRICS_FILE}"

az monitor metrics list \
  --resource "${APP_ID}" \
  --metric "Requests,AverageResponseTime,Http2xx,Http3xx,Http4xx,Http5xx,HealthCheckStatus" \
  --aggregation "Average Minimum Maximum Total Count" \
  --interval "${INTERVAL}" \
  --start-time "${START_TIME}" \
  --end-time "${END_TIME}" \
  --output json > "${APP_METRICS_FILE}"

python3 - <<'PY' "${PLAN_METRICS_FILE}" "${APP_METRICS_FILE}" "${SUMMARY_CSV}"
import csv
import json
import sys

plan_file, app_file, summary_file = sys.argv[1:4]

def flatten(path, resource_type):
    with open(path, encoding='utf-8') as handle:
        payload = json.load(handle)
    rows = []
    for metric in payload.get('value', []):
        metric_name = (metric.get('name') or {}).get('value', '')
        for series in metric.get('timeseries', []):
            for point in series.get('data', []):
                rows.append({
                    'resource_type': resource_type,
                    'metric': metric_name,
                    'timestamp': point.get('timeStamp', ''),
                    'average': point.get('average', ''),
                    'minimum': point.get('minimum', ''),
                    'maximum': point.get('maximum', ''),
                    'total': point.get('total', ''),
                    'count': point.get('count', ''),
                })
    return rows

rows = flatten(plan_file, 'plan') + flatten(app_file, 'app')
fieldnames = ['resource_type', 'metric', 'timestamp', 'average', 'minimum', 'maximum', 'total', 'count']

with open(summary_file, 'w', newline='', encoding='utf-8') as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f'[collect-metrics] wrote {len(rows)} rows to {summary_file}')
PY

echo "[collect-metrics] plan metrics: ${PLAN_METRICS_FILE}"
echo "[collect-metrics] app metrics:  ${APP_METRICS_FILE}"
echo "[collect-metrics] summary csv:  ${SUMMARY_CSV}"
