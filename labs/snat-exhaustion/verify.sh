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

snat_console_query='AppServiceConsoleLogs
| where TimeGenerated > ago(2h)
| where ResultDescription has_any ("SNAT", "timed out", "timeout", "connection refused", "Cannot assign requested address", "EADDRNOTAVAIL")
| summarize hitCount = count()'

platform_query='AppServicePlatformLogs
| where TimeGenerated > ago(2h)
| where ResultDescription has_any ("SNAT", "outbound", "connection", "failed", "timeout")
| summarize hitCount = count()'

http_query='AppServiceHTTPLogs
| where TimeGenerated > ago(2h)
| where CsUriStem in ("/outbound", "/outbound-fixed")
| summarize highLatencyOr5xx = countif(TimeTaken > 2000 or ScStatus >= 500), total = count()'

snat_console_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$snat_console_query" \
    --query "tables[0].rows[0][0]" \
    --output tsv)

platform_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$platform_query" \
    --query "tables[0].rows[0][0]" \
    --output tsv)

http_symptom_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$http_query" \
    --query "tables[0].rows[0][0]" \
    --output tsv)

total_http_hits=$(az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$http_query" \
    --query "tables[0].rows[0][1]" \
    --output tsv)

snat_console_hits=${snat_console_hits:-0}
platform_hits=${platform_hits:-0}
http_symptom_hits=${http_symptom_hits:-0}
total_http_hits=${total_http_hits:-0}

echo
echo "Observed signal counts (last 2 hours):"
echo "  Console SNAT/timeout/refused signals: $snat_console_hits"
echo "  Platform outbound/timeout signals: $platform_hits"
echo "  HTTP high-latency-or-5xx (/outbound*): $http_symptom_hits"
echo "  HTTP total sampled (/outbound*): $total_http_hits"
echo

if [ "$snat_console_hits" -gt 0 ] || [ "$platform_hits" -gt 0 ] || [ "$http_symptom_hits" -gt 0 ]; then
    echo "✅ Expected SNAT-related symptoms detected. Reproduction appears successful."
else
    echo "⚠️  No strong SNAT-related signals detected yet."
    echo "Run trigger.sh again, wait 2-5 minutes, and rerun verify.sh."
fi
