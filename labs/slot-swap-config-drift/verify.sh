#!/bin/bash
set -euo pipefail

RESOURCE_GROUP="${1:-rg-lab-slotsw}"
APP_NAME="${2:-}"
WORKSPACE_ID="${3:-}"

if [ -z "${APP_NAME}" ]; then
    APP_NAME=$(az webapp list \
        --resource-group "${RESOURCE_GROUP}" \
        --query "[0].name" \
        --output tsv)
fi

if [ -z "${APP_NAME}" ] || [ "${APP_NAME}" = "null" ]; then
    echo "Unable to determine app name in resource group: ${RESOURCE_GROUP}"
    echo "Usage: bash labs/slot-swap-config-drift/verify.sh <resource-group> <app-name> <workspace-resource-id>"
    exit 1
fi

if [ -z "${WORKSPACE_ID}" ]; then
    WORKSPACE_ID=$(az monitor diagnostic-settings list \
        --resource "$(az webapp show --resource-group "${RESOURCE_GROUP}" --name "${APP_NAME}" --query "id" --output tsv)" \
        --query "value[0].workspaceId" \
        --output tsv)
fi

if [ -z "${WORKSPACE_ID}" ] || [ "${WORKSPACE_ID}" = "null" ]; then
    echo "Unable to determine Log Analytics workspace resource ID."
    echo "Pass it explicitly as the third argument."
    exit 1
fi

echo "Using resource group: ${RESOURCE_GROUP}"
echo "Using app name: ${APP_NAME}"
echo "Using workspace resource ID: ${WORKSPACE_ID}"

SWAP_QUERY=$(cat <<EOF
AppServicePlatformLogs
| where TimeGenerated > ago(2h)
| where _ResourceId has "/sites/${APP_NAME}"
| where ResultDescription has_any ("swap", "slot")
| project TimeGenerated, _ResourceId, ResultDescription
| order by TimeGenerated desc
EOF
)

RESTART_QUERY=$(cat <<EOF
AppServicePlatformLogs
| where TimeGenerated > ago(2h)
| where _ResourceId has "/sites/${APP_NAME}"
| where ResultDescription has_any (
    "restart",
    "recycle",
    "stopping site",
    "starting site",
    "container start",
    "container started"
)
| project TimeGenerated, _ResourceId, ResultDescription
| order by TimeGenerated desc
EOF
)

echo
echo "Swap-related platform events"
az monitor log-analytics query \
    --workspace "${WORKSPACE_ID}" \
    --analytics-query "${SWAP_QUERY}" \
    --timespan P2D \
    --output table

echo
echo "Restart-related platform events"
az monitor log-analytics query \
    --workspace "${WORKSPACE_ID}" \
    --analytics-query "${RESTART_QUERY}" \
    --timespan P2D \
    --output table
