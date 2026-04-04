#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <APP_URL>"
    echo "Example: $0 https://app-lab5xx-xxxx.azurewebsites.net"
    exit 1
fi

APP_URL="$1"
SLOW_CONCURRENCY=20
FAST_REQUESTS=10
RESULTS_DIR="$(mktemp -d)"

cleanup() {
    rm -rf "$RESULTS_DIR"
}
trap cleanup EXIT

run_request() {
    local endpoint="$1"
    local index="$2"
    local output_file="$RESULTS_DIR/${endpoint}-${index}.txt"

    curl --silent --show-error --output /dev/null \
        --max-time 45 \
        --write-out "${endpoint},${index},%{http_code},%{time_total}\n" \
        "${APP_URL}/${endpoint}" > "$output_file"
}

echo "Launching ${SLOW_CONCURRENCY} concurrent requests to ${APP_URL}/slow"
pids=()
for i in $(seq 1 "$SLOW_CONCURRENCY"); do
    run_request "slow" "$i" &
    pids+=("$!")
done

echo "Immediately sending ${FAST_REQUESTS} requests to ${APP_URL}/fast"
for i in $(seq 1 "$FAST_REQUESTS"); do
    run_request "fast" "$i"
done

echo "Waiting for background /slow requests to complete"
for pid in "${pids[@]}"; do
    wait "$pid"
done

echo
echo "Raw request results (endpoint,index,http_code,time_seconds):"
cat "$RESULTS_DIR"/*.txt | sort

echo
echo "Status code distribution:"
cat "$RESULTS_DIR"/*.txt | awk -F',' '{print $3}' | sort | uniq -c | awk '{printf "  HTTP %s: %s\n", $2, $1}'

echo
echo "Average latency by endpoint:"
cat "$RESULTS_DIR"/*.txt | awk -F',' '{sum[$1]+=$4; count[$1]++} END {for (endpoint in sum) printf "  %s: %.2fs (%d requests)\n", endpoint, sum[endpoint]/count[endpoint], count[endpoint]}' | sort
