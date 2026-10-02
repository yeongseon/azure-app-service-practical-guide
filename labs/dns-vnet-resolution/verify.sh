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
dependency_query='AppDependencies
| where TimeGenerated > ago(2h)
| where Target has "blob.core.windows.net" and Target !has "privatelink"
| summarize failed = countif(Success == false), total = count()'

result=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$dependency_query" \
    --query "[0].[failed, total]" \
    --output tsv | tr -d '\r')

failed=$(echo "$result" | awk '{print $1}')
total=$(echo "$result" | awk '{print $2}')
failed=${failed:-0}
total=${total:-0}

echo
echo "Storage dependency calls via the standard FQDN (last 2 hours): ${failed} failed of ${total}"
echo

if [ "$total" -eq 0 ]; then
    echo "No dependency telemetry yet. Run trigger.sh, wait 2-5 minutes for ingestion, then re-run."
    exit 1
elif [ "$failed" -gt 0 ]; then
    echo "Reproduction observed: storage calls are failing while the app keeps returning 200."
    echo "Confirm the cause by checking which address the name resolves to (/resolve) and the zone's VNet links."
else
    echo "All storage calls succeeded: the private path is working (expected after linking the zone)."
fi
