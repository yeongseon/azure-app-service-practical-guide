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

# This script is a collector. It reports counts and does not decide whether
# SNAT exhaustion was reproduced.
#
# The previous version printed "Reproduction appears successful" whenever any
# one of these counters was above zero. Two of them are non-specific: the HTTP
# counter is `TimeTaken > 2000 or ScStatus >= 500`, so any slow response or any
# 5xx from any cause satisfied it. A deployment restart, a cold start or an
# unrelated downstream fault all produced the same "successful reproduction".
# That is symptom evidence being promoted to causal proof.
#
# The counts below are emitted as raw evidence. Whether they support the
# hypothesis is decided by the declared assertions in the run manifest and by
# scripts/golden/evaluate_run.py, which may legitimately answer INCONCLUSIVE.

EVIDENCE_PATH="${EVIDENCE_PATH:-./evidence.json}"
cat > "$EVIDENCE_PATH" <<JSON
{
  "console_snat_timeout_refused_hits": ${snat_console_hits},
  "platform_outbound_timeout_hits": ${platform_hits},
  "http_high_latency_or_5xx_hits": ${http_symptom_hits},
  "http_total_sampled": ${total_http_hits},
  "window": "last 2 hours",
  "evidence_role": "symptom",
  "causal_claim": null
}
JSON

echo "Raw signal counts written to ${EVIDENCE_PATH}."
echo
echo "These are symptom counts. They do not identify a cause:"
echo "  - the HTTP counter matches any response over 2000 ms or any 5xx,"
echo "    whatever produced it;"
echo "  - connection-level exhaustion is the discriminating signal and is"
echo "    reported by the workload as transportFailure, not by these counters."
echo
echo "Evaluate the declared assertions instead of reading a verdict here:"
echo "  python3 scripts/golden/evaluate_run.py <run-dir>"
