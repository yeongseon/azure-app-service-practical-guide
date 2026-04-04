#!/bin/bash
set -euo pipefail

APP_URL_INPUT="${1:-${APP_URL:-}}"

if [ -z "$APP_URL_INPUT" ]; then
    echo "Usage: $0 <APP_URL>"
    echo "Example: $0 https://app-labsnat-xxxxxxxx.azurewebsites.net"
    exit 1
fi

APP_URL="${APP_URL_INPUT%/}"

echo "Starting SNAT exhaustion trigger against: $APP_URL"
echo "Phase 1/1: Sending 200 concurrent requests to /outbound"

status_dir=$(mktemp --directory)

for request_number in $(seq 1 200); do
    (
        status_code=$(curl \
            --silent \
            --show-error \
            --output /dev/null \
            --write-out "%{http_code}" \
            "$APP_URL/outbound?calls=40")
        printf "%s\n" "$status_code" > "$status_dir/$request_number.status"
    ) &

    while [ "$(jobs -r | wc -l)" -ge 20 ]; do
        sleep 0.2
    done

    if [ $((request_number % 20)) -eq 0 ]; then
        echo "  progress: $request_number/200"
    fi
done

wait

request_failures=0
http_5xx=0
for status_file in "$status_dir"/*.status; do
    status_code=$(<"$status_file")
    if [ "$status_code" -eq 000 ]; then
        request_failures=$((request_failures + 1))
    elif [ "$status_code" -ge 500 ]; then
        http_5xx=$((http_5xx + 1))
    fi
done

rm --recursive --force "$status_dir"

echo
echo "Trigger complete."
echo "  Transport failures (curl 000): $request_failures"
echo "  HTTP failures (5xx): $http_5xx"
echo
echo "Next: run verify.sh to query Log Analytics for SNAT indicators."
