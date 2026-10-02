#!/bin/bash
# Report the current private-endpoint path state: does the storage name still
# resolve to the endpoint address, and how did the most recent calls end?
set -euo pipefail

RESOURCE_GROUP_NAME="${1:-}"
WINDOW_MINUTES="${2:-10}"

if [ -z "$RESOURCE_GROUP_NAME" ]; then
    echo "Usage: $0 <RESOURCE_GROUP_NAME> [WINDOW_MINUTES]"
    exit 1
fi

app_host=$(az webapp list \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query "[0].defaultHostName" \
    --output tsv | tr -d '\r')
endpoint_nic=$(az network private-endpoint list \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query "[0].networkInterfaces[0].id" \
    --output tsv | tr -d '\r')
endpoint_ip=$(az network nic show \
    --ids "$endpoint_nic" \
    --query "ipConfigurations[0].privateIPAddress" \
    --output tsv | tr -d '\r')
workspace_id=$(az monitor log-analytics workspace list \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --query "[0].customerId" \
    --output tsv | tr -d '\r')

resolved=$(curl --silent --max-time 30 "https://${app_host}/resolve" \
    | python3 -c "import json,sys; print(','.join(json.load(sys.stdin)['results'][0].get('addresses', [])))")

echo "Private endpoint address: ${endpoint_ip}"
echo "Storage name resolves to: ${resolved:-<no answer>}"
if [ "$resolved" = "$endpoint_ip" ]; then
    echo "DNS layer: correct (private answer). A failure now is on the path, not in DNS."
else
    echo "DNS layer: NOT the endpoint address. Use the DNS lab and playbook first."
fi

dependency_query="AppDependencies
| where TimeGenerated > ago(${WINDOW_MINUTES}m)
| where Target has \"blob.core.windows.net\" and Target !has \"privatelink\"
| summarize calls = count(), p50Ms = round(percentile(DurationMs, 50)), latest = max(TimeGenerated) by ResultCode
| order by latest desc"

rows=$(az monitor log-analytics query \
    --workspace "$workspace_id" \
    --analytics-query "$dependency_query" \
    --query "[].[ResultCode, calls, p50Ms]" \
    --output tsv | tr -d '\r')

echo
echo "Storage calls in the last ${WINDOW_MINUTES} minutes (newest result first):"
if [ -z "$rows" ]; then
    echo "  none yet; run /connect a few times and wait 2-5 minutes for ingestion."
    exit 1
fi
echo "$rows" | awk -F'\t' '{printf "  ResultCode %s: %s call(s), p50 %s ms\n", ($1 == "" ? "<none>" : $1), $2, $3}'
