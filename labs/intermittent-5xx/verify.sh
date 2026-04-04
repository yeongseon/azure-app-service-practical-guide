#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <RESOURCE_GROUP_NAME>"
    echo "Example: $0 rg-lab-5xx"
    exit 1
fi

RESOURCE_GROUP_NAME="$1"

WORKSPACE_CUSTOMER_ID="$(az monitor log-analytics workspace list \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query "[0].customerId" \
    --output tsv)"

if [[ -z "$WORKSPACE_CUSTOMER_ID" ]]; then
    echo "No Log Analytics workspace found in resource group: $RESOURCE_GROUP_NAME"
    exit 1
fi

echo "Using Log Analytics workspace customer ID: $WORKSPACE_CUSTOMER_ID"
echo

HTTP_QUERY="AppServiceHTTPLogs
| where TimeGenerated > ago(1h)
| summarize totalRequests=count(), errors5xx=countif(ScStatus >= 500), avgTimeTakenMs=avg(TimeTaken) by CsUriStem
| order by errors5xx desc"

TIMEOUT_QUERY="AppServiceConsoleLogs
| where TimeGenerated > ago(1h)
| where tostring(pack_all()) has \"WORKER TIMEOUT\"
| summarize timeoutEvents=count(), latestEvent=max(TimeGenerated)"

echo "=== HTTP status and latency by endpoint (last 1 hour) ==="
az monitor log-analytics query \
    --workspace "$WORKSPACE_CUSTOMER_ID" \
    --analytics-query "$HTTP_QUERY" \
    --output table

echo
echo "=== Gunicorn WORKER TIMEOUT signals (last 1 hour) ==="
az monitor log-analytics query \
    --workspace "$WORKSPACE_CUSTOMER_ID" \
    --analytics-query "$TIMEOUT_QUERY" \
    --output table

echo
echo "Verification complete. If errors5xx > 0 and timeoutEvents > 0, the lab signal is reproduced."
