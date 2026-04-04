#!/bin/bash
set -euo pipefail

RESOURCE_GROUP_NAME="${1:-}"

if [ -z "$RESOURCE_GROUP_NAME" ]; then
    echo "Usage: $0 <RESOURCE_GROUP_NAME>"
    exit 1
fi

WORKSPACE_ID=$(az monitor log-analytics workspace list \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query "[0].customerId" \
    --output tsv)

if [ -z "$WORKSPACE_ID" ]; then
    echo "No Log Analytics workspace found in resource group: $RESOURCE_GROUP_NAME"
    exit 1
fi

echo "Using Log Analytics workspace ID: $WORKSPACE_ID"

disk_query='AppServiceConsoleLogs
| where TimeGenerated > ago(2h)
| where ResultDescription has_any ("No space left", "ENOSPC", "disk", "NoSpaceLeftOnDevice")
| project TimeGenerated, ResultDescription
| order by TimeGenerated desc'

hit_count_query='AppServiceConsoleLogs
| where TimeGenerated > ago(2h)
| where ResultDescription has_any ("No space left", "ENOSPC", "disk", "NoSpaceLeftOnDevice")
| summarize hitCount = count()'

disk_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$hit_count_query" \
    --query "tables[0].rows[0][0]" \
    --output tsv)

disk_hits=${disk_hits:-0}

echo
echo "Observed disk-pressure signal count (last 2 hours): $disk_hits"
echo

az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$disk_query" \
    --output table

echo
if [ "$disk_hits" -gt 0 ]; then
    echo "✅ Expected disk-pressure symptoms detected. Reproduction appears successful."
else
    echo "⚠️  No expected disk-pressure symptoms detected yet."
    echo "Try running trigger.sh again, then wait 2-5 minutes and re-run verify.sh."
fi
