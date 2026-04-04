#!/bin/bash
set -euo pipefail

APP_URL_INPUT="${1:-${APP_URL:-}}"

if [ -z "$APP_URL_INPUT" ]; then
    echo "Usage: $0 <APP_URL>"
    echo "Example: $0 https://app-labmem-xxxxxxxx.azurewebsites.net"
    exit 1
fi

APP_URL="${APP_URL_INPUT%/}"

echo "Starting memory-pressure trigger against: $APP_URL"
echo "Phase 1/2: Sending 100 sequential /leak requests"

leak_failures=0
for request_number in $(seq 1 100); do
    status_code=$(curl --silent --show-error --output /dev/null --write-out "%{http_code}" "$APP_URL/leak")
    if [ "$status_code" -ge 500 ]; then
        leak_failures=$((leak_failures + 1))
    fi
    if [ $((request_number % 20)) -eq 0 ]; then
        echo "  /leak progress: $request_number/100"
    fi
done

echo "Phase 2/2: Sending 50 concurrent /heavy requests"

heavy_status_dir=$(mktemp --directory)
for request_number in $(seq 1 50); do
    (
        status_code=$(curl --silent --show-error --output /dev/null --write-out "%{http_code}" "$APP_URL/heavy")
        printf "%s\n" "$status_code" > "$heavy_status_dir/$request_number.status"
    ) &

    while [ "$(jobs -r | wc -l)" -ge 10 ]; do
        sleep 0.2
    done
done

wait

heavy_failures=0
for status_file in "$heavy_status_dir"/*.status; do
    status_code=$(<"$status_file")
    if [ "$status_code" -ge 500 ]; then
        heavy_failures=$((heavy_failures + 1))
    fi
done

rm --recursive --force "$heavy_status_dir"

echo
echo "Trigger complete."
echo "  /leak failures (HTTP 5xx): $leak_failures"
echo "  /heavy failures (HTTP 5xx): $heavy_failures"
echo
echo "Expected observation: rising memory usage, potential Gunicorn worker timeouts," \
     "and possible restart or degradation signals in logs."
