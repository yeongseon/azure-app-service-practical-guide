#!/usr/bin/env bash

set -euo pipefail

RG="${1:-}"
APP_NAME="${2:-}"
OUTPUT_DIR="${3:-artifacts/raw/kql}"
TIMESPAN="${4:-PT2H}"

if [[ -z "${RG}" || -z "${APP_NAME}" ]]; then
  echo "Usage: $0 <RG> <APP_NAME> [OUTPUT_DIR] [TIMESPAN]"
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

HTTP_LOGS_FILE="${OUTPUT_DIR}/http-logs.json"
CONSOLE_LOGS_FILE="${OUTPUT_DIR}/console-logs.json"
PLATFORM_LOGS_FILE="${OUTPUT_DIR}/platform-logs.json"

APP_ID="$(az webapp show --resource-group "${RG}" --name "${APP_NAME}" --query id --output tsv)"

if [[ -z "${APP_ID}" ]]; then
  echo "[collect-kql] Could not resolve app resource id for ${APP_NAME}"
  exit 1
fi

WORKSPACE_RESOURCE_ID="$(az monitor diagnostic-settings list --resource "${APP_ID}" --query "value[0].workspaceId" --output tsv 2>/dev/null || true)"

if [[ -z "${WORKSPACE_RESOURCE_ID}" || "${WORKSPACE_RESOURCE_ID}" == "None" ]]; then
  WORKSPACE_RESOURCE_ID="$(az monitor log-analytics workspace list --resource-group "${RG}" --query "[0].id" --output tsv 2>/dev/null || true)"
fi

WORKSPACE_ID=""
if [[ -n "${WORKSPACE_RESOURCE_ID}" ]]; then
  if [[ "${WORKSPACE_RESOURCE_ID}" == /subscriptions/* ]]; then
    WORKSPACE_ID="$(az monitor log-analytics workspace show --ids "${WORKSPACE_RESOURCE_ID}" --query customerId --output tsv 2>/dev/null || true)"
  else
    WORKSPACE_ID="${WORKSPACE_RESOURCE_ID}"
  fi
fi

if [[ -z "${WORKSPACE_ID}" || "${WORKSPACE_ID}" == "None" ]]; then
  echo "[collect-kql] Warning: Log Analytics workspace not found. Writing empty files."
  python3 - <<'PY' "${HTTP_LOGS_FILE}" "${CONSOLE_LOGS_FILE}" "${PLATFORM_LOGS_FILE}"
import json
import sys

payload = {
    'error': 'Log Analytics workspace not found for this app/resource group',
    'tables': [],
}
for path in sys.argv[1:]:
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, indent=2)
PY
  exit 0
fi

HTTP_QUERY="AppServiceHTTPLogs | where _ResourceId contains \"${APP_NAME}\" | project TimeGenerated, CsMethod, CsUriStem, ScStatus, TimeTaken, Result | order by TimeGenerated asc"
CONSOLE_QUERY="AppServiceConsoleLogs | where _ResourceId contains \"${APP_NAME}\" | project TimeGenerated, ResultDescription | order by TimeGenerated asc"
PLATFORM_QUERY="AppServicePlatformLogs | where _ResourceId contains \"${APP_NAME}\" | project TimeGenerated, Level, Message | order by TimeGenerated asc"

az monitor log-analytics query \
  --workspace "${WORKSPACE_ID}" \
  --analytics-query "${HTTP_QUERY}" \
  --timespan "${TIMESPAN}" \
  --output json > "${HTTP_LOGS_FILE}"

az monitor log-analytics query \
  --workspace "${WORKSPACE_ID}" \
  --analytics-query "${CONSOLE_QUERY}" \
  --timespan "${TIMESPAN}" \
  --output json > "${CONSOLE_LOGS_FILE}"

az monitor log-analytics query \
  --workspace "${WORKSPACE_ID}" \
  --analytics-query "${PLATFORM_QUERY}" \
  --timespan "${TIMESPAN}" \
  --output json > "${PLATFORM_LOGS_FILE}"

echo "[collect-kql] workspace: ${WORKSPACE_ID}"
echo "[collect-kql] http logs: ${HTTP_LOGS_FILE}"
echo "[collect-kql] console logs: ${CONSOLE_LOGS_FILE}"
echo "[collect-kql] platform logs: ${PLATFORM_LOGS_FILE}"
