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

memory_query='AppServiceConsoleLogs
| where TimeGenerated > ago(2h)
| where ResultDescription has_any ("OutOfMemory", "OOM", "Killed", "memory", "Cannot allocate memory")
| summarize hitCount = count()'

worker_query='AppServiceConsoleLogs
| where TimeGenerated > ago(2h)
| where ResultDescription has_any ("worker timeout", "Booting worker", "Worker exiting", "SIGKILL", "signal 9")
| summarize hitCount = count()'

platform_query='AppServicePlatformLogs
| where TimeGenerated > ago(2h)
| where ResultDescription has_any ("Restarting", "Container", "stopped", "started", "health")
| summarize hitCount = count()'

memory_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$memory_query" \
    --query "tables[0].rows[0][0]" \
    --output tsv)

worker_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$worker_query" \
    --query "tables[0].rows[0][0]" \
    --output tsv)

platform_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$platform_query" \
    --query "tables[0].rows[0][0]" \
    --output tsv)

memory_hits=${memory_hits:-0}
worker_hits=${worker_hits:-0}
platform_hits=${platform_hits:-0}

echo
echo "Observed signal counts (last 2 hours):"
echo "  Memory-related console signals: $memory_hits"
echo "  Worker timeout/restart console signals: $worker_hits"
echo "  Platform restart/lifecycle signals: $platform_hits"
echo

if [ "$memory_hits" -gt 0 ] || [ "$worker_hits" -gt 0 ] || [ "$platform_hits" -gt 0 ]; then
    echo "✅ Expected symptoms detected. Reproduction appears successful."
else
    echo "⚠️  No expected symptoms detected yet."
    echo "Try running trigger.sh again, then wait 2-5 minutes and re-run verify.sh."
fi
