#!/bin/bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 <APP_URL> [OUTPUT_DIR]"
    echo "Example: $0 https://app-winjavatimeout-abcd.azurewebsites.net ./results"
    exit 1
fi

APP_URL="$1"
OUTPUT_DIR="${2:-./stage0-results-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUTPUT_DIR"

PROBE_DURATIONS=(60 180 210 220 225 240 300 360)
CURL_MAX_TIME=400
INTER_PROBE_SLEEP=15
STREAM_MAX_TIME=310

SLOW_CSV="${OUTPUT_DIR}/slow-probes.csv"
STREAM_CSV="${OUTPUT_DIR}/stream-probes.csv"
SUMMARY_MD="${OUTPUT_DIR}/summary.md"

echo "=== Timeout probe target: $APP_URL ==="
echo "  Output dir: $OUTPUT_DIR"
echo "  Probes:     ${PROBE_DURATIONS[*]}"
echo "  curl --max-time: ${CURL_MAX_TIME}s"
echo "  Sleep between probes: ${INTER_PROBE_SLEEP}s"
echo

echo "requested_seconds,http_code,time_total_sec,curl_exit_code,started_utc,ended_utc" > "$SLOW_CSV"

echo "Step 1/2: /slow/{n} probes (no bytes emitted until completion)"
for duration in "${PROBE_DURATIONS[@]}"; do
    STARTED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    START_EPOCH=$(date +%s)
    set +e
    RESULT="$(curl --silent --output /dev/null \
        --max-time "$CURL_MAX_TIME" \
        --write-out '%{http_code},%{time_total}' \
        "${APP_URL}/slow/${duration}")"
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

    echo "${duration},${HTTP_CODE},${TIME_TOTAL},${CURL_EXIT},${STARTED_UTC},${ENDED_UTC}" >> "$SLOW_CSV"
    echo "  /slow/${duration}: http=${HTTP_CODE} time=${TIME_TOTAL}s curl_exit=${CURL_EXIT}"

    # Completion-safe pacing: when the front-end cuts curl at ~230s but the
    # backend Thread.sleep(duration) keeps running, the next probe would
    # overlap with orphan backend work and break the queue-depth-1 assumption.
    # Wait for the estimated backend completion (duration seconds from start)
    # plus a 10s buffer, or the fixed INTER_PROBE_SLEEP - whichever is larger.
    BACKEND_REMAINING="$(awk -v d="$duration" -v t="$TIME_TOTAL" \
        'BEGIN { r = d - t + 10; if (r < 0) r = 0; printf "%d", r }')"
    if [[ $BACKEND_REMAINING -gt $INTER_PROBE_SLEEP ]]; then
        SLEEP_FOR=$BACKEND_REMAINING
    else
        SLEEP_FOR=$INTER_PROBE_SLEEP
    fi
    echo "  waiting ${SLEEP_FOR}s (backend completion + buffer)"
    sleep "$SLEEP_FOR"
done

echo
echo "Step 2/2: /stream/300 probe (H7 idle-vs-absolute-timeout falsification)"
echo "requested_seconds,http_code,time_total_sec,curl_exit_code,bytes_received,started_utc,ended_utc" > "$STREAM_CSV"
STREAM_TMP="$(mktemp)"
trap 'rm -f "$STREAM_TMP"' EXIT

STARTED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
START_EPOCH=$(date +%s)
set +e
STREAM_RESULT="$(curl --silent --output "$STREAM_TMP" \
    --max-time "$STREAM_MAX_TIME" \
    --write-out '%{http_code},%{time_total}' \
    "${APP_URL}/stream/300")"
STREAM_EXIT=$?
set -e
ENDED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
END_EPOCH=$(date +%s)

if [[ -z "$STREAM_RESULT" ]]; then
    STREAM_HTTP="000"
    STREAM_TIME="$((END_EPOCH - START_EPOCH))"
else
    STREAM_HTTP="$(echo "$STREAM_RESULT" | cut -d',' -f1)"
    STREAM_TIME="$(echo "$STREAM_RESULT" | cut -d',' -f2)"
fi
STREAM_BYTES="$(wc -c < "$STREAM_TMP" | tr -d ' ')"

echo "300,${STREAM_HTTP},${STREAM_TIME},${STREAM_EXIT},${STREAM_BYTES},${STARTED_UTC},${ENDED_UTC}" >> "$STREAM_CSV"
echo "  /stream/300: http=${STREAM_HTTP} time=${STREAM_TIME}s curl_exit=${STREAM_EXIT} bytes=${STREAM_BYTES}"

cp "$STREAM_TMP" "${OUTPUT_DIR}/stream-body.ndjson" 2>/dev/null || true

echo
echo "=== Writing summary to $SUMMARY_MD ==="
{
    echo "# Stage 0 timeout probe results"
    echo
    echo "- Target: \`$APP_URL\`"
    echo "- Started: $(head -2 "$SLOW_CSV" | tail -1 | cut -d',' -f5)"
    echo "- Ended:   ${ENDED_UTC}"
    echo
    echo "## /slow/{n} probes"
    echo
    echo "| requested_s | http_code | time_total_s | curl_exit |"
    echo "|---|---|---|---|"
    tail -n +2 "$SLOW_CSV" | while IFS=, read -r req code total exit_code _ _; do
        printf "| %s | %s | %s | %s |\n" "$req" "$code" "$total" "$exit_code"
    done
    echo
    echo "## /stream/300 probe (H7 test)"
    echo
    echo "| requested_s | http_code | time_total_s | curl_exit | bytes_received |"
    echo "|---|---|---|---|---|"
    tail -n +2 "$STREAM_CSV" | while IFS=, read -r req code total exit_code bytes _ _; do
        printf "| %s | %s | %s | %s | %s |\n" "$req" "$code" "$total" "$exit_code" "$bytes"
    done
    echo
    echo "## Interpretation (see stage-0-config-discovery/README.md)"
    echo
    echo "- If /slow/{n} succeeds for all n <= 230 and cuts around 230s for n > 230: front-end limit is 230s (default)"
    echo "- If /slow cuts around 120s: httpPlatformHandler requestTimeout default (120s) is in force"
    echo "- If /stream/300 completes with 11 chunks: 230s is an IDLE timeout"
    echo "- If /stream/300 cuts around 230s: 230s is an ABSOLUTE request-duration limit"
} > "$SUMMARY_MD"

echo
echo "Probe complete. Results:"
echo "  CSV (slow):    $SLOW_CSV"
echo "  CSV (stream):  $STREAM_CSV"
echo "  Stream body:   ${OUTPUT_DIR}/stream-body.ndjson"
echo "  Summary:       $SUMMARY_MD"
echo
echo "Next: bash collect-effective-config.sh <APP_NAME> <RESOURCE_GROUP_NAME> $OUTPUT_DIR"
