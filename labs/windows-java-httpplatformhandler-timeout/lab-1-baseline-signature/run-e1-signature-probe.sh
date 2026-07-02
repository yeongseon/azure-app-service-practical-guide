#!/bin/bash
set -euo pipefail

# E1 adaptive baseline signature stability probe (L1-H1R + L1-H2R).
#
# Design (per design-proposal.md revision 2, Oracle-approved):
#
# - Serialized, no overlap. Queue depth stays at 1 throughout.
# - 10 iterations first; extends to MAX_ITERATIONS if any trigger fires
#   (any .64, or ScStatus/ScSubStatus != 500/121 in AppServiceHTTPLogs).
# - Pacing: wait for backend completion (Java Thread.sleep finishes ~10s
#   after client cutoff per Stage 0) + 10s buffer. This shortens the wait
#   versus a fixed 60s while preserving the no-overlap invariant.
#
# Trigger evaluation is deferred to verify.sh because AppServiceHTTPLogs
# ingestion has ~2-5 minute latency; this script cannot reliably read
# post-request rows in-loop. The script always runs BASELINE_ITERATIONS
# and records enough client-side data for verify.sh to decide whether
# extension was needed.

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 <APP_URL> [OUTPUT_DIR]"
    echo "Example: $0 https://app-winjavatimeoutl1-abcd.azurewebsites.net ./results"
    exit 1
fi

APP_URL="$1"
OUTPUT_DIR="${2:-./lab1-results-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUTPUT_DIR"

PROBE_DURATION=240
BASELINE_ITERATIONS=10
MAX_ITERATIONS=20
CURL_MAX_TIME=400
BACKEND_BUFFER_SEC=10
MIN_INTER_PROBE_SLEEP=15

# ITERATIONS is set at invocation time. Operator can override to run the
# extended set unconditionally when replaying against a known-anomalous
# baseline. Default is BASELINE_ITERATIONS; override via ITERATIONS env var.
ITERATIONS="${ITERATIONS:-$BASELINE_ITERATIONS}"
if [[ $ITERATIONS -lt 1 || $ITERATIONS -gt $MAX_ITERATIONS ]]; then
    echo "ERROR: ITERATIONS=$ITERATIONS out of range [1, $MAX_ITERATIONS]"
    exit 1
fi

SIGNATURE_CSV="${OUTPUT_DIR}/e1-signature-probes.csv"
E1_SUMMARY="${OUTPUT_DIR}/e1-summary.md"

echo "=== E1 baseline signature probe: $APP_URL ==="
echo "  Output dir:      $OUTPUT_DIR"
echo "  Endpoint:        /slow/${PROBE_DURATION}"
echo "  Iterations:      $ITERATIONS (baseline=${BASELINE_ITERATIONS}, max=${MAX_ITERATIONS})"
echo "  curl --max-time: ${CURL_MAX_TIME}s"
echo "  Pacing:          backend completion (Thread.sleep ends ~10s after client cut) + ${BACKEND_BUFFER_SEC}s buffer"
echo

echo "iteration_index,requested_seconds,http_code,time_total_sec,curl_exit_code,started_utc,ended_utc,paced_sleep_sec" > "$SIGNATURE_CSV"

echo "Running $ITERATIONS iterations of /slow/${PROBE_DURATION}"

for i in $(seq 1 "$ITERATIONS"); do
    STARTED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    START_EPOCH=$(date +%s)
    set +e
    RESULT="$(curl --silent --output /dev/null \
        --max-time "$CURL_MAX_TIME" \
        --write-out '%{http_code},%{time_total}' \
        "${APP_URL}/slow/${PROBE_DURATION}")"
    CURL_EXIT=$?
    set -e
    ENDED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    END_EPOCH=$(date +%s)

    if [[ -z "$RESULT" ]]; then
        HTTP_CODE="000"
        TIME_TOTAL="$((END_EPOCH - START_EPOCH))"
    else
        HTTP_CODE="$(echo "$RESULT" | cut -d',' -f1)"
        TIME_TOTAL="$(echo "$RESULT" | cut -d',' -f2)"
    fi

    # Backend-completion-safe pacing. Stage 0 measured orphan Java work
    # continuing 240016 ms after a 240s /slow request started, i.e. ~10s
    # after the client cutoff. Formula: remaining = PROBE_DURATION - client_elapsed + BUFFER.
    BACKEND_REMAINING="$(awk -v d="$PROBE_DURATION" -v t="$TIME_TOTAL" -v b="$BACKEND_BUFFER_SEC" \
        'BEGIN { r = d - t + b; if (r < 0) r = 0; printf "%d", r }')"
    if [[ $BACKEND_REMAINING -gt $MIN_INTER_PROBE_SLEEP ]]; then
        SLEEP_FOR=$BACKEND_REMAINING
    else
        SLEEP_FOR=$MIN_INTER_PROBE_SLEEP
    fi

    echo "${i},${PROBE_DURATION},${HTTP_CODE},${TIME_TOTAL},${CURL_EXIT},${STARTED_UTC},${ENDED_UTC},${SLEEP_FOR}" >> "$SIGNATURE_CSV"
    echo "  iter ${i}/${ITERATIONS}: http=${HTTP_CODE} time=${TIME_TOTAL}s curl_exit=${CURL_EXIT} pacing_sleep=${SLEEP_FOR}s"

    if [[ $i -lt $ITERATIONS ]]; then
        sleep "$SLEEP_FOR"
    fi
done

echo
echo "=== Writing preliminary summary to $E1_SUMMARY ==="
{
    echo "# E1 baseline signature probe results (preliminary)"
    echo
    echo "- Target:     \`$APP_URL\`"
    echo "- Endpoint:   \`/slow/${PROBE_DURATION}\`"
    echo "- Iterations: $ITERATIONS"
    echo "- CSV:        \`$(basename "$SIGNATURE_CSV")\`"
    echo
    echo "## Client-side observations"
    echo
    echo "| # | http | time_total_s | curl_exit |"
    echo "|---|---|---|---|"
    tail -n +2 "$SIGNATURE_CSV" | while IFS=, read -r idx _ code total exit_code _ _ _; do
        printf "| %s | %s | %s | %s |\n" "$idx" "$code" "$total" "$exit_code"
    done
    echo
    echo "## Adaptive extension trigger evaluation"
    echo
    echo "This script does NOT decide whether to extend iterations because"
    echo "AppServiceHTTPLogs ingestion has ~2-5 minute latency. Run \`verify.sh\`"
    echo "after post-flight config collection to:"
    echo
    echo "1. Query server-side \`ScStatus\`, \`ScSubStatus\`, \`ScWin32Status\`, \`TimeTaken\` for these iterations."
    echo "2. Evaluate L1-H1R success criterion: 100% \`500/121\` and \`TimeTaken\` in [229800, 230500] ms with stddev < 200 ms."
    echo "3. Evaluate L1-H2R success criterion: 100% \`ScWin32Status = 0\`."
    echo "4. If either criterion fails and this run used <\ ${MAX_ITERATIONS} iterations, re-run with:"
    echo "   \`ITERATIONS=${MAX_ITERATIONS} bash $(basename "$0") $APP_URL $OUTPUT_DIR\`"
} > "$E1_SUMMARY"

echo
echo "E1 complete. Client-side data written to:"
echo "  CSV:     $SIGNATURE_CSV"
echo "  Summary: $E1_SUMMARY"
echo
echo "Next: bash run-e2-config-visibility.sh <APP_NAME> <RESOURCE_GROUP_NAME> $OUTPUT_DIR"
