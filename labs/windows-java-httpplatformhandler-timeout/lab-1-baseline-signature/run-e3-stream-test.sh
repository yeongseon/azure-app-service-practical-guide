#!/bin/bash
set -euo pipefail

# E3 stream absolute-vs-idle timer probe (L1-H4).
#
# Design (per design-proposal.md revision 2, Oracle-approved):
# - Single /stream/300 request. main.bicep sets
#   SPRING_MVC_ASYNC_REQUEST_TIMEOUT=600000 so the platform-level timer
#   (front-end 230s) determines cutoff rather than the Spring MVC async
#   30s default.
# - Chunk boundary is 30s; a full completion produces 11 chunks (0..10).
#   A 230s ABSOLUTE cut produces ~8 chunks (0..7) at t=0,30,60,90,120,150,180,210.
# - --max-time 320s exceeds both the ABSOLUTE ceiling (230s) and the target
#   duration (300s) with margin for platform overhead.

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 <APP_URL> [OUTPUT_DIR]"
    echo "Example: $0 https://app-winjavatimeoutl1-abcd.azurewebsites.net ./results"
    exit 1
fi

APP_URL="$1"
OUTPUT_DIR="${2:-./lab1-results-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUTPUT_DIR"

STREAM_DURATION=300
STREAM_MAX_TIME=320
EXPECTED_CHUNKS_IDLE=11
EXPECTED_CHUNKS_ABSOLUTE=8

STREAM_CSV="${OUTPUT_DIR}/e3-stream-probe.csv"
STREAM_BODY="${OUTPUT_DIR}/e3-stream-body.ndjson"
E3_SUMMARY="${OUTPUT_DIR}/e3-summary.md"

echo "=== E3 /stream/${STREAM_DURATION} probe: $APP_URL ==="
echo "  Output dir:      $OUTPUT_DIR"
echo "  curl --max-time: ${STREAM_MAX_TIME}s"
echo "  Expected chunks: IDLE=${EXPECTED_CHUNKS_IDLE}, ABSOLUTE=${EXPECTED_CHUNKS_ABSOLUTE}"
echo

echo "requested_seconds,http_code,time_total_sec,curl_exit_code,bytes_received,chunk_count,started_utc,ended_utc" > "$STREAM_CSV"

STARTED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
START_EPOCH=$(date +%s)

echo "Firing single /stream/${STREAM_DURATION} request..."
set +e
RESULT="$(curl --silent --no-buffer --output "$STREAM_BODY" \
    --max-time "$STREAM_MAX_TIME" \
    --write-out '%{http_code},%{time_total}' \
    "${APP_URL}/stream/${STREAM_DURATION}")"
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
BYTES_RECEIVED="$(wc -c < "$STREAM_BODY" 2>/dev/null | tr -d ' ' || echo 0)"
# grep -c prints "0" on zero matches and also exits 1; the `|| echo 0` then
# adds a second "0", producing "0\n0". Discard grep's exit code by piping
# through a filter so grep's stdout ("0" or the real count) is authoritative.
CHUNK_COUNT="$(grep -c '"chunkIndex"' "$STREAM_BODY" 2>/dev/null | head -1)"
CHUNK_COUNT="${CHUNK_COUNT:-0}"

echo "${STREAM_DURATION},${HTTP_CODE},${TIME_TOTAL},${CURL_EXIT},${BYTES_RECEIVED},${CHUNK_COUNT},${STARTED_UTC},${ENDED_UTC}" >> "$STREAM_CSV"

echo
echo "Result:"
echo "  http_code:      $HTTP_CODE"
echo "  time_total:     ${TIME_TOTAL}s"
echo "  curl_exit_code: $CURL_EXIT"
echo "  bytes_received: $BYTES_RECEIVED"
echo "  chunk_count:    $CHUNK_COUNT"

# Route the observation to a preliminary verdict. verify.sh performs the
# authoritative correlation with AppServiceHTTPLogs.TimeTaken and
# AppServiceConsoleLogs stream.* events (client-side timing is affected by
# curl's TCP close latency; server-side TimeTaken is the source of truth).
VERDICT_LABEL="unknown"
VERDICT_DETAIL=""
TIME_INT="$(printf '%.0f' "$TIME_TOTAL")"
if [[ $CHUNK_COUNT -eq $EXPECTED_CHUNKS_IDLE && $TIME_INT -ge 290 && $TIME_INT -le 320 ]]; then
    VERDICT_LABEL="IDLE"
    VERDICT_DETAIL="all $EXPECTED_CHUNKS_IDLE chunks received and time_total in [290s, 320s] window"
elif [[ $CHUNK_COUNT -ge 7 && $CHUNK_COUNT -le 9 && $TIME_INT -ge 225 && $TIME_INT -le 240 ]]; then
    VERDICT_LABEL="ABSOLUTE"
    VERDICT_DETAIL="~$EXPECTED_CHUNKS_ABSOLUTE chunks (got $CHUNK_COUNT) and time_total near 230s cut"
else
    VERDICT_DETAIL="chunk_count=$CHUNK_COUNT time_total=${TIME_TOTAL}s does not match either interpretation cleanly; investigate"
fi
echo "  preliminary:    $VERDICT_LABEL ($VERDICT_DETAIL)"

echo
echo "=== Writing E3 summary to $E3_SUMMARY ==="
{
    echo "# E3 stream absolute-vs-idle probe results (preliminary)"
    echo
    echo "- Target:     \`$APP_URL\`"
    echo "- Endpoint:   \`/stream/${STREAM_DURATION}\`"
    echo "- CSV:        \`$(basename "$STREAM_CSV")\`"
    echo "- Body:       \`$(basename "$STREAM_BODY")\`"
    echo
    echo "## Client observation"
    echo
    echo "| field | value |"
    echo "|---|---|"
    echo "| http_code | $HTTP_CODE |"
    echo "| time_total | ${TIME_TOTAL}s |"
    echo "| curl_exit_code | $CURL_EXIT |"
    echo "| bytes_received | $BYTES_RECEIVED |"
    echo "| chunk_count | $CHUNK_COUNT |"
    echo "| started_utc | $STARTED_UTC |"
    echo "| ended_utc | $ENDED_UTC |"
    echo
    echo "## Preliminary H4 verdict"
    echo
    echo "- **$VERDICT_LABEL** - $VERDICT_DETAIL"
    echo
    echo "Authoritative verdict is written by \`verify.sh\` using \`AppServiceHTTPLogs.TimeTaken\`"
    echo "and \`AppServiceConsoleLogs\` \`stream.start/chunk/end/interrupted\` events."
    echo
    echo "## Interpretation matrix (from design-proposal.md)"
    echo
    echo "| server TimeTaken | client chunks | verdict |"
    echo "|---|---|---|"
    echo "| ~230000 ms | ~8 | ABSOLUTE (front-end 230s is total request duration) |"
    echo "| ~300000 ms | 11 | IDLE (server-sent bytes reset front-end counter) |"
    echo "| other | other | ambiguous - document as anomaly |"
    echo
    echo "## Next"
    echo
    echo "\`\`\`bash"
    echo "bash collect-effective-config.sh <APP_NAME> <RESOURCE_GROUP_NAME> $OUTPUT_DIR"
    echo "bash verify.sh <APP_NAME> <RESOURCE_GROUP_NAME> <WORKSPACE_ID> $OUTPUT_DIR"
    echo "\`\`\`"
} > "$E3_SUMMARY"

echo
echo "E3 complete."
echo "  CSV:     $STREAM_CSV"
echo "  Body:    $STREAM_BODY"
echo "  Summary: $E3_SUMMARY"
