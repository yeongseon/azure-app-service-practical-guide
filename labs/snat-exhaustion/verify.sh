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

run_query() {
    az monitor log-analytics query \
        --workspace "$WORKSPACE_ID" \
        --analytics-query "$1" \
        --output table | tr -d '\r'
}

# Outbound calls by result code. A 4xx from the target is recorded with
# Success == false, so "failed" alone does not mean the connection failed:
# connection-level failures (for example connect timeouts) are recorded with ResultCode 0.
echo
echo "== Outbound dependency calls by result code (last 2 hours)"
run_query 'AppDependencies
| where TimeGenerated > ago(2h)
| summarize calls = count(), p50Ms = round(percentile(DurationMs, 50)), p95Ms = round(percentile(DurationMs, 95)) by ResultCode'

echo
echo "== Inbound time per endpoint (last 2 hours)"
run_query 'AppServiceHTTPLogs
| where TimeGenerated > ago(2h)
| where CsUriStem in ("/outbound", "/outbound-fixed")
| summarize requests = count(), s5xx = countif(ScStatus >= 500), p50Ms = percentile(TimeTaken, 50), p95Ms = percentile(TimeTaken, 95) by CsUriStem, ScStatus'

echo
echo "== Console timeout and socket error signatures (last 2 hours)"
run_query 'AppServiceConsoleLogs
| where TimeGenerated > ago(2h)
| where ResultDescription has_any ("SNAT", "timed out", "WORKER TIMEOUT", "SIGKILL", "Cannot assign requested address", "EADDRNOTAVAIL")
| summarize hits = count()'

cat <<'GUIDE'

How to read this:
  - Connection-level failures (ResultCode 0, timeouts, EADDRNOTAVAIL) are
    the outbound signal consistent with SNAT pressure. Zero of them means SNAT
    exhaustion was not reproduced, whatever the inbound latency looks like.
  - High inbound time on /outbound with fast, successful dependency calls points
    at worker saturation from per-call connection setup, not at SNAT.
  - Confirm SNAT with the "SNAT Port Exhaustion" detector. On Basic plans it
    only reports that the tier is non-production and gives no port data.
GUIDE
