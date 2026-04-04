#!/bin/bash
set -euo pipefail

RESOURCE_GROUP_NAME="${1:-rg-lab-forward}"

WORKSPACE_ID=$(az monitor log-analytics workspace list \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query "[0].customerId" \
    --output tsv)

if [ -z "$WORKSPACE_ID" ]; then
    echo "No Log Analytics workspace found in resource group: $RESOURCE_GROUP_NAME"
    exit 1
fi

echo "Using Log Analytics workspace ID: $WORKSPACE_ID"

platform_query=$'AppServicePlatformLogs\n| where TimeGenerated > ago(2h)\n| where ResultDescription has_any ("Failed to forward request", "Container didn\'t respond")\n| summarize hitCount = count()'

http_503_query='AppServiceHTTPLogs
| where TimeGenerated > ago(2h)
| where ScStatus == 503
| summarize hitCount = count()'

platform_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$platform_query" \
    --query "tables[0].rows[0][0]" \
    --output tsv)

http_503_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$http_503_query" \
    --query "tables[0].rows[0][0]" \
    --output tsv)

platform_hits=${platform_hits:-0}
http_503_hits=${http_503_hits:-0}

echo
echo "Observed signal counts (last 2 hours):"
echo "  Platform forwarder/container response signals: $platform_hits"
echo "  HTTP 503 responses: $http_503_hits"
echo

if [ "$platform_hits" -gt 0 ] || [ "$http_503_hits" -gt 0 ]; then
    echo "✅ Expected symptoms detected. Reproduction appears successful."
else
    echo "⚠️  No expected symptoms detected yet."
    echo "Run trigger.sh, wait 2-5 minutes, then run verify.sh again."
fi
