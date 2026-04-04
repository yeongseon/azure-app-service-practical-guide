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

dns_console_query='AppServiceConsoleLogs
| where TimeGenerated > ago(2h)
| where ResultDescription has_any ("DNS", "resolve", "Name or service not known", "getaddrinfo")
| summarize hitCount = count()'

http_5xx_query='AppServiceHTTPLogs
| where TimeGenerated > ago(2h)
| where ScStatus >= 500
| summarize hitCount = count()'

dns_console_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$dns_console_query" \
    --query "tables[0].rows[0][0]" \
    --output tsv)

http_5xx_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$http_5xx_query" \
    --query "tables[0].rows[0][0]" \
    --output tsv)

dns_console_hits=${dns_console_hits:-0}
http_5xx_hits=${http_5xx_hits:-0}

echo
echo "Observed signal counts (last 2 hours):"
echo "  DNS-related console log hits: $dns_console_hits"
echo "  HTTP 5xx log hits: $http_5xx_hits"
echo

if [ "$dns_console_hits" -gt 0 ] || [ "$http_5xx_hits" -gt 0 ]; then
    echo "✅ Expected DNS misconfiguration symptoms detected. Reproduction appears successful."
else
    echo "⚠️  No expected DNS symptoms detected yet."
    echo "Run trigger.sh again, wait 2-5 minutes, then re-run verify.sh."
fi
