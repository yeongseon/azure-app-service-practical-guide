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
    --output tsv | tr -d '\r')

if [ -z "$WORKSPACE_ID" ]; then
    echo "No Log Analytics workspace found in resource group: $RESOURCE_GROUP_NAME"
    exit 1
fi

echo "Using Log Analytics workspace ID: $WORKSPACE_ID"

# The fault does not produce DNS errors or 5xx: the storage name resolves to a
# public address, the call is rejected, and the app still answers 200. The
# signal lives in Application Insights dependencies (see the DNS playbook).
# Judge the CURRENT state from the most recent call, not a 2-hour total: after
# the zone is linked, earlier 403 rows are still inside any long window.
WINDOW_MINUTES="${2:-15}"
dependency_query="AppDependencies
| where TimeGenerated > ago(${WINDOW_MINUTES}m)
| where Target has \"blob.core.windows.net\" and Target !has \"privatelink\"
| summarize calls = count(), latest = max(TimeGenerated) by ResultCode
| order by latest desc"

rows=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$dependency_query" \
    --query "[].[ResultCode, calls]" \
    --output tsv | tr -d '\r')

echo
echo "Storage calls via the standard FQDN in the last ${WINDOW_MINUTES} minutes (newest result code first):"
if [ -z "$rows" ]; then
    echo "  none"
    echo "No dependency telemetry yet. Run trigger.sh, wait 2-5 minutes for ingestion, then re-run."
    exit 1
fi
echo "$rows" | awk '{printf "  ResultCode %s: %s call(s)\n", $1, $2}'
latest_code=$(echo "$rows" | head -n 1 | awk '{print $1}')
echo

if [ "$latest_code" = "403" ]; then
    echo "Fault reproduced: the latest call was rejected with HTTP 403 while the app keeps returning 200."
    echo "Confirm the cause: /resolve should show a public address, and the zone should have no VNet link."
else
    echo "The latest call returned ${latest_code}, not 403."
    echo "This alone does not prove the private path; check that /resolve now returns the private endpoint address."
fi
