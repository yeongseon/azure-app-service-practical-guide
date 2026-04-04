#!/bin/bash
set -euo pipefail

RESOURCE_GROUP_NAME="${1:-rg-lab-coldstart}"
APP_NAME_INPUT="${2:-}"

if [ -n "$APP_NAME_INPUT" ]; then
    APP_NAME="$APP_NAME_INPUT"
else
    APP_NAME=$(az webapp list \
        --resource-group "$RESOURCE_GROUP_NAME" \
        --query "[0].name" \
        --output tsv)
fi

if [ -z "$APP_NAME" ]; then
    echo "No App Service found in resource group: $RESOURCE_GROUP_NAME"
    echo "Usage: $0 <RESOURCE_GROUP_NAME> [APP_NAME]"
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

WEBAPP_RESOURCE_ID=$(az webapp show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$APP_NAME" \
    --query "id" \
    --output tsv)

echo "Using app: $APP_NAME"
echo "Using Log Analytics workspace ID: $WORKSPACE_ID"
echo

http_distribution_query="AppServiceHTTPLogs
| where TimeGenerated > ago(2h)
| where _ResourceId =~ '$WEBAPP_RESOURCE_ID'
| summarize requestCount=count(), p50Ms=round(percentile(TimeTaken, 50), 2), p95Ms=round(percentile(TimeTaken, 95), 2), p99Ms=round(percentile(TimeTaken, 99), 2), maxMs=max(TimeTaken)"

http_timeline_query="AppServiceHTTPLogs
| where TimeGenerated > ago(2h)
| where _ResourceId =~ '$WEBAPP_RESOURCE_ID'
| summarize requestCount=count(), avgMs=round(avg(TimeTaken), 2), p95Ms=round(percentile(TimeTaken, 95), 2) by bin(TimeGenerated, 5m)
| order by TimeGenerated desc
| take 12"

platform_start_query="AppServicePlatformLogs
| where TimeGenerated > ago(2h)
| where _ResourceId =~ '$WEBAPP_RESOURCE_ID'
| where ResultDescription has_any ('Container', 'started', 'starting', 'restart', 'Initializing')
| project TimeGenerated, Level, ResultDescription
| order by TimeGenerated desc
| take 30"

echo "HTTP latency distribution (last 2 hours)"
az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$http_distribution_query" \
    --output table

echo
echo "HTTP latency timeline (5-minute bins, last 12 bins)"
az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$http_timeline_query" \
    --output table

echo
echo "Platform lifecycle events (container start/restart signals)"
az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$platform_start_query" \
    --output table

echo
echo "Interpretation: periodic high-latency first requests with start/restart events indicate cold starts, not steady-state code regression."
