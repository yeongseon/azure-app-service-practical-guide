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

count_query='AppServiceConsoleLogs
| where TimeGenerated > ago(2h)
| where ResultDescription has_any ("ModuleNotFoundError", "wrong_module", "No module named")
| summarize hitCount = count()'

details_query='AppServiceConsoleLogs
| where TimeGenerated > ago(2h)
| where ResultDescription has_any ("ModuleNotFoundError", "wrong_module", "No module named")
| project TimeGenerated, ResultDescription
| order by TimeGenerated desc
| take 20'

startup_failure_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$count_query" \
    --query "tables[0].rows[0][0]" \
    --output tsv)

startup_failure_hits=${startup_failure_hits:-0}

echo
echo "Observed startup-failure console signals (last 2 hours): $startup_failure_hits"
echo

az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$details_query" \
    --output table

echo
if [ "$startup_failure_hits" -gt 0 ]; then
    echo "✅ Expected startup failure evidence detected."
else
    echo "⚠️ No startup-failure evidence found yet."
    echo "Run trigger.sh first, then wait 2-5 minutes and re-run verify.sh."
fi
