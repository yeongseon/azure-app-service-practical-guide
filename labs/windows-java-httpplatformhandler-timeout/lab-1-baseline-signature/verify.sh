#!/bin/bash
set -euo pipefail

# verify.sh: Lab 1 KQL-based analysis and H1R/H2R/H3R/H4/H5R verdict writer.
#
# Log Analytics has ~2-5 minute ingestion latency, so this script waits
# WAIT_MINS (default 5) before querying. Override with --wait-mins N.

if [[ $# -lt 3 ]]; then
    echo "Usage: $0 <APP_NAME> <RESOURCE_GROUP_NAME> <LOG_ANALYTICS_WORKSPACE_NAME> [OUTPUT_DIR] [--wait-mins N]"
    echo "Example: $0 app-winjavatimeoutl1-abcd rg-lab-winjavatimeoutl1 law-winjavatimeoutl1-abcd ./results"
    echo "Example (skip wait): $0 ... ./results --wait-mins 0"
    exit 1
fi

APP_NAME="$1"
RESOURCE_GROUP_NAME="$2"
LAW_NAME="$3"
shift 3

OUTPUT_DIR=""
WAIT_MINS=5
while [[ $# -gt 0 ]]; do
    case "$1" in
        --wait-mins)
            WAIT_MINS="$2"
            shift 2
            ;;
        *)
            if [[ -z "$OUTPUT_DIR" ]]; then
                OUTPUT_DIR="$1"
                shift
            else
                echo "ERROR: unexpected argument: $1"
                exit 1
            fi
            ;;
    esac
done

if [[ -z "$OUTPUT_DIR" ]]; then
    echo "ERROR: OUTPUT_DIR is required"
    exit 1
fi

if [[ ! -d "$OUTPUT_DIR" ]]; then
    echo "ERROR: OUTPUT_DIR does not exist: $OUTPUT_DIR"
    exit 1
fi

E1_CSV="${OUTPUT_DIR}/e1-signature-probes.csv"
E3_CSV="${OUTPUT_DIR}/e3-stream-probe.csv"
E2_MANIFEST="${OUTPUT_DIR}/e2-kudu-fetch-manifest.csv"
E2_GREP="${OUTPUT_DIR}/e2-httpplatform-grep.log"
VERIFY_REPORT="${OUTPUT_DIR}/verify-report.md"

if [[ ! -f "$E1_CSV" ]]; then
    echo "ERROR: E1 CSV not found: $E1_CSV. Run run-e1-signature-probe.sh first."
    exit 1
fi

echo "=== Lab 1 verify.sh ==="
echo "  App:            $APP_NAME"
echo "  RG:             $RESOURCE_GROUP_NAME"
echo "  Workspace name: $LAW_NAME"
echo "  Output dir:     $OUTPUT_DIR"
echo "  Wait:           ${WAIT_MINS} min (Log Analytics ingestion)"
echo

echo "Step 1: Resolve workspace customer ID (GUID)"
WORKSPACE_ID="$(az monitor log-analytics workspace show \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --workspace-name "$LAW_NAME" \
    --query customerId --output tsv)"
if [[ -z "$WORKSPACE_ID" ]]; then
    echo "ERROR: could not resolve workspace customer ID"
    exit 1
fi
echo "  workspace_id: $WORKSPACE_ID"

if [[ $WAIT_MINS -gt 0 ]]; then
    echo
    echo "Step 2: Wait ${WAIT_MINS} min for Log Analytics ingestion"
    for min in $(seq 1 "$WAIT_MINS"); do
        sleep 60
        echo "  waited ${min}/${WAIT_MINS} min"
    done
else
    echo
    echo "Step 2: Skipped (--wait-mins 0)"
fi

# Derive time bounds from CSV timestamps. Widen by 5 min on each side so
# KQL captures any log rows emitted slightly before the first probe or
# after the last one.
E1_START="$(tail -n +2 "$E1_CSV" | head -1 | cut -d',' -f6)"
E1_END="$(tail -n 1 "$E1_CSV" | cut -d',' -f7)"
E3_START=""
E3_END=""
if [[ -f "$E3_CSV" ]]; then
    E3_START="$(tail -n +2 "$E3_CSV" | head -1 | cut -d',' -f7)"
    E3_END="$(tail -n +2 "$E3_CSV" | head -1 | cut -d',' -f8)"
fi

echo
echo "Step 3: Query time bounds"
echo "  E1: $E1_START -> $E1_END"
if [[ -n "$E3_START" ]]; then
    echo "  E3: $E3_START -> $E3_END"
else
    echo "  E3: (skipped, e3-stream-probe.csv not present)"
fi

# Widen the query window by 5 min on each side. The az CLI accepts KQL
# datetime literals in ISO-8601 form; we compute broadened bounds in the
# same format via `date -u -d`.
widen_start() {
    date -u -d "$1 - 5 minutes" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
        || date -u -j -v-5M -f "%Y-%m-%dT%H:%M:%SZ" "$1" +%Y-%m-%dT%H:%M:%SZ
}
widen_end() {
    date -u -d "$1 + 5 minutes" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
        || date -u -j -v+5M -f "%Y-%m-%dT%H:%M:%SZ" "$1" +%Y-%m-%dT%H:%M:%SZ
}

E1_START_W="$(widen_start "$E1_START")"
E1_END_W="$(widen_end "$E1_END")"

echo
echo "Step 4: Query E1 per-request AppServiceHTTPLogs rows"
# Extract E1 endpoint from CSV so KQL excludes warm-up requests
# (warm-up.sh uses /slow/2, E1 iterations use /slow/${REQUESTED_SECONDS}).
# CSV column 2 is requested_seconds.
E1_ENDPOINT="/slow/$(tail -n +2 "$E1_CSV" | head -1 | cut -d',' -f2)"
E1_HTTP_JSON="${OUTPUT_DIR}/verify-e1-http-rows.json"
KQL_E1_ROWS=$(cat <<KQL
AppServiceHTTPLogs
| where TimeGenerated between (datetime('$E1_START_W') .. datetime('$E1_END_W'))
| where CsUriStem == "$E1_ENDPOINT"
| project TimeGenerated, CsUriStem, ScStatus, ScSubStatus, ScWin32Status, TimeTaken, CsBytes, ScBytes
| order by TimeGenerated asc
KQL
)
az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$KQL_E1_ROWS" \
    --output json > "$E1_HTTP_JSON"
E1_ROW_COUNT="$(python3 -c 'import json; d=json.load(open("'"$E1_HTTP_JSON"'")); print(len(d))')"
echo "  Retrieved $E1_ROW_COUNT AppServiceHTTPLogs rows for $E1_ENDPOINT"

echo
echo "Step 5: Query E1 summary statistics"
E1_STATS_JSON="${OUTPUT_DIR}/verify-e1-stats.json"
KQL_E1_STATS=$(cat <<KQL
AppServiceHTTPLogs
| where TimeGenerated between (datetime('$E1_START_W') .. datetime('$E1_END_W'))
| where CsUriStem == "$E1_ENDPOINT"
| summarize 
    row_count=count(),
    mean_TimeTaken=avg(TimeTaken),
    stdev_TimeTaken=stdev(TimeTaken),
    min_TimeTaken=min(TimeTaken),
    max_TimeTaken=max(TimeTaken),
    win32_zero_count=countif(ScWin32Status == 0),
    win32_64_count=countif(ScWin32Status == 64),
    status_500_121_count=countif(ScStatus == 500 and ScSubStatus == 121)
KQL
)
az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "$KQL_E1_STATS" \
    --output json > "$E1_STATS_JSON"

E1_STATS_VARS="$(python3 -c '
import json
d = json.load(open("'"$E1_STATS_JSON"'"))
if not d:
    print("E1_ROWS=0"); print("MEAN=0"); print("STDEV=0"); print("MIN=0"); print("MAX=0")
    print("WIN32_ZERO=0"); print("WIN32_64=0"); print("STATUS_500_121=0")
else:
    r = d[0]
    print("E1_ROWS={}".format(r.get("row_count", 0)))
    print("MEAN={}".format(r.get("mean_TimeTaken") or 0))
    print("STDEV={}".format(r.get("stdev_TimeTaken") or 0))
    print("MIN={}".format(r.get("min_TimeTaken") or 0))
    print("MAX={}".format(r.get("max_TimeTaken") or 0))
    print("WIN32_ZERO={}".format(r.get("win32_zero_count", 0)))
    print("WIN32_64={}".format(r.get("win32_64_count", 0)))
    print("STATUS_500_121={}".format(r.get("status_500_121_count", 0)))
')"
eval "$E1_STATS_VARS"

echo "  rows: $E1_ROWS  mean: $MEAN ms  stdev: $STDEV ms  min: $MIN  max: $MAX"
echo "  ScStatus/ScSubStatus 500/121: $STATUS_500_121 / $E1_ROWS"
echo "  ScWin32Status ==  0: $WIN32_ZERO / $E1_ROWS"
echo "  ScWin32Status == 64: $WIN32_64  / $E1_ROWS"

# H1R success criteria (per design-proposal.md):
# - ScStatus/ScSubStatus = 500/121 in 100% of iterations
# - mean TimeTaken in [229800, 230500] ms with stddev < 200 ms
H1R_VERDICT="unknown"
H1R_REASONS=()
if [[ $E1_ROWS -gt 0 ]]; then
    if [[ "$STATUS_500_121" -eq "$E1_ROWS" ]]; then
        H1R_REASONS+=("500/121 = 100% ($STATUS_500_121/$E1_ROWS)")
        MEAN_INT=$(python3 -c "print(int(round(float('$MEAN'))))")
        STDEV_INT=$(python3 -c "print(int(round(float('$STDEV'))))")
        if [[ $MEAN_INT -ge 229800 && $MEAN_INT -le 230500 && $STDEV_INT -lt 200 ]]; then
            H1R_VERDICT="CONFIRMED"
            H1R_REASONS+=("mean $MEAN_INT ms in [229800, 230500], stdev $STDEV_INT < 200")
        else
            H1R_VERDICT="PARTIAL"
            H1R_REASONS+=("mean $MEAN_INT ms or stdev $STDEV_INT outside acceptance window")
        fi
    else
        H1R_VERDICT="FALSIFIED"
        H1R_REASONS+=("500/121 only $STATUS_500_121/$E1_ROWS iterations")
    fi
fi

# H2R success criterion (per design-proposal.md):
# - ScWin32Status = 0 in 100% of iterations
# - Any single .64 -> anomaly, recommend extension to MAX_ITERATIONS=20
H2R_VERDICT="unknown"
H2R_REASONS=()
if [[ $E1_ROWS -gt 0 ]]; then
    if [[ "$WIN32_ZERO" -eq "$E1_ROWS" && "$WIN32_64" -eq 0 ]]; then
        H2R_VERDICT="CONFIRMED"
        H2R_REASONS+=("ScWin32Status = 0 in 100% ($WIN32_ZERO/$E1_ROWS), zero .64")
    else
        H2R_VERDICT="FALSIFIED"
        H2R_REASONS+=("ScWin32Status distribution: zero=$WIN32_ZERO 64=$WIN32_64 total=$E1_ROWS")
        if [[ "$WIN32_64" -gt 0 && $E1_ROWS -lt 20 ]]; then
            H2R_REASONS+=("*** Trigger fired: recommend re-run with ITERATIONS=20 ***")
        fi
    fi
fi

echo
echo "Step 6: Grep E2 artifacts for httpPlatform + requestTimeout"
H3R_VERDICT="unknown"
H3R_REASONS=()
if [[ ! -f "$E2_MANIFEST" ]]; then
    H3R_VERDICT="skipped"
    H3R_REASONS+=("E2 manifest not present ($E2_MANIFEST)")
else
    HTTP_200_COUNT="$(tail -n +2 "$E2_MANIFEST" | awk -F, '$4 == "200"' | wc -l | tr -d ' ')"
    REQUEST_TIMEOUT_HIT="$(grep -iE 'requestTimeout' "$E2_GREP" 2>/dev/null | grep -vE '\(no matches\)' | head -1 || true)"
    if [[ -n "$REQUEST_TIMEOUT_HIT" ]]; then
        H3R_VERDICT="CONFIRMED-OR-PARTIAL"
        H3R_REASONS+=("requestTimeout marker found: $REQUEST_TIMEOUT_HIT")
        H3R_REASONS+=("Manual review required: >= 230000 -> CONFIRMED, < 230000 -> PARTIAL")
    elif [[ $HTTP_200_COUNT -eq 0 ]]; then
        H3R_VERDICT="FALSIFIED"
        H3R_REASONS+=("0/7 Kudu probes returned HTTP 200; effective config not Kudu-accessible")
    else
        H3R_VERDICT="FALSIFIED"
        H3R_REASONS+=("$HTTP_200_COUNT/7 probes returned HTTP 200 but none contained requestTimeout marker")
    fi
fi

echo "  E2 verdict: $H3R_VERDICT"

echo
echo "Step 7: Query E3 stream request + console logs"
H4_VERDICT="unknown"
H4_REASONS=()
if [[ -z "$E3_START" ]]; then
    H4_VERDICT="skipped"
    H4_REASONS+=("E3 CSV not present; run run-e3-stream-test.sh")
else
    E3_START_W="$(widen_start "$E3_START")"
    E3_END_W="$(widen_end "$E3_END")"
    E3_HTTP_JSON="${OUTPUT_DIR}/verify-e3-http-rows.json"
    E3_CONSOLE_JSON="${OUTPUT_DIR}/verify-e3-console-rows.json"

    KQL_E3_HTTP=$(cat <<KQL
AppServiceHTTPLogs
| where TimeGenerated between (datetime('$E3_START_W') .. datetime('$E3_END_W'))
| where CsUriStem startswith "/stream/"
| project TimeGenerated, CsUriStem, ScStatus, ScSubStatus, ScWin32Status, TimeTaken, CsBytes, ScBytes
KQL
)
    az monitor log-analytics query \
        --workspace "$WORKSPACE_ID" \
        --analytics-query "$KQL_E3_HTTP" \
        --output json > "$E3_HTTP_JSON"

    KQL_E3_CONSOLE=$(cat <<KQL
AppServiceConsoleLogs
| where TimeGenerated between (datetime('$E3_START_W') .. datetime('$E3_END_W'))
| where ResultDescription has_any ("stream.start", "stream.end", "stream.interrupted")
| project TimeGenerated, ResultDescription
| order by TimeGenerated asc
KQL
)
    az monitor log-analytics query \
        --workspace "$WORKSPACE_ID" \
        --analytics-query "$KQL_E3_CONSOLE" \
        --output json > "$E3_CONSOLE_JSON"

    E3_STATS="$(python3 -c '
import json
rows = json.load(open("'"$E3_HTTP_JSON"'"))
if not rows:
    print("E3_HTTP_ROWS=0"); print("E3_TIME_TAKEN=0"); print("E3_SC_STATUS=0"); print("E3_SC_SUB=0")
else:
    r = rows[0]
    print("E3_HTTP_ROWS={}".format(len(rows)))
    print("E3_TIME_TAKEN={}".format(r.get("TimeTaken") or 0))
    print("E3_SC_STATUS={}".format(r.get("ScStatus") or 0))
    print("E3_SC_SUB={}".format(r.get("ScSubStatus") or 0))
')"
    eval "$E3_STATS"
    CLIENT_CHUNKS="$(tail -n +2 "$E3_CSV" | head -1 | cut -d',' -f6)"

    echo "  E3 HTTP rows: $E3_HTTP_ROWS  TimeTaken: ${E3_TIME_TAKEN} ms  ScStatus: $E3_SC_STATUS  ScSubStatus: $E3_SC_SUB  client chunks: $CLIENT_CHUNKS"

    E3_TIME_INT="$(python3 -c "print(int(round(float('$E3_TIME_TAKEN'))))")"
    if [[ $E3_TIME_INT -ge 225000 && $E3_TIME_INT -le 235000 && "$E3_SC_STATUS" == "500" && "$E3_SC_SUB" == "121" && "$CLIENT_CHUNKS" -ge 7 && "$CLIENT_CHUNKS" -le 9 ]]; then
        H4_VERDICT="ABSOLUTE"
        H4_REASONS+=("TimeTaken ${E3_TIME_INT} ms near 230000, ScStatus/ScSubStatus=500/121, chunks $CLIENT_CHUNKS in [7,9]")
    elif [[ $E3_TIME_INT -ge 290000 && $E3_TIME_INT -le 320000 && "$E3_SC_STATUS" == "200" && "$CLIENT_CHUNKS" -eq 11 ]]; then
        H4_VERDICT="IDLE"
        H4_REASONS+=("TimeTaken ${E3_TIME_INT} ms near 300000, ScStatus=200, all 11 chunks received")
    else
        H4_VERDICT="AMBIGUOUS"
        H4_REASONS+=("TimeTaken=$E3_TIME_INT ms, ScStatus/ScSubStatus=$E3_SC_STATUS/$E3_SC_SUB, chunks=$CLIENT_CHUNKS")
    fi
fi

H5R_VERDICT="unknown"
H5R_REASONS=()
CLIENT_500_COUNT="$(tail -n +2 "$E1_CSV" | awk -F, '$3 == "500"' | wc -l | tr -d ' ')"
CLIENT_502_COUNT="$(tail -n +2 "$E1_CSV" | awk -F, '$3 == "502"' | wc -l | tr -d ' ')"
CLIENT_TOTAL="$(tail -n +2 "$E1_CSV" | wc -l | tr -d ' ')"
if [[ "$CLIENT_502_COUNT" -eq 0 && "$CLIENT_500_COUNT" -eq "$CLIENT_TOTAL" ]]; then
    H5R_VERDICT="CONFIRMED"
    H5R_REASONS+=("Client sees 500 in $CLIENT_500_COUNT/$CLIENT_TOTAL iterations, zero 502 (direct App Service request path)")
elif [[ "$CLIENT_502_COUNT" -gt 0 ]]; then
    H5R_VERDICT="FALSIFIED"
    H5R_REASONS+=("Client sees 502 in $CLIENT_502_COUNT/$CLIENT_TOTAL iterations on direct App Service request")
else
    H5R_VERDICT="MIXED"
    H5R_REASONS+=("Client code distribution: 500=$CLIENT_500_COUNT 502=$CLIENT_502_COUNT total=$CLIENT_TOTAL")
fi

echo
echo "=== Writing verify report to $VERIFY_REPORT ==="
{
    echo "# Lab 1 verify report"
    echo
    echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo
    echo "- App: \`$APP_NAME\`"
    echo "- RG:  \`$RESOURCE_GROUP_NAME\`"
    echo "- Workspace: \`$LAW_NAME\` (customer id \`$WORKSPACE_ID\`)"
    echo "- Output dir: \`$OUTPUT_DIR\`"
    echo
    echo "## E1 baseline signature statistics"
    echo
    echo "| metric | value |"
    echo "|---|---|"
    echo "| row_count (AppServiceHTTPLogs) | $E1_ROWS |"
    echo "| mean TimeTaken (ms) | $MEAN |"
    echo "| stdev TimeTaken (ms) | $STDEV |"
    echo "| min TimeTaken (ms) | $MIN |"
    echo "| max TimeTaken (ms) | $MAX |"
    echo "| ScStatus/ScSubStatus 500/121 count | $STATUS_500_121 / $E1_ROWS |"
    echo "| ScWin32Status == 0 count | $WIN32_ZERO / $E1_ROWS |"
    echo "| ScWin32Status == 64 count | $WIN32_64 / $E1_ROWS |"
    echo
    echo "### H1R verdict: $H1R_VERDICT"
    for r in "${H1R_REASONS[@]}"; do
        echo "- $r"
    done
    echo
    echo "### H2R verdict: $H2R_VERDICT"
    for r in "${H2R_REASONS[@]}"; do
        echo "- $r"
    done
    echo
    echo "## E2 Kudu config visibility"
    echo
    echo "### H3R verdict: $H3R_VERDICT"
    for r in "${H3R_REASONS[@]}"; do
        echo "- $r"
    done
    echo
    if [[ -f "$E2_MANIFEST" ]]; then
        echo "See \`$(basename "$E2_MANIFEST")\` for the 7-probe manifest and \`$(basename "$E2_GREP")\` for grep results."
    fi
    echo
    echo "## E3 stream absolute-vs-idle"
    echo
    if [[ -f "$E3_CSV" ]]; then
        echo "| metric | value |"
        echo "|---|---|"
        echo "| server TimeTaken (ms) | ${E3_TIME_TAKEN:-N/A} |"
        echo "| server ScStatus | ${E3_SC_STATUS:-N/A} |"
        echo "| server ScSubStatus | ${E3_SC_SUB:-N/A} |"
        echo "| client chunks received | ${CLIENT_CHUNKS:-N/A} |"
        echo
    fi
    echo "### H4 verdict: $H4_VERDICT"
    for r in "${H4_REASONS[@]}"; do
        echo "- $r"
    done
    echo
    echo "## E4 (optional) client vs IIS outer status"
    echo
    echo "### H5R verdict: $H5R_VERDICT"
    for r in "${H5R_REASONS[@]}"; do
        echo "- $r"
    done
    echo
    echo "## Raw artifacts"
    echo
    echo "- E1 per-request rows: \`$(basename "$E1_HTTP_JSON")\`"
    echo "- E1 summary stats:    \`$(basename "$E1_STATS_JSON")\`"
    if [[ -n "$E3_START" ]]; then
        echo "- E3 HTTP rows:        \`verify-e3-http-rows.json\`"
        echo "- E3 console rows:     \`verify-e3-console-rows.json\`"
    fi
    echo
    echo "## Next"
    echo
    echo "If H2R = FALSIFIED with \`.64\` present AND E1 ran < 20 iterations, re-run:"
    echo
    echo "\`\`\`bash"
    echo "ITERATIONS=20 bash run-e1-signature-probe.sh https://${APP_NAME}.azurewebsites.net $OUTPUT_DIR"
    echo "bash verify.sh $APP_NAME $RESOURCE_GROUP_NAME $LAW_NAME $OUTPUT_DIR"
    echo "\`\`\`"
    echo
    echo "Otherwise, proceed to \`lab-1-interpretation.md\` authoring."
} > "$VERIFY_REPORT"

echo
echo "=========================================="
echo "H1R verdict: $H1R_VERDICT"
echo "H2R verdict: $H2R_VERDICT"
echo "H3R verdict: $H3R_VERDICT"
echo "H4  verdict: $H4_VERDICT"
echo "H5R verdict: $H5R_VERDICT"
echo "=========================================="
echo
echo "Full report: $VERIFY_REPORT"
